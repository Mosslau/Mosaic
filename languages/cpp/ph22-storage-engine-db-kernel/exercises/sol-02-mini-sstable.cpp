// sol-02-mini-sstable.cpp —— exercises/练习 2 参考实现：设计 block header 并实现 Mini SSTable
// 题目见 exercises/README.md。本解的文件格式（解题者自定，这里给出一种“能校验、能断块”的设计）：
//   [数据区] block* ：
//       每 block 以 8 字节 header 开头：
//         [count u16][reserved u16][checksum u32]     ← block header 设计
//       然后 count 条 entry：[klen u32][vlen u32][key][value]，key 升序
//       checksum = CRC32(header 前 4 字节 + 本 block 全部 entry 字节)
//   [索引区] 每 block 一条：[klen u32][块首 key][block_off u64]
//   [footer] 定长 24 字节：[data_off u64][index_off u64][index_size u32][magic u32]
// 为什么 block header 里带校验和：SSTable 不可变 → 读到损坏 block 只能“拒绝服务”，
// 不能静默返回错误数据；校验和把“位衰减/半写”在第一次被触碰时暴露出来。
// 点查路径：footer → 索引二分（找最后一块首 key <= 目标）→ 读目标 block（校验）→ 块内顺扫。
// 资源管理：RAII fd_file + vector<uint8_t> 拥有文件字节（R.1/R.11）。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -Wall -Wextra sol-02-mini-sstable.cpp -o /tmp/ph22-sol02 && /tmp/ph22-sol02
// 验证状态：已验证（零警告、断言全绿、退出码 0）

#include <array>
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

namespace sst2 {

constexpr std::uint32_t k_magic = 0x53535432u;  // "SST2"
constexpr std::size_t k_footer = 24;
constexpr std::size_t k_block_header = 8;       // count u16 + reserved u16 + checksum u32
constexpr std::uint16_t k_block_cap = 4;        // 每块最多 4 条
constexpr std::uint32_t k_max_kv = 64u * 1024u;

struct kv {
    std::string key;
    std::string value;
};

// —— CRC32（表驱动；单文件自包含）——
static std::array<std::uint32_t, 256> crc_table() {
    std::array<std::uint32_t, 256> t{};
    for (std::uint32_t i = 0; i < 256; ++i) {
        std::uint32_t c = i;
        for (int b = 0; b < 8; ++b) {
            c = (c & 1u) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
        }
        t[i] = c;
    }
    return t;
}

std::uint32_t crc32(const void* data, std::size_t n) {
    static const auto table = crc_table();
    std::uint32_t c = 0xFFFFFFFFu;
    const auto* p = static_cast<const std::uint8_t*>(data);
    for (std::size_t i = 0; i < n; ++i) {
        c = table[(c ^ p[i]) & 0xFFu] ^ (c >> 8);
    }
    return c ^ 0xFFFFFFFFu;
}

std::uint32_t crc32_table_single(std::size_t idx) {
    static const auto table = crc_table();
    return table[idx & 0xFFu];
}

// CRC 增量：在已有 crc 基础上继续吃 n 字节（流式校验 block 用）
std::uint32_t crc32_add(std::uint32_t c, const void* data, std::size_t n) {
    const auto* p = static_cast<const std::uint8_t*>(data);
    for (std::size_t i = 0; i < n; ++i) {
        c = (c >> 8) ^ crc32_table_single((c ^ p[i]) & 0xFFu);
    }
    return c;
}

void put_u16(std::uint8_t* b, std::uint16_t v) {
    b[0] = static_cast<std::uint8_t>((v >> 8) & 0xFFu);
    b[1] = static_cast<std::uint8_t>(v & 0xFFu);
}

std::uint16_t get_u16(const std::uint8_t* b) {
    return static_cast<std::uint16_t>((static_cast<std::uint16_t>(b[0]) << 8) | b[1]);
}

void put_u32(std::uint8_t* b, std::uint32_t v) {
    b[0] = static_cast<std::uint8_t>((v >> 24) & 0xFFu);
    b[1] = static_cast<std::uint8_t>((v >> 16) & 0xFFu);
    b[2] = static_cast<std::uint8_t>((v >> 8) & 0xFFu);
    b[3] = static_cast<std::uint8_t>(v & 0xFFu);
}

std::uint32_t get_u32(const std::uint8_t* b) {
    return (static_cast<std::uint32_t>(b[0]) << 24) | (static_cast<std::uint32_t>(b[1]) << 16) |
           (static_cast<std::uint32_t>(b[2]) << 8) | static_cast<std::uint32_t>(b[3]);
}

void put_u64(std::uint8_t* b, std::uint64_t v) {
    put_u32(b, static_cast<std::uint32_t>(v >> 32));
    put_u32(b + 4, static_cast<std::uint32_t>(v & 0xFFFFFFFFu));
}

std::uint64_t get_u64(const std::uint8_t* b) {
    return (static_cast<std::uint64_t>(get_u32(b)) << 32) | get_u32(b + 4);
}

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
    fd_file(fd_file&& o) noexcept : fd_{std::exchange(o.fd_, -1)} {}
    int get() const { return fd_; }

private:
    int fd_;
};

