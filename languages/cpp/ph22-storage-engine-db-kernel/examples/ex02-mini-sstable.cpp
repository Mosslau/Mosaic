// ex02-mini-sstable.cpp —— SSTable：不可变有序文件的 block 布局 / writer / reader 点查
// 对应 ph22 主文档 3.3 与 roadmap §22「设计 SSTable block header 并实现 Mini SSTable writer/reader」。
// 教学点：
//   ① SSTable = 不可变有序文件：MemTable flush 一次写出、之后只读——不可变带来
//      免锁读、崩溃安全（不会半改）、可放心缓存；
//   ② 文件布局（本示例的教学简化版）：
//        [数据区]  block*（每块 k_block_cap 条，升序）：
//                  entry = [klen u32][vlen u32][key][value]
//        [索引区]  每数据块 1 条：块首 key + 块在文件中的偏移（稀疏索引，可整体载入内存二分）
//        [footer]  定长 24 字节：data_off u64 | index_off u64 | index_size u32 | magic u32
//   ③ 点查路径三步：读 footer（文件尾定长定位）→ 载入索引对「块首 key」二分
//      → 跳到命中块内顺序扫（≤ 块容量）→ 比最小块首 key 还小的查询零数据区扫描；
//   ④ 教学简化（注明）：整文件读入内存模拟真实引擎的页缓存形态，教学重点在
//      偏移解析与索引跳转；真实引擎用 mmap/顺序读 + Buffer Pool 管理页，见主文档 3.3/3.7。
// 资源管理：RAII fd（R.1）；vector<uint8_t> 拥有文件字节，无裸 new/delete（R.11）。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -Wall -Wextra ex02-mini-sstable.cpp -o /tmp/ph22-ex02 && /tmp/ph22-ex02
// 验证状态：已验证（零警告、断言全绿、退出码 0）

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace sst {

constexpr std::uint32_t k_magic = 0x53535432u;  // ASCII "SST2"
constexpr std::size_t k_footer_size = 24;       // data_off u64 | index_off u64 | index_size u32 | magic u32
constexpr std::size_t k_block_cap = 4;          // 每块最多 4 条 → 块内顺扫 ≤ 4 条
constexpr std::size_t k_max_kv = 64u * 1024u;   // 长度上限防护

struct kv_entry {
    std::string key;
    std::string value;
};

// —— RAII 文件描述符（与 ex01 同款；教学性重复以保持单文件自包含）——
class fd_file {
public:
    explicit fd_file(int fd) : fd_{fd} {}
    ~fd_file() {
        if (fd_ >= 0) {
            ::close(fd_);
        }
    }
    fd_file(const fd_file&) = delete;
    fd_file& operator=(const fd_file&) = delete;
    fd_file(fd_file&& other) noexcept : fd_{std::exchange(other.fd_, -1)} {}
    fd_file& operator=(fd_file&& other) noexcept {
        if (this != &other) {
            if (fd_ >= 0) {
                ::close(fd_);
            }
            fd_ = std::exchange(other.fd_, -1);
        }
        return *this;
    }
    int get() const { return fd_; }

private:
    int fd_;
};

// —— 大端编码/解码（与 ex01 同款线上格式纪律，跨语言可对照）——
void put_u32be(std::uint8_t* buf, std::uint32_t v) {
    buf[0] = static_cast<std::uint8_t>((v >> 24) & 0xFFu);
    buf[1] = static_cast<std::uint8_t>((v >> 16) & 0xFFu);
    buf[2] = static_cast<std::uint8_t>((v >> 8) & 0xFFu);
    buf[3] = static_cast<std::uint8_t>(v & 0xFFu);
}

void put_u64be(std::uint8_t* buf, std::uint64_t v) {
    put_u32be(buf, static_cast<std::uint32_t>(v >> 32));
    put_u32be(buf + 4, static_cast<std::uint32_t>(v & 0xFFFFFFFFu));
}

std::uint32_t get_u32be(const std::uint8_t* buf) {
    return (static_cast<std::uint32_t>(buf[0]) << 24) |
           (static_cast<std::uint32_t>(buf[1]) << 16) |
           (static_cast<std::uint32_t>(buf[2]) << 8) |
           static_cast<std::uint32_t>(buf[3]);
}

std::uint64_t get_u64be(const std::uint8_t* buf) {
    return (static_cast<std::uint64_t>(get_u32be(buf)) << 32) |
           static_cast<std::uint64_t>(get_u32be(buf + 4));
}

void append_str(std::vector<std::uint8_t>& out, std::string_view s) {
    out.insert(out.end(), s.begin(), s.end());
}

void append_u32(std::vector<std::uint8_t>& out, std::uint32_t v) {
    std::uint8_t b[4];
    put_u32be(b, v);
    out.insert(out.end(), b, b + 4);
}

void append_u64(std::vector<std::uint8_t>& out, std::uint64_t v) {
    std::uint8_t b[8];
    put_u64be(b, v);
    out.insert(out.end(), b, b + 8);
}

struct build_stats {
    std::uint64_t file_size;
    std::size_t block_count;
};

// —— writer：数据区（块升序）+ 索引区（块首 key → 块偏移）+ 定长 footer ——
// 前置条件：entries 已按 key 升序且无重复（MemTable flush 天然满足，见主文档 3.2/3.3）。
build_stats write_sstable(const std::string& path, const std::vector<kv_entry>& entries) {
    std::vector<std::uint8_t> data;   // 数据区
    std::vector<std::uint8_t> index;  // 索引区
    std::size_t block_cnt = 0;
    std::uint16_t in_block = 0;
    std::string first_key;                 // 当前块的块首 key
    std::uint64_t block_start = 0;         // 当前块在数据区中的起始偏移

    auto close_block = [&]() {
        if (in_block == 0) {
            return;
        }
        append_u32(index, static_cast<std::uint32_t>(first_key.size()));
        append_str(index, first_key);
        append_u64(index, block_start);  // 块在文件中的起始偏移（二分定位后用）
        ++block_cnt;
        in_block = 0;
    };

    for (const auto& e : entries) {
        if (e.key.size() + e.value.size() > k_max_kv) {
            throw std::runtime_error("entry too large");
        }
        if (in_block == 0) {
            first_key = e.key;
            block_start = data.size();  // ★ 记「块首条落盘前」的偏移，而非块封口时
        }
        append_u32(data, static_cast<std::uint32_t>(e.key.size()));
        append_u32(data, static_cast<std::uint32_t>(e.value.size()));
        append_str(data, e.key);
        append_str(data, e.value);
        ++in_block;
        if (in_block == k_block_cap) {
            close_block();
        }
    }
    close_block();  // 末块不足 k_block_cap 也封

    // footer：data_off u64 | index_off u64 | index_size u32 | magic u32
    std::vector<std::uint8_t> footer;
    append_u64(footer, 0);  // data_off = 0（数据区恒在文件头）
    append_u64(footer, static_cast<std::uint64_t>(data.size()));
    append_u32(footer, static_cast<std::uint32_t>(index.size()));
    append_u32(footer, k_magic);

    std::vector<std::uint8_t> file;
    file.reserve(data.size() + index.size() + footer.size());
    file.insert(file.end(), data.begin(), data.end());
    file.insert(file.end(), index.begin(), index.end());
    file.insert(file.end(), footer.begin(), footer.end());

    const int fd = ::open(path.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) {
        throw std::runtime_error("open(write) failed: " + path);
    }
    fd_file f{fd};
    std::size_t done = 0;
    while (done < file.size()) {
        const ssize_t w = ::write(f.get(), file.data() + done, file.size() - done);
        if (w < 0) {
            if (errno == EINTR) {
                continue;
            }
            throw std::runtime_error("write failed");
        }
        done += static_cast<std::size_t>(w);
    }
    if (::fsync(f.get()) != 0) {
        throw std::runtime_error("fsync failed");
    }
    return {static_cast<std::uint64_t>(file.size()), block_cnt};
}

// —— reader：open 读整文件进内存（教学简化）→ 解析 footer → 载入索引 → get ——
class sstable_reader {
public:
    struct index_item {
        std::string first_key;
        std::uint64_t offset;
    };

    explicit sstable_reader(const std::string& path) {
        const int fd = ::open(path.c_str(), O_RDONLY);
        if (fd < 0) {
            throw std::runtime_error("open(read) failed: " + path);
        }
        fd_file f{fd};
        const off_t sz = ::lseek(f.get(), 0, SEEK_END);
        if (sz < 0) {
            throw std::runtime_error("lseek failed");
        }
        const std::size_t file_size = static_cast<std::size_t>(sz);
        if (file_size < k_footer_size) {
            throw std::runtime_error("file too small to be sstable");
        }
        ::lseek(f.get(), 0, SEEK_SET);
        bytes_.resize(file_size);
        std::size_t done = 0;
        while (done < file_size) {
            const ssize_t r = ::read(f.get(), bytes_.data() + done, file_size - done);
            if (r <= 0) {
                throw std::runtime_error("read failed");
            }
            done += static_cast<std::size_t>(r);
        }

        // footer 定长 24 字节：直接定位到文件尾
        const std::uint8_t* ft = bytes_.data() + (file_size - k_footer_size);
        const std::uint64_t index_off = get_u64be(ft + 8);
        const std::uint32_t index_size = get_u32be(ft + 16);
        if (get_u32be(ft + 20) != k_magic) {
            throw std::runtime_error("sstable magic mismatch");
        }
        data_end_ = index_off;

        // 解析索引区：每项 = klen u32 + key + block_off u64
        std::size_t p = static_cast<std::size_t>(index_off);
        const std::size_t index_end = p + index_size;
        while (p + 12 <= index_end) {
            const std::uint32_t klen = get_u32be(bytes_.data() + p);
            p += 4;
            if (p + klen + 8 > index_end || klen > k_max_kv) {
                throw std::runtime_error("bad index entry");
            }
            index_item item;
            item.first_key.assign(reinterpret_cast<const char*>(bytes_.data() + p), klen);
            p += klen;
            item.offset = get_u64be(bytes_.data() + p);
            p += 8;
            if (item.offset > data_end_) {
                throw std::runtime_error("index offset out of data area");
            }
            index_.push_back(std::move(item));
        }
        if (p != index_end) {
            throw std::runtime_error("index area not fully consumed");
        }
    }

    std::size_t block_count() const { return index_.size(); }

    // 点查：不存在返回 nullopt；用输出参数统计定位代价（教学用，不入生产接口）
    std::optional<std::string> get(const std::string& key, std::size_t* index_steps,
                                   std::size_t* entries_scanned) const {
        *index_steps = 0;
        *entries_scanned = 0;
        // 1. 索引二分：最后一个 first_key <= key 的块
        std::size_t lo = 0;
        std::size_t hi = index_.size();
        while (lo < hi) {
            const std::size_t mid = lo + (hi - lo) / 2;
            ++*index_steps;
            if (index_[mid].first_key <= key) {
                lo = mid + 1;
            } else {
                hi = mid;
            }
        }
        if (lo == 0) {
            return std::nullopt;  // 比首个块首 key 还小 → 零数据区扫描
        }
        // 2. 块内顺扫：≤ k_block_cap 条（末块可能更少），扫到命中/越界/数据区尽头即停
        std::size_t p = static_cast<std::size_t>(index_[lo - 1].offset);
        for (std::size_t i = 0; i < k_block_cap && p + 8 <= data_end_; ++i) {
            ++*entries_scanned;
            const std::uint32_t klen = get_u32be(bytes_.data() + p);
            const std::uint32_t vlen = get_u32be(bytes_.data() + p + 4);
            p += 8;
            if (p + klen + vlen > data_end_ || klen + vlen > k_max_kv) {
                break;  // 损坏防护
            }
            const std::string k(reinterpret_cast<const char*>(bytes_.data() + p), klen);
            if (k == key) {
                return std::string(reinterpret_cast<const char*>(bytes_.data() + p + klen), vlen);
            }
            if (k > key) {
                break;  // 块内有序：已越过目标
            }
            p += klen + vlen;
        }
        return std::nullopt;
    }

private:
    std::vector<std::uint8_t> bytes_;
    std::vector<index_item> index_;
    std::uint64_t data_end_{0};  // 数据区终点 = 索引区起点（块内顺扫的界）
};

}  // namespace sst

