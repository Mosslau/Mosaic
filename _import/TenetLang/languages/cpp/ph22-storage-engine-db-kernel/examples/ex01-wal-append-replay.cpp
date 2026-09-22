// ex01-wal-append-replay.cpp —— WAL：record 格式 / append-only 追加 / replay 四道校验 / 残尾修复
// 对应 ph22 主文档 3.1/3.2 与 roadmap §22「实现 append-only WAL 写入与 replay」。
// 教学点：
//   ① record 布局 [magic u32 "WAL1"][type u8][klen u32][vlen u32][key][value][crc32 u32]
//      多字节字段显式大端（与 C 路线 ph16 同款纪律，跨语言可对照）；
//   ② append-only：O_APPEND + 短写循环；append 返回 ≠ 持久化，fsync 才算落盘
//      （macOS 真落盘需 F_FULLFSYNC，见 C 路线 ph13，本示例用 fsync 演示）；
//   ③ replay 校验顺序：长度够 → magic 对 → 联合长度上限 → CRC 吻合；
//      任一失败即停在残尾（torn tail），报告偏移后可 ftruncate 修复再继续追加；
//   ④ CRC 覆盖 type..payload（跳过 magic 自身）：翻转任意一字节都会被拦截。
// 资源管理：文件描述符用 RAII 封装（fd_file，R.11 无裸 new/delete，规则见 ph13 RAII）。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -Wall -Wextra ex01-wal-append-replay.cpp -o /tmp/ph22-ex01 && /tmp/ph22-ex01
// 验证状态：已验证（零警告、断言全绿、退出码 0）

#include <algorithm>
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