// —— writer：entries（已升序、无重复）→ 数据区 + 索引 + footer 一次落盘 ——
std::uint64_t write_sstable(const std::string& path, const std::vector<kv>& entries) {
    std::vector<std::uint8_t> data;
    std::vector<std::uint8_t> index;
    std::size_t block_cnt = 0;
    std::uint16_t in_block = 0;
    std::uint64_t block_off = 0;
    std::string first_key;

    auto close_block = [&]() {
        if (in_block == 0) {
            return;
        }
        // 回填 block header：count/reserved 写数据区，checksum 写坑位
        const std::uint64_t start = block_off;
        std::uint8_t hdr[4];
        put_u16(hdr, in_block);
        put_u16(hdr + 2, 0);  // reserved（预留扩展位，如压缩标记）
        std::copy(hdr, hdr + 4, data.begin() + static_cast<std::ptrdiff_t>(start));
        // checksum 覆盖 header 前 4 字节 + 本 block 的 entry 字节
        const std::size_t block_len = data.size() - static_cast<std::size_t>(start);
        std::uint32_t c = crc32(hdr, 4);
        c = crc32_add(c, data.data() + static_cast<std::size_t>(start) + k_block_header,
                      block_len - k_block_header);
        put_u32(data.data() + static_cast<std::size_t>(start) + 4, c);
        // 索引项 = keylen u16 + 块首 key + block_off u64
        std::uint8_t kb[2];
        put_u16(kb, static_cast<std::uint16_t>(first_key.size()));
        index.insert(index.end(), kb, kb + 2);  // 索引也用 u16 定长 key len（教学约束 key < 64K）
        index.insert(index.end(), first_key.begin(), first_key.end());
        std::uint8_t offb[8];
        put_u64(offb, start);
        index.insert(index.end(), offb, offb + 8);
        ++block_cnt;
        in_block = 0;
    };

    for (const auto& e : entries) {
        if (e.key.size() + e.value.size() > k_max_kv || e.key.size() > 0xFFFFu) {
            throw std::runtime_error("entry too large");
        }
        if (in_block == 0) {
            // 新 block：先写 8 字节 header 坑（count/checksum 在 close_block 回填）
            first_key = e.key;
            block_off = data.size();
            data.insert(data.end(), k_block_header, 0);
        }
        std::uint8_t len[8];
        put_u32(len, static_cast<std::uint32_t>(e.key.size()));
        put_u32(len + 4, static_cast<std::uint32_t>(e.value.size()));
        data.insert(data.end(), len, len + 8);
        data.insert(data.end(), e.key.begin(), e.key.end());
        data.insert(data.end(), e.value.begin(), e.value.end());
        ++in_block;
        if (in_block == k_block_cap) {
            close_block();
        }
    }
    close_block();

    std::vector<std::uint8_t> file;
    file.reserve(data.size() + index.size() + k_footer);
    file.insert(file.end(), data.begin(), data.end());
    file.insert(file.end(), index.begin(), index.end());
    std::uint8_t ft[k_footer];
    put_u64(ft, 0);                                          // data_off
    put_u64(ft + 8, static_cast<std::uint64_t>(data.size()));  // index_off
    put_u32(ft + 16, static_cast<std::uint32_t>(index.size()));
    put_u32(ft + 20, k_magic);
    file.insert(file.end(), ft, ft + k_footer);

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
    return static_cast<std::uint64_t>(file.size());
}

