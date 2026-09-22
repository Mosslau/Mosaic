// wal.h —— Mini LSM KV：WAL（Write-Ahead Log）组件（header-only）
// 对应 ph22 主文档 3.1/3.2。承载 Mini LSM 的写路径：put/del 先落日志再进 MemTable；
// 崩溃后 open 时 replay 重建内存态（残尾 ftruncate 修复）；flush 后日志作废重建。
// 与 examples/ex01、exercises/sol-01 同款 record 纪律，这里做成独立小库：
//   record = [magic u32 "WAL1"][type u8][klen u32][vlen u32][key][value][crc32 u32]
//   多字节大端；CRC 覆盖 magic 之后的整段；追加用 O_APPEND + 短写循环。
// 资源管理：RAII fd（R.1）。无裸 new/delete（R.11）。
#ifndef PH22_PROJECT_WAL_H
#define PH22_PROJECT_WAL_H

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace minilsm::wal {

enum class op_type : std::uint8_t { k_put = 1, k_del = 2 };

struct op {
    op_type type;
    std::string key;
    std::string value;
};

constexpr std::uint32_t k_magic = 0x57414C31u;  // "WAL1"
constexpr std::size_t k_hdr = 13;               // magic4 + type1 + klen4 + vlen4
constexpr std::uint32_t k_max_kv = 64u * 1024u;

// —— CRC32（IEEE，表驱动）——
namespace detail {

inline const std::array<std::uint32_t, 256>& crc_table() {
    static const std::array<std::uint32_t, 256> table = [] {
        std::array<std::uint32_t, 256> t{};
        for (std::uint32_t i = 0; i < 256; ++i) {
            std::uint32_t c = i;
            for (int b = 0; b < 8; ++b) {
                c = (c & 1u) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
            }
            t[i] = c;
        }
        return t;
    }();
    return table;
}

inline std::uint32_t crc32(const void* data, std::size_t n) {
    std::uint32_t c = 0xFFFFFFFFu;
    const auto* p = static_cast<const std::uint8_t*>(data);
    for (std::size_t i = 0; i < n; ++i) {
        c = crc_table()[(c ^ p[i]) & 0xFFu] ^ (c >> 8);
    }
    return c ^ 0xFFFFFFFFu;
}

inline void put_u32(std::uint8_t* b, std::uint32_t v) {
    b[0] = static_cast<std::uint8_t>((v >> 24) & 0xFFu);
    b[1] = static_cast<std::uint8_t>((v >> 16) & 0xFFu);
    b[2] = static_cast<std::uint8_t>((v >> 8) & 0xFFu);
    b[3] = static_cast<std::uint8_t>(v & 0xFFu);
}

inline std::uint32_t get_u32(const std::uint8_t* b) {
    return (static_cast<std::uint32_t>(b[0]) << 24) | (static_cast<std::uint32_t>(b[1]) << 16) |
           (static_cast<std::uint32_t>(b[2]) << 8) | static_cast<std::uint32_t>(b[3]);
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

inline fd_file open_append(const std::string& path) {
    const int fd = ::open(path.c_str(), O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0) {
        throw std::runtime_error("wal open(append) failed: " + path);
    }
    return fd_file{fd};
}

inline fd_file open_read(const std::string& path) {
    const int fd = ::open(path.c_str(), O_RDONLY);
    if (fd < 0) {
        throw std::runtime_error("wal open(read) failed: " + path);
    }
    return fd_file{fd};
}

inline std::uint64_t file_size(int fd) {
    const off_t s = ::lseek(fd, 0, SEEK_END);
    if (s < 0) {
        throw std::runtime_error("lseek failed");
    }
    return static_cast<std::uint64_t>(s);
}

}  // namespace detail

// —— 日志 ——
class log {
public:
    explicit log(std::string path) : path_{std::move(path)} {}

    // 追加并落盘（单条同步；批量路径由上层决定调用频率）
    void append_sync(op_type type, const std::string& key, const std::string& value) {
        if (key.size() + value.size() > k_max_kv) {
            throw std::runtime_error("wal op too large");
        }
        auto bytes = encode(type, key, value);
        auto f = detail::open_append(path_);
        write_all(f.get(), bytes);
        if (::fsync(f.get()) != 0) {
            throw std::runtime_error("fsync failed");
        }
    }

    // replay：返回全部完整 op；残尾则报告偏移（供 repair 截断）。损坏中途一律停。
    // 文件不存在（首次使用前）视为空日志。
    std::vector<op> replay(std::optional<std::uint64_t>* torn) const {
        torn->reset();
        const int raw_fd = ::open(path_.c_str(), O_RDONLY);
        if (raw_fd < 0) {
            if (errno == ENOENT) {
                return {};
            }
            throw std::runtime_error("wal open(read) failed: " + path_);
        }
        auto f = detail::fd_file{raw_fd};
        const int fd = f.get();
        std::vector<op> out;
        std::vector<std::uint8_t> hdr(k_hdr);
        std::uint64_t pos = 0;
        const std::uint64_t total = detail::file_size(fd);  // lseek(END) 会移动读偏移
        if (::lseek(fd, 0, SEEK_SET) < 0) {                 // ★ 必须把偏移拨回文件头
            throw std::runtime_error("lseek back failed");
        }
        while (pos + k_hdr <= total) {
            if (!read_exact(fd, hdr.data(), k_hdr)) {
                *torn = pos;
                return out;
            }
            if (detail::get_u32(hdr.data()) != k_magic || hdr[4] > 2u) {
                *torn = pos;
                return out;
            }
            const std::uint32_t klen = detail::get_u32(hdr.data() + 5);
            const std::uint32_t vlen = detail::get_u32(hdr.data() + 9);
            if (klen > k_max_kv || vlen > k_max_kv || klen + vlen > k_max_kv) {
                *torn = pos;
                return out;
            }
            const std::size_t body_len = static_cast<std::size_t>(klen) + vlen;
            if (pos + k_hdr + body_len + 4 > total) {  // 不足一条完整记录
                *torn = pos;
                return out;
            }
            std::vector<std::uint8_t> body(body_len);
            std::array<std::uint8_t, 4> tail{};
            if (!read_exact(fd, body.data(), body_len) || !read_exact(fd, tail.data(), 4)) {
                *torn = pos;
                return out;
            }
            // 校验范围 = magic 之后的整段（type..value），与编码端一致
            std::vector<std::uint8_t> check;
            check.reserve((k_hdr - 4) + body_len);
            check.insert(check.end(), hdr.begin() + 4, hdr.end());
            check.insert(check.end(), body.begin(), body.end());
            if (detail::crc32(check.data(), check.size()) != detail::get_u32(tail.data())) {
                *torn = pos;
                return out;
            }
            op o;
            o.type = static_cast<op_type>(hdr[4]);
            o.key.assign(reinterpret_cast<const char*>(body.data()), klen);
            o.value.assign(reinterpret_cast<const char*>(body.data() + klen), vlen);
            out.push_back(std::move(o));
            pos += k_hdr + body_len + 4;
        }
        if (pos < total) {  // 有尾巴但不够一个头
            *torn = pos;
        }
        return out;
    }

    // flush 后作废旧日志：直接删除（下次 open 自动重建空日志）
    void reset() { ::unlink(path_.c_str()); }

    // 残尾修复：截断到 keep_bytes（replay 报告的 torn 偏移）
    void truncate_to(std::uint64_t keep_bytes) {
        auto f = detail::open_append(path_);
        if (::ftruncate(f.get(), static_cast<off_t>(keep_bytes)) != 0) {
            throw std::runtime_error("ftruncate failed");
        }
    }

    std::string path() const { return path_; }

private:
    std::string path_;

    static std::vector<std::uint8_t> encode(op_type type, const std::string& key,
                                            const std::string& value) {
        std::vector<std::uint8_t> b(k_hdr + key.size() + value.size() + 4);
        detail::put_u32(b.data(), k_magic);
        b[4] = static_cast<std::uint8_t>(type);
        detail::put_u32(b.data() + 5, static_cast<std::uint32_t>(key.size()));
        detail::put_u32(b.data() + 9, static_cast<std::uint32_t>(value.size()));
        if (!key.empty()) {
            std::copy(key.begin(), key.end(), b.begin() + static_cast<std::ptrdiff_t>(k_hdr));
        }
        if (!value.empty()) {
            std::copy(value.begin(), value.end(),
                      b.begin() + static_cast<std::ptrdiff_t>(k_hdr + key.size()));
        }
        const std::uint32_t c =
            detail::crc32(b.data() + 4, k_hdr - 4 + key.size() + value.size());
        detail::put_u32(b.data() + (b.size() - 4), c);
        return b;
    }

    static void write_all(int fd, const std::vector<std::uint8_t>& b) {
        std::size_t done = 0;
        while (done < b.size()) {
            const ssize_t w = ::write(fd, b.data() + done, b.size() - done);
            if (w < 0) {
                if (errno == EINTR) {
                    continue;
                }
                throw std::runtime_error("wal write failed");
            }
            done += static_cast<std::size_t>(w);
        }
    }

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
                throw std::runtime_error("wal read failed");
            }
            done += static_cast<std::size_t>(r);
        }
        return true;
    }
};

}  // namespace minilsm::wal

#endif  // PH22_PROJECT_WAL_H