namespace wal {

// —— 常量与类型 ——
constexpr std::uint32_t k_magic = 0x57414C31u;  // ASCII "WAL1"
constexpr std::size_t k_hdr_size = 13;          // magic4 + type1 + klen4 + vlen4
constexpr std::size_t k_crc_size = 4;
constexpr std::uint32_t k_max_kv = 64u * 1024u; // 单条 key+value 联合上限（防恶意长度前缀）

enum class type : std::uint8_t { k_put = 1, k_del = 2 };

struct record {
    type op;
    std::string key;
    std::string value;  // k_del 时为空（tombstone）
    std::uint64_t offset;  // 该记录在文件中的起始偏移（replay 报告残尾用）
};

// —— CRC32（IEEE 802.3，表驱动；教学实现，逐字节查表）——
static const std::array<std::uint32_t, 256> k_crc_table = [] {
    std::array<std::uint32_t, 256> t{};
    for (std::uint32_t i = 0; i < 256; ++i) {
        std::uint32_t c = i;
        for (int k = 0; k < 8; ++k) {
            c = (c & 1u) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
        }
        t[i] = c;
    }
    return t;
}();

std::uint32_t crc32(const void* data, std::size_t n) {
    std::uint32_t c = 0xFFFFFFFFu;
    const auto* p = static_cast<const std::uint8_t*>(data);
    for (std::size_t i = 0; i < n; ++i) {
        c = k_crc_table[(c ^ p[i]) & 0xFFu] ^ (c >> 8);
    }
    return c ^ 0xFFFFFFFFu;
}

// —— 大端写 / 读（跨语言、跨平台一致的线上格式纪律）——
void put_u32be(std::uint8_t* buf, std::uint32_t v) {
    buf[0] = static_cast<std::uint8_t>((v >> 24) & 0xFFu);
    buf[1] = static_cast<std::uint8_t>((v >> 16) & 0xFFu);
    buf[2] = static_cast<std::uint8_t>((v >> 8) & 0xFFu);
    buf[3] = static_cast<std::uint8_t>(v & 0xFFu);
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

// —— RAII 文件描述符（R.1：资源生命周期绑定对象生命周期）——
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

// 单文件开 fd（O_APPEND 写 / 只读两种用途）
fd_file open_append(const std::string& path) {
    const int fd = ::open(path.c_str(), O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0) {
        throw std::runtime_error("open(write) failed: " + path);
    }
    return fd_file{fd};
}

fd_file open_read(const std::string& path) {
    const int fd = ::open(path.c_str(), O_RDONLY);
    if (fd < 0) {
        throw std::runtime_error("open(read) failed: " + path);
    }
    return fd_file{fd};
}

// 短写循环：把 buf 全部写入（EINTR 重试是教科书级纪律，这里一并演示）
void write_full(int fd, const std::uint8_t* buf, std::size_t n) {
    std::size_t done = 0;
    while (done < n) {
        const ssize_t w = ::write(fd, buf + done, n - done);
        if (w < 0) {
            if (errno == EINTR) {
                continue;
            }
            throw std::runtime_error("write failed");
        }
        done += static_cast<std::size_t>(w);
    }
}

// 编码一条记录到字节串（crc 覆盖 type..value 整段，跳 magic）
std::vector<std::uint8_t> encode(const record& r) {
    if (r.key.size() > k_max_kv || r.value.size() > k_max_kv ||
        r.key.size() + r.value.size() > k_max_kv) {
        throw std::runtime_error("record too large");
    }
    const std::size_t total = k_hdr_size + r.key.size() + r.value.size();
    std::vector<std::uint8_t> buf(total + k_crc_size);
    put_u32be(buf.data(), k_magic);
    buf[4] = static_cast<std::uint8_t>(r.op);
    put_u32be(buf.data() + 5, static_cast<std::uint32_t>(r.key.size()));
    put_u32be(buf.data() + 9, static_cast<std::uint32_t>(r.value.size()));
    if (!r.key.empty()) {
        std::copy(r.key.begin(), r.key.end(), buf.begin() + static_cast<std::ptrdiff_t>(k_hdr_size));
    }
    if (!r.value.empty()) {
        std::copy(r.value.begin(), r.value.end(),
                  buf.begin() + static_cast<std::ptrdiff_t>(k_hdr_size + r.key.size()));
    }
    const std::uint32_t crc = crc32(buf.data() + 4, total - 4);
    put_u32be(buf.data() + total, crc);
    return buf;
}

// —— WalLog：append / sync / replay / repair ——
class wal_log {
public:
    explicit wal_log(std::string path) : path_{std::move(path)} {}

    // 追加一条记录并立即 fsync（工程里按事务/批频次调用 sync，见 4.3 group commit）
    void append_sync(const record& r) {
        append(r);
        sync();
    }

    void append(const record& r) {
        auto f = open_append(path_);
        const auto bytes = encode(r);
        write_full(f.get(), bytes.data(), bytes.size());
    }

    void sync() {
        auto f = open_append(path_);
        if (::fsync(f.get()) != 0) {
            throw std::runtime_error("fsync failed");
        }
    }

    // 截断到 keep_bytes（残尾修复）；文件变短即丢弃损坏的尾部
    void truncate_to(std::uint64_t keep_bytes) {
        auto f = open_append(path_);
        if (::ftruncate(f.get(), static_cast<off_t>(keep_bytes)) != 0) {
            throw std::runtime_error("ftruncate failed");
        }
    }

    // replay：返回全部完整记录；若结尾有残尾/损坏，置 torn_at 为其起始偏移并停止
    std::vector<record> replay(std::optional<std::uint64_t>* torn_at) const {
        torn_at->reset();
        auto f = open_read(path_);
        const int fd = f.get();
        std::vector<record> out;
        std::vector<std::uint8_t> hdr(k_hdr_size);
        std::uint64_t pos = 0;
        while (true) {
            // 1. 长度够？
            if (!read_exact(fd, hdr.data(), hdr.size())) {
                if (pos == file_size(fd)) {
                    break;  // 干净 EOF
                }
                *torn_at = pos;  // 残余字节不足一个头
                break;
            }
            if (get_u32be(hdr.data()) != k_magic) {  // 2. magic 对？
                *torn_at = pos;
                break;
            }
            const std::uint32_t klen = get_u32be(hdr.data() + 5);
            const std::uint32_t vlen = get_u32be(hdr.data() + 9);
            // 3. 联合长度上限（各自 ≤ 上限 AND 合计 ≤ 上限，防 payload 越界）
            if (klen > k_max_kv || vlen > k_max_kv || klen + vlen > k_max_kv) {
                *torn_at = pos;
                break;
            }
            std::vector<std::uint8_t> body(static_cast<std::size_t>(klen) + vlen);
            std::array<std::uint8_t, k_crc_size> tail{};
            if (!read_exact(fd, body.data(), body.size()) ||
                !read_exact(fd, tail.data(), tail.size())) {
                *torn_at = pos;  // payload/crc 不完整：残尾
                break;
            }
            const std::uint32_t expect = get_u32be(tail.data());
            // 4. CRC 吻合？(crc 覆盖 magic 之后整段：type+klen+vlen+key+value，与 encode 一致)
            std::vector<std::uint8_t> check;
            check.reserve((k_hdr_size - 4) + body.size());
            check.insert(check.end(), hdr.begin() + 4, hdr.end());  // type+klen+vlen
            check.insert(check.end(), body.begin(), body.end());    // key+value
            if (crc32(check.data(), check.size()) != expect) {  // CRC 不吻合 → 损坏/残写
                *torn_at = pos;
                break;
            }
            record r;
            r.op = static_cast<type>(hdr[4]);
            r.key.assign(reinterpret_cast<const char*>(body.data()), klen);
            r.value.assign(reinterpret_cast<const char*>(body.data() + klen), vlen);
            r.offset = pos;
            out.push_back(std::move(r));
            pos += k_hdr_size + klen + vlen + k_crc_size;
        }
        return out;
    }

private:
    std::string path_;

    // 读到 n 字节为止；不够返回 false（不清除已读部分——残尾按头校验处理即可）
    static bool read_exact(int fd, std::uint8_t* buf, std::size_t n) {
        std::size_t done = 0;
        while (done < n) {
            const ssize_t r = ::read(fd, buf + done, n - done);
            if (r == 0) {
                return false;
            }
            if (r < 0) {
                if (errno == EINTR) {
                    continue;
                }
                throw std::runtime_error("read failed");
            }
            done += static_cast<std::size_t>(r);
        }
        return true;
    }

    static std::uint64_t file_size(int fd) {
        const off_t sz = ::lseek(fd, 0, SEEK_END);
        if (sz < 0) {
            throw std::runtime_error("lseek failed");
        }
        return static_cast<std::uint64_t>(sz);
    }
};

}  // namespace wal

// —— 测试框架：CHECK 宏 + 全局失败计数 ——
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

static const char* op_name(wal::type t) {
    return t == wal::type::k_put ? "PUT" : "DEL";
}

static void print_record(const wal::record& r) {
    std::cout << "  [" << r.offset << "] " << op_name(r.op) << " key=\"" << r.key << "\"";
    if (r.op == wal::type::k_put) {
        std::cout << " value=\"" << r.value << "\"";
    }
    std::cout << '\n';
}

int main() {
    const std::string path = "/tmp/ph22-ex01.wal";
    ::unlink(path.c_str());

    // —— 场景 1：追加 3 条（2 PUT + 1 DEL）并 fsync，replay 原样恢复 ——
    {
        wal::wal_log log{path};
        log.append_sync({wal::type::k_put, "name", "tenet", 0});
        log.append_sync({wal::type::k_put, "lang", "cpp", 0});
        log.append_sync({wal::type::k_del, "oldkey", "", 0});
    }
    std::cout << "[1] 追加 3 条后 replay:\n";
    std::optional<std::uint64_t> torn;
    auto recs = wal::wal_log{path}.replay(&torn);
    for (const auto& r : recs) {
        print_record(r);
    }
    CHECK(!torn.has_value());
    CHECK(recs.size() == 3);
    if (recs.size() == 3) {
        CHECK(recs[0].op == wal::type::k_put && recs[0].key == "name" && recs[0].value == "tenet");
        CHECK(recs[1].op == wal::type::k_put && recs[1].key == "lang" && recs[1].value == "cpp");
        CHECK(recs[2].op == wal::type::k_del && recs[2].key == "oldkey");
    }

    // —— 场景 2：尾部追加 6 字节残尾（模拟崩溃只写了一半）→ replay 停在残尾 ——
    {
        auto f = wal::open_append(path);
        const std::uint8_t garbage[6] = {0x57, 0x41, 0x4c, 0x31, 0x01, 0x00};  // 头都凑不满
        wal::write_full(f.get(), garbage, sizeof(garbage));
    }
    recs = wal::wal_log{path}.replay(&torn);
    std::cout << "[2] 塞入 6 字节残尾后 replay:\n";
    for (const auto& r : recs) {
        print_record(r);
    }
    CHECK(torn.has_value());
    CHECK(recs.size() == 3);
    const std::uint64_t clean_end = torn.value();
    std::cout << "    残尾偏移 = " << clean_end << '\n';

    // ftruncate 修复后回到干净状态，还能继续追加
    wal::wal_log{path}.truncate_to(clean_end);
    recs = wal::wal_log{path}.replay(&torn);
    std::cout << "    ftruncate 修复后 replay: 记录 " << recs.size() << " 条, torn="
              << (torn.has_value() ? "是" : "否") << '\n';
    CHECK(!torn.has_value() && recs.size() == 3);
    {
        wal::wal_log{path}.append_sync({wal::type::k_put, "after", "repair", 0});
    }
    recs = wal::wal_log{path}.replay(&torn);
    CHECK(!torn.has_value() && recs.size() == 4 && recs[3].key == "after");
    ::unlink(path.c_str());

    // —— 场景 3：翻转变更中间一字节 → CRC 拦截，定位到该条记录的起始偏移 ——
    {
        const std::string p2 = "/tmp/ph22-ex01-corrupt.wal";
        ::unlink(p2.c_str());
        wal::wal_log log{p2};
        log.append_sync({wal::type::k_put, "aaa", "111", 0});
        log.append_sync({wal::type::k_put, "bbb", "222", 0});
        // 手工以 O_RDWR 打开（pread 读回 + pwrite 翻转），把第二条 payload 的值首字节翻转
        const int raw_fd = ::open(p2.c_str(), O_RDWR);
        CHECK(raw_fd >= 0);
        wal::fd_file f{raw_fd};
        const std::uint64_t second_off = wal::k_hdr_size + 3 + 3 + wal::k_crc_size;  // 第一条记录 26 字节
        const off_t target = static_cast<off_t>(second_off + wal::k_hdr_size + 3);    // 第二条 value 首字节
        std::uint8_t one = 0;
        CHECK(::pread(f.get(), &one, 1, target) == 1);
        one = static_cast<std::uint8_t>(one ^ 0xFFu);
        CHECK(::pwrite(f.get(), &one, 1, target) == 1);
        auto recs2 = wal::wal_log{p2}.replay(&torn);
        std::cout << "[3] 翻转 payload 一字节后 replay: 记录 " << recs2.size()
                  << " 条, torn 偏移 = " << (torn.has_value() ? torn.value() : 0)
                  << " (期望 = 第二条起始 " << second_off << ")\n";
        CHECK(recs2.size() == 1);
        CHECK(torn.has_value());
        CHECK(torn.value() == second_off);
        ::unlink(p2.c_str());
    }

    std::cout << "checks: " << g_checks << ", failed: " << g_failed << '\n';
    if (g_failed == 0) {
        std::cout << "ph22-ex01 OK\n";
        return 0;
    }
    return 1;
}