// —— reader ——
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
        const std::size_t size = static_cast<std::size_t>(sz);
        if (size < k_footer) {
            throw std::runtime_error("too small");
        }
        ::lseek(f.get(), 0, SEEK_SET);
        bytes_.resize(size);
        std::size_t done = 0;
        while (done < size) {
            const ssize_t r = ::read(f.get(), bytes_.data() + done, size - done);
            if (r <= 0) {
                throw std::runtime_error("read failed");
            }
            done += static_cast<std::size_t>(r);
        }
        const std::uint8_t* ft = bytes_.data() + (size - k_footer);
        if (get_u32(ft + 20) != k_magic) {
            throw std::runtime_error("magic mismatch");
        }
        const std::uint64_t index_off = get_u64(ft + 8);
        const std::uint32_t index_size = get_u32(ft + 16);
        data_end_ = index_off;
        std::size_t p = static_cast<std::size_t>(index_off);
        const std::size_t end = p + index_size;
        while (p < end) {
            if (p + 2 > end) {
                throw std::runtime_error("bad index");
            }
            const std::uint16_t klen = get_u16(bytes_.data() + p);
            p += 2;
            if (p + klen + 8 > end) {
                throw std::runtime_error("bad index entry");
            }
            index_item item;
            item.first_key.assign(reinterpret_cast<const char*>(bytes_.data() + p), klen);
            p += klen;
            item.offset = get_u64(bytes_.data() + p);
            p += 8;
            index_.push_back(std::move(item));
        }
    }

    std::size_t block_count() const { return index_.size(); }

    // 点查：块校验失败抛异常（SSTable 不可变：损坏 = 拒绝服务而非错数据）
    std::optional<std::string> get(const std::string& key) const {
        std::size_t lo = 0;
        std::size_t hi = index_.size();
        while (lo < hi) {  // 最后一个 first_key <= key
            const std::size_t mid = lo + (hi - lo) / 2;
            if (index_[mid].first_key <= key) {
                lo = mid + 1;
            } else {
                hi = mid;
            }
        }
        if (lo == 0) {
            return std::nullopt;
        }
        const std::size_t off = static_cast<std::size_t>(index_[lo - 1].offset);
        const auto* hdr = bytes_.data() + off;
        const std::uint16_t count = get_u16(hdr);
        // 校验 block：header 前 4 字节 + entries
        const std::uint8_t h4[4] = {hdr[0], hdr[1], hdr[2], hdr[3]};
        const std::uint32_t expect = get_u32(hdr + 4);
        std::uint32_t c = crc32(h4, 4);
        // 一次遍历完成两件事：整块校验（必须消费 count 条全部字节）+
        // 块内线性找 key。生产上块解码本就整体发生，校验成本是解码的固定开销。
        std::size_t p = off + k_block_header;
        std::string hit_value;
        bool found = false;
        bool passed = false;  // 已越过目标 key → 后续条不再做字符串比较
        for (std::uint16_t i = 0; i < count; ++i) {
            if (p + 8 > static_cast<std::size_t>(data_end_)) {
                throw std::runtime_error("corrupt block: entry header overflow");
            }
            c = crc32_add(c, bytes_.data() + p, 8);
            const std::uint32_t klen = get_u32(bytes_.data() + p);
            const std::uint32_t vlen = get_u32(bytes_.data() + p + 4);
            p += 8;
            if (p + klen + vlen > static_cast<std::size_t>(data_end_)) {
                throw std::runtime_error("corrupt block: entry overflow");
            }
            c = crc32_add(c, bytes_.data() + p, klen + vlen);
            if (!passed) {
                const std::string k(reinterpret_cast<const char*>(bytes_.data() + p), klen);
                if (k == key) {
                    found = true;
                    hit_value.assign(reinterpret_cast<const char*>(bytes_.data() + p + klen), vlen);
                }
                if (k > key) {
                    passed = true;  // 有序：越过目标，后面只前进不做比较
                }
            }
            p += klen + vlen;
        }
        if (c != expect) {
            if (getenv("PH22_DBG")) {
                std::cerr << "[dbg] mismatch off=" << off << " count=" << count
                          << " expect=" << expect << " got=" << c
                          << " data_end=" << data_end_ << '\n';
            }
            throw std::runtime_error("block checksum mismatch");
        }
        return found ? std::optional<std::string>{std::move(hit_value)} : std::nullopt;
    }

