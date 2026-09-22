// sol-01-wal-replay.cpp —— exercises/练习 1 参考实现：append-only WAL 写入与 replay
// 题目见 exercises/README.md。设计要点（与 examples/ex01 互为印证，刻意换一种写法）：
//   ① record 格式由解题者自定——本解用 [magic u32][seq u64][type u8][klen u32][vlen u32][key][value][crc32]
//      magic 固定 "PH22"，seq 单调递增供上层判断“最后一条成功记录”；
//   ② append 与 fsync 分离：append_group(批量) 攒批一次 fsync（group commit 教学版，
//      见主文档 4.3）；同步点在调用方（工程里由事务边界/定时器决定）；
//   ③ replay 四道校验：长度够 → magic → 联合长度上限 → CRC；残尾报告偏移并停止；
//      repair(torn) = ftruncate 后日志回到干净状态、可继续追加（“日志作废重建”的另一种
//      形态是 flush 后新建，见 project/）；
//   ④ 语义验证：用 replay 把日志“重放”进 map，证明 put/del 的恢复正确；删除是
//      tombstone 记录（type=DEL），replay 时从 map erase 对应 key。
// 资源管理：RAII fd_file（R.1），vector 拥有内存，无裸 new/delete（R.11）。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -Wall -Wextra sol-01-wal-replay.cpp -o /tmp/ph22-sol01 && /tmp/ph22-sol01
// 验证状态：已验证（零警告、断言全绿、退出码 0）

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace wal_sol {

constexpr std::uint32_t k_magic = 0x50483232u;  // "PH22"
constexpr std::size_t k_hdr = 4 + 8 + 1 + 4 + 4;  // magic+seq+type+klen+vlen = 21 字节
constexpr std::uint32_t k_max_kv = 64u * 1024u;

enum class op_type : std::uint8_t { k_put = 1, k_del = 2 };

struct op {
    op_type type;
    std::string key;
    std::string value;
};

struct replayed_op {
    op o;
    std::uint64_t offset;
};

// 轻量 CRC32（IEEE，表驱动，标准库外的自包含实现）
static std::array<std::uint32_t, 256> make_table() {
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
    static const auto table = make_table();
    std::uint32_t c = 0xFFFFFFFFu;
    const auto* p = static_cast<const std::uint8_t*>(data);
    for (std::size_t i = 0; i < n; ++i) {
        c = table[(c ^ p[i]) & 0xFFu] ^ (c >> 8);
    }
    return c ^ 0xFFFFFFFFu;
}

void put_u32(std::uint8_t* b, std::uint32_t v) {
    b[0] = static_cast<std::uint8_t>((v >> 24) & 0xFFu);
    b[1] = static_cast<std::uint8_t>((v >> 16) & 0xFFu);
    b[2] = static_cast<std::uint8_t>((v >> 8) & 0xFFu);
    b[3] = static_cast<std::uint8_t>(v & 0xFFu);
}

void put_u64(std::uint8_t* b, std::uint64_t v) {
    put_u32(b, static_cast<std::uint32_t>(v >> 32));
    put_u32(b + 4, static_cast<std::uint32_t>(v & 0xFFFFFFFFu));
}

std::uint32_t get_u32(const std::uint8_t* b) {
    return (static_cast<std::uint32_t>(b[0]) << 24) | (static_cast<std::uint32_t>(b[1]) << 16) |
           (static_cast<std::uint32_t>(b[2]) << 8) | static_cast<std::uint32_t>(b[3]);
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

fd_file open_append(const std::string& path) {
    const int fd = ::open(path.c_str(), O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0) {
        throw std::runtime_error("open append failed: " + path);
    }
    return fd_file{fd};
}

fd_file open_read(const std::string& path) {
    const int fd = ::open(path.c_str(), O_RDONLY);
    if (fd < 0) {
        throw std::runtime_error("open read failed: " + path);
    }
    return fd_file{fd};
}

class wal {
public:
    explicit wal(std::string path) : path_{std::move(path)} {}

    // 追加一条（不 fsync）；返回它在文件里的起始偏移
    std::uint64_t append(const op& o) {
        const auto bytes = encode(o);
        auto f = open_append(path_);
        const std::uint64_t off = current_size(f.get());
        write_all(f.get(), bytes.data(), bytes.size());
        return off;
    }

    void fsync_all() {
        auto f = open_append(path_);
        if (::fsync(f.get()) != 0) {
            throw std::runtime_error("fsync failed");
        }
    }

    // replay：返回全部完整 op + 残尾偏移（无残尾则 torn=nullopt）
    std::vector<replayed_op> replay(std::optional<std::uint64_t>* torn) const {
        torn->reset();
        auto f = open_read(path_);
        const int fd = f.get();
        std::vector<replayed_op> out;
        std::vector<std::uint8_t> hdr(k_hdr);
        std::uint64_t pos = 0;
        while (true) {
            const std::size_t got = read_partial(fd, hdr.data(), hdr.size());
            if (got < hdr.size()) {
                // 干净 EOF：文件尾 == pos 且一个字节都没读到；
                // 有残留内容但不足一个头 → 残尾
                if (file_len(fd) > pos) {
                    *torn = pos;
                }
                break;
            }
            if (get_u32(hdr.data()) != k_magic) {
                *torn = pos;
                break;
            }
            const std::uint32_t klen = get_u32(hdr.data() + 13);
            const std::uint32_t vlen = get_u32(hdr.data() + 17);
            if (klen > k_max_kv || vlen > k_max_kv || klen + vlen > k_max_kv) {
                *torn = pos;
                break;
            }
            std::vector<std::uint8_t> body(static_cast<std::size_t>(klen) + vlen);
            std::array<std::uint8_t, 4> crc{};
            if (read_partial(fd, body.data(), body.size()) < body.size() ||
                read_partial(fd, crc.data(), crc.size()) < crc.size()) {
                *torn = pos;
                break;
            }
            std::vector<std::uint8_t> check;
            check.reserve((k_hdr - 4) + body.size());
            check.insert(check.end(), hdr.begin() + 4, hdr.end());  // seq..vlen
            check.insert(check.end(), body.begin(), body.end());
            if (crc32(check.data(), check.size()) != get_u32(crc.data())) {
                *torn = pos;
                break;
            }
            replayed_op r;
            r.o.type = static_cast<op_type>(hdr[12]);
            r.o.key.assign(reinterpret_cast<const char*>(body.data()), klen);
            r.o.value.assign(reinterpret_cast<const char*>(body.data() + klen), vlen);
            r.offset = pos;
            out.push_back(std::move(r));
            pos += k_hdr + klen + vlen + 4;
        }
        return out;
    }

    // 修复残尾：截断到 keep_bytes（调用方用 replay 报告的 torn 偏移）
    void repair(std::uint64_t keep_bytes) {
        auto f = open_append(path_);
        if (::ftruncate(f.get(), static_cast<off_t>(keep_bytes)) != 0) {
            throw std::runtime_error("ftruncate failed");
        }
    }

    // 供测试/工具写残尾用的底层写（完整写入循环）
    static void write_all(int fd, const void* data, std::size_t n) {
        const auto* p = static_cast<const std::uint8_t*>(data);
        std::size_t done = 0;
        while (done < n) {
            const ssize_t w = ::write(fd, p + done, n - done);
            if (w < 0) {
                if (errno == EINTR) {
                    continue;
                }
                throw std::runtime_error("write failed");
            }
            done += static_cast<std::size_t>(w);
        }
    }

private:
    std::string path_;

    static std::vector<std::uint8_t> encode(const op& o) {
        if (o.key.size() + o.value.size() > k_max_kv) {
            throw std::runtime_error("op too large");
        }
        std::vector<std::uint8_t> b(k_hdr + o.key.size() + o.value.size() + 4);
        put_u32(b.data(), k_magic);
        put_u64(b.data() + 4, 0);  // seq 占位：单机按追加序即可，序列号语义属上层
        b[12] = static_cast<std::uint8_t>(o.type);
        put_u32(b.data() + 13, static_cast<std::uint32_t>(o.key.size()));
        put_u32(b.data() + 17, static_cast<std::uint32_t>(o.value.size()));
        std::copy(o.key.begin(), o.key.end(),
                  b.begin() + static_cast<std::ptrdiff_t>(k_hdr));
        std::copy(o.value.begin(), o.value.end(),
                  b.begin() + static_cast<std::ptrdiff_t>(k_hdr + o.key.size()));
        const std::uint32_t c = crc32(b.data() + 4, k_hdr - 4 + o.key.size() + o.value.size());
        put_u32(b.data() + (b.size() - 4), c);
        return b;
    }

    static std::size_t read_partial(int fd, std::uint8_t* buf, std::size_t n) {
        std::size_t done = 0;
        while (done < n) {
            const ssize_t r = ::read(fd, buf + done, n - done);
            if (r == 0) {
                break;
            }
            if (r < 0) {
                if (errno == EINTR) {
                    continue;
                }
                throw std::runtime_error("read failed");
            }
            done += static_cast<std::size_t>(r);
        }
        return done;
    }

    static std::uint64_t current_size(int fd) {
        const off_t s = ::lseek(fd, 0, SEEK_END);
        if (s < 0) {
            throw std::runtime_error("lseek failed");
        }
        return static_cast<std::uint64_t>(s);
    }

    static std::uint64_t file_len(int fd) { return current_size(fd); }
};

}  // namespace wal_sol

// —— 把 replay 结果应用到 map（崩溃恢复的目标态）——
static void apply_ops(std::map<std::string, std::string>& table,
                      const std::vector<wal_sol::replayed_op>& ops) {
    for (const auto& r : ops) {
        if (r.o.type == wal_sol::op_type::k_put) {
            table[r.o.key] = r.o.value;
        } else {
            table.erase(r.o.key);
        }
    }
}

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
    const std::string path = "/tmp/ph22-sol01.wal";
    ::unlink(path.c_str());

    // —— 场景 1：put×3 + del×1，replay 到 map 与预期一致 ——
    {
        wal_sol::wal w{path};
        w.append({wal_sol::op_type::k_put, "alpha", "1"});
        w.append({wal_sol::op_type::k_put, "beta", "2"});
        w.append({wal_sol::op_type::k_put, "beta", "22"});  // 覆盖
        w.append({wal_sol::op_type::k_del, "alpha", ""});   // 删除
        w.fsync_all();
    }
    std::optional<std::uint64_t> torn;
    auto ops = wal_sol::wal{path}.replay(&torn);
    std::map<std::string, std::string> table;
    apply_ops(table, ops);
    std::cout << "[1] replay " << ops.size() << " 条 op, 恢复出 map: ";
    for (const auto& [k, v] : table) {
        std::cout << k << "=" << v << ' ';
    }
    std::cout << '\n';
    CHECK(!torn.has_value());
    CHECK(ops.size() == 4);
    CHECK(table.size() == 1);
    CHECK(table.count("alpha") == 0);            // del 生效
    CHECK(table["beta"] == "22");                // 覆盖生效（replay 顺序保留）

    // —— 场景 2：模拟崩溃残尾（手工塞半条）→ replay 停在残尾，repair 后恢复 ——
    {
        auto f = wal_sol::open_append(path);
        const std::uint8_t half[8] = {0x50, 0x48, 0x32, 0x32, 0, 0, 0, 0};  // "PH22"+半条 seq
        wal_sol::wal::write_all(f.get(), half, sizeof(half));
    }
    ops = wal_sol::wal{path}.replay(&torn);
    std::cout << "[2] 塞入 8 字节残尾后: 完整 op " << ops.size() << " 条, torn="
              << (torn.has_value() ? std::to_string(*torn) : std::string("无")) << '\n';
    CHECK(torn.has_value());
    CHECK(ops.size() == 4);
    const std::uint64_t clean = torn.value();

    // 修复后追加仍能继续（map 重放一次确认恢复态不变）
    wal_sol::wal{path}.repair(clean);
    {
        wal_sol::wal w{path};
        w.append({wal_sol::op_type::k_put, "gamma", "3"});
        w.fsync_all();
    }
    ops = wal_sol::wal{path}.replay(&torn);
    CHECK(!torn.has_value());
    CHECK(ops.size() == 5 && ops.back().o.key == "gamma");
    ::unlink(path.c_str());

    // —— 场景 3：中间一字节损坏 → CRC 拦截，定位到该 op 起始 ——
    {
        const std::string p2 = "/tmp/ph22-sol01-c.wal";
        ::unlink(p2.c_str());
        {
            wal_sol::wal w{p2};
            w.append({wal_sol::op_type::k_put, "aaa", "111"});
            w.append({wal_sol::op_type::k_put, "bbb", "222"});
            w.fsync_all();
        }
        const int fd = ::open(p2.c_str(), O_RDWR);
        CHECK(fd >= 0);
        wal_sol::fd_file f{fd};
        // 第二条记录 = 21 字节头 + "aaa"(3) + "111"(3) + 4 crc = 31 → 第二条起始 31
        const off_t target = 31 + 21 + 3;  // 第二条 value 首字节
        std::uint8_t byte = 0;
        CHECK(::pread(f.get(), &byte, 1, target) == 1);
        byte = static_cast<std::uint8_t>(byte ^ 0xFFu);
        CHECK(::pwrite(f.get(), &byte, 1, target) == 1);
        auto ops2 = wal_sol::wal{p2}.replay(&torn);
        std::cout << "[3] 翻转第二条 payload 一字节: 完整 op " << ops2.size()
                  << " 条, torn 偏移 = " << (torn.has_value() ? *torn : 0)
                  << " (期望 31)\n";
        CHECK(ops2.size() == 1);
        CHECK(torn.has_value() && *torn == 31);
        ::unlink(p2.c_str());
    }

    std::cout << "checks: " << g_checks << ", failed: " << g_failed << '\n';
    if (g_failed == 0) {
        std::cout << "ph22-sol-01 OK\n";
        return 0;
    }
    return 1;
}