// —— 测试框架 ——
static int g_failed = 0;
static int g_checks = 0;

#define CHECK(cond)                                                        \
    do {                                                                   \
        ++g_checks;                                                        \
        if (!(cond)) {                                                     \
            std::cerr << "FAIL: " << #cond << " (line " << __LINE__ << ")\n"; \
            ++g_failed;                                                    \
        }                                                                  \
    } while (0)

int main() {
    // 10 条有序记录 → 3 个数据块（4+4+2）
    const std::vector<sst::kv_entry> entries = {
        {"ape", "v-ape"},  {"bee", "v-bee"},  {"cat", "v-cat"},  {"dog", "v-dog"},
        {"eel", "v-eel"},  {"fox", "v-fox"},  {"gnu", "v-gnu"},  {"hog", "v-hog"},
        {"ibis", "v-ibis"}, {"jay", "v-jay"},
    };
    const std::string path = "/tmp/ph22-ex02.sst";
    ::unlink(path.c_str());

    const auto st = sst::write_sstable(path, entries);
    std::cout << "[1] 写出 " << path << ": " << st.file_size << " 字节, "
              << st.block_count << " 个数据块 (每块容量 " << sst::k_block_cap << ")\n";
    CHECK(st.block_count == 3);
    CHECK(st.file_size > 0);

    sst::sstable_reader r{path};
    CHECK(r.block_count() == 3);

    std::size_t steps = 0;
    std::size_t scanned = 0;
    auto probe = [&](const std::string& key) -> std::optional<std::string> {
        steps = 0;
        scanned = 0;
        auto v = r.get(key, &steps, &scanned);
        std::cout << "    get(\"" << key << "\") -> "
                  << (v.has_value() ? ("\"" + *v + "\"") : "(not found)")
                  << "  [索引二分 " << steps << " 步, 块内扫 " << scanned << " 条]\n";
        return v;
    };

    std::cout << "[2] 点查（跨块命中 / 块内命中 / 不存在）:\n";
    CHECK(probe("ape") == std::string("v-ape"));  // 第 1 块首条
    CHECK(probe("dog") == std::string("v-dog"));  // 第 1 块末条
    CHECK(probe("fox") == std::string("v-fox"));  // 第 2 块（索引二分定位到第 2 块）
    CHECK(probe("jay") == std::string("v-jay"));  // 末块末条 = 全文件末条
    CHECK(!probe("zzz").has_value());             // 不存在：定位到末块扫完即 miss
    CHECK(!probe("aaa").has_value());             // 比最小 key 还小：零数据区扫描
    CHECK(!probe("duck").has_value());            // 位于 dog..eel 之间：第 1 块内越界即停

    // “比最小 key 还小”的查询应不扫任何 entry
    std::size_t s2 = 99;
    std::size_t e2 = 99;
    r.get("aaa", &s2, &e2);
    CHECK(s2 >= 1 && e2 == 0);

    ::unlink(path.c_str());
    std::cout << "checks: " << g_checks << ", failed: " << g_failed << '\n';
    if (g_failed == 0) {
        std::cout << "ph22-ex02 OK\n";
        return 0;
    }
    return 1;
}
