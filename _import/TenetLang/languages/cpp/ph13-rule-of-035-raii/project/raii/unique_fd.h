// raii/unique_fd.h —— POSIX fd 的 RAII 封装（move-only）
// 设计要点：-1 表示"无句柄"（fd 合法值从 0 起）；移动 noexcept（E.16）；
// 析构/close 永不抛异常（E.16）。
#ifndef PH13_RAII_UNIQUE_FD_H
#define PH13_RAII_UNIQUE_FD_H

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <unistd.h>
#include <utility>

namespace raii {

class UniqueFd {
public:
    UniqueFd() = default;
    explicit UniqueFd(int fd) : fd_(fd) {}
    ~UniqueFd() {
        if (fd_ >= 0) ::close(fd_);
    }
    UniqueFd(const UniqueFd&) = delete;             // 所有权唯一
    UniqueFd& operator=(const UniqueFd&) = delete;
    UniqueFd(UniqueFd&& o) noexcept : fd_(std::exchange(o.fd_, -1)) {}
    UniqueFd& operator=(UniqueFd&& o) noexcept {
        if (this != &o) {
            if (fd_ >= 0) ::close(fd_);
            fd_ = std::exchange(o.fd_, -1);
        }
        return *this;
    }

    int get() const { return fd_; }
    explicit operator bool() const { return fd_ >= 0; }
    int release() noexcept { return std::exchange(fd_, -1); }   // 放弃所有权

    void write_all(const char* data, std::size_t n) const {
        std::size_t off = 0;
        while (off < n) {
            const ssize_t w = ::write(fd_, data + off, n - off);
            if (w < 0) {
                throw std::runtime_error(std::string("write: ") +
                                         std::strerror(errno));
            }
            off += static_cast<std::size_t>(w);
        }
    }
    std::size_t read_some(char* buf, std::size_t cap) const {
        const ssize_t r = ::read(fd_, buf, cap);
        if (r < 0) {
            throw std::runtime_error(std::string("read: ") + std::strerror(errno));
        }
        return static_cast<std::size_t>(r);
    }

private:
    int fd_{-1};
};

}  // namespace raii

#endif  // PH13_RAII_UNIQUE_FD_H
