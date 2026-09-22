// sol-03-fd-raii.cpp —— 练习 3 参考实现：把 POSIX fd 封装成 RAII 句柄（socketpair 演示）
// 练习 3 要求：unique_fd move-only、析构 close、用 fcntl(F_GETFD) 实测句柄确已关闭、
//   异常路径不泄漏。
//
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致；
// fd 编号 3/4/5/6 每次运行可能不同）：
//   [1] socketpair 建立双向通道
//     open fd=3
//     open fd=4
//   [2] 写端发送、读端接收
//     收到: ping-ph13（9 字节）
//   [3] 移动后旧句柄失效、新句柄接管
//     move：fd=4 易主
//     移动后: b 有效=0  c 有效=1  fd_alive(4)=1
//   [4] 异常路径：写已关闭的对端 → EPIPE 异常，close 仍由析构兜底
//     open fd=5
//     捕获: write 失败
//     无论是否抛异常，x 的 close 都由析构兜底：
//     close(fd=5)（析构自动调用）
//   [5] 作用域结束后 fd 确已关闭（fcntl 实测）
//     open fd=5
//     open fd=6
//     作用域内 fd_alive(5)=1
//     close(fd=6)（析构自动调用）
//     close(fd=5)（析构自动调用）
//     作用域外 fd_alive(5)=0（0=已关闭，errno=EBADF）
//     close(fd=4)（析构自动调用）
//     close(fd=3)（析构自动调用）
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-03-fd-raii.cpp -o /tmp/ph13-sol-03
// 运行：    /tmp/ph13-sol-03
// 验证状态：已验证（两种编译器均零警告；fcntl 实测作用域外 fd 已 EBADF）
#include <cerrno>
#include <csignal>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <stdexcept>
#include <sys/socket.h>
#include <unistd.h>
#include <utility>

// POSIX fd 的 RAII 封装：-1 表示"无句柄"（fd 的合法值从 0 起，不能用 nullptr 语义）
class UniqueFd {
public:
    UniqueFd() = default;
    explicit UniqueFd(int fd) : fd_(fd) {
        if (fd_ >= 0) std::printf("  open fd=%d\n", fd_);
    }
    ~UniqueFd() {
        if (fd_ >= 0) {
            std::printf("  close(fd=%d)（析构自动调用）\n", fd_);
            ::close(fd_);
        }
    }
    UniqueFd(const UniqueFd&) = delete;
    UniqueFd& operator=(const UniqueFd&) = delete;
    UniqueFd(UniqueFd&& o) noexcept : fd_(std::exchange(o.fd_, -1)) {
        if (fd_ >= 0) std::printf("  move：fd=%d 易主\n", fd_);
    }
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
            if (w < 0) throw std::runtime_error("write 失败");
            off += static_cast<std::size_t>(w);
        }
    }
    std::size_t read_some(char* buf, std::size_t cap) const {
        const ssize_t r = ::read(fd_, buf, cap);
        if (r < 0) throw std::runtime_error("read 失败");
        return static_cast<std::size_t>(r);
    }

private:
    int fd_{-1};
};

// 用 fcntl(F_GETFD) 探测 fd 是否还有效：返回 -1 且 errno==EBADF 即已关闭
bool fd_alive(int fd) {
    return ::fcntl(fd, F_GETFD) != -1 || errno != EBADF;
}

int main() {
    std::signal(SIGPIPE, SIG_IGN);   // 写已关闭的对端改为返回 EPIPE，而不是杀死进程
    std::printf("[1] socketpair 建立双向通道\n");
    int sv[2];
    if (::socketpair(AF_UNIX, SOCK_STREAM, 0, sv) != 0) {
        std::fprintf(stderr, "socketpair 失败: %s\n", std::strerror(errno));
        return 1;
    }
    UniqueFd a(sv[0]);
    UniqueFd b(sv[1]);

    std::printf("[2] 写端发送、读端接收\n");
    const char* msg = "ping-ph13";
    a.write_all(msg, std::strlen(msg));
    char buf[32] = {};
    const std::size_t n = b.read_some(buf, sizeof buf - 1);
    std::printf("  收到: %s（%zu 字节）\n", buf, n);

    std::printf("[3] 移动后旧句柄失效、新句柄接管\n");
    const int raw = b.get();
    UniqueFd c = std::move(b);
    std::printf("  移动后: b 有效=%d  c 有效=%d  fd_alive(%d)=%d\n",
                static_cast<int>(static_cast<bool>(b)),
                static_cast<int>(static_cast<bool>(c)),
                raw, static_cast<int>(fd_alive(raw)));

    std::printf("[4] 异常路径：写已关闭的对端 → EPIPE 异常，close 仍由析构兜底\n");
    {
        int sv2[2];
        if (::socketpair(AF_UNIX, SOCK_STREAM, 0, sv2) != 0) return 1;
        UniqueFd x(sv2[0]);
        const int peer = sv2[1];
        ::close(peer);   // 对端直接关闭（非 RAII，模拟对端进程退出）
        try {
            x.write_all("hello", 5);   // 对端已关：SIGPIPE/EPIPE
            std::printf("  （本机未触发 EPIPE，写入了内核缓冲）\n");
        } catch (const std::runtime_error& e) {
            std::printf("  捕获: %s\n", e.what());
        }
        std::printf("  无论是否抛异常，x 的 close 都由析构兜底：\n");
    }

    std::printf("[5] 作用域结束后 fd 确已关闭（fcntl 实测）\n");
    int probe;
    {
        int sv3[2];
        if (::socketpair(AF_UNIX, SOCK_STREAM, 0, sv3) != 0) return 1;
        UniqueFd p(sv3[0]);
        UniqueFd q(sv3[1]);
        probe = p.get();
        std::printf("  作用域内 fd_alive(%d)=%d\n", probe,
                    static_cast<int>(fd_alive(probe)));
        // q 也在此析构
    }
    std::printf("  作用域外 fd_alive(%d)=%d（0=已关闭，errno=EBADF）\n", probe,
                static_cast<int>(fd_alive(probe)));
    return 0;
}