private:
    std::vector<std::uint8_t> bytes_;
    std::vector<index_item> index_;
    std::uint64_t data_end_{0};
};

}  // namespace sst2

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
    // 9 条 → 3 block（4+4+1）
    std::vector<sst2::kv> entries;
    for (int i = 0; i < 9; ++i) {
        entries.push_back({std::string(1, static_cast<char>('a' + i)) + "aa",
                           "v" + std::to_string(i)});
    }
    const std::string path = "/tmp/ph22-sol02.sst";
    ::unlink(path.c_str());

    const std::uint64_t sz = sst2::write_sstable(path, entries);
    std::cout << "[1] 写出 " << sz << " 字节, block 数 = "
              << sst2::sstable_reader{path}.block_count() << " (期望 3)\n";
    CHECK(sst2::sstable_reader{path}.block_count() == 3);

    sst2::sstable_reader r{path};
    auto hit = [&](const std::string& k, const std::string& want) {
        const auto v = r.get(k);
        std::cout << "    get(\"" << k << "\") -> "
                  << (v ? ("\"" + *v + "\"") : "(not found)") << '\n';
        CHECK(v.has_value() && *v == want);
    };
    std::cout << "[2] 点查（首/末 block、边界、跨 block）:\n";
    hit("aaa", "v0");              // 第 1 块首条
    hit("daa", "v3");              // 第 1 块末条（恰好塞满）
    hit("eaa", "v4");              // 第 2 块首条（跨 block 定位）
    hit("iaa", "v8");              // 末块单条
    CHECK(!r.get("zza").has_value());
    CHECK(!r.get("abz").has_value());  // aaa..abz 之间，第 1 块内越界即停

    // [3] 篡改一个字节 → 点查该 block 触发 checksum 拒绝
    {
        const int fd = ::open(path.c_str(), O_RDWR);
        CHECK(fd >= 0);
        sst2::fd_file f{fd};
        std::uint8_t byte = 0;
        CHECK(::pread(f.get(), &byte, 1, 30) == 1);  // 第 1 块 entry 区某字节
        byte = static_cast<std::uint8_t>(byte ^ 0xFFu);
        CHECK(::pwrite(f.get(), &byte, 1, 30) == 1);
        bool threw = false;
        try {
            sst2::sstable_reader r2{path};
            (void)r2.get("aaa");  // 必须抛 checksum mismatch
        } catch (const std::runtime_error&) {
            threw = true;
        }
        std::cout << "[3] 篡改第 1 块一个字节后点查: "
                  << (threw ? "校验拒绝(抛异常) ✓" : "静默错数据 ✗") << '\n';
        CHECK(threw);
    }

    ::unlink(path.c_str());
    std::cout << "checks: " << g_checks << ", failed: " << g_failed << '\n';
    if (g_failed == 0) {
        std::cout << "ph22-sol-02 OK\n";
        return 0;
    }
    return 1;
}
