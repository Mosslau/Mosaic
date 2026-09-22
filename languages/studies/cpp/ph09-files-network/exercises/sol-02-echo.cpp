// sol-02-echo.cpp —— 练习 2 参考实现：TCP echo server（RAII socket + 阻塞收发 + 超时）
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra sol-02-echo.cpp -o sol-02
// 运行：
//   ./sol-02 selftest               —— 自动验证：fork 子进程连本机回环，回显一致
//   ./sol-02 server 9000            —— 手动模式：起服务（另开终端 ./sol-02 client 9000）
// 验证状态：已验证（编译零警告 + selftest 通过）
#include <arpa/inet.h>
#include <cerrno>
#include <csignal>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <unistd.h>

class Socket {                        // RAII：析构自动 close，禁拷贝允移动
public:
    explicit Socket(int fd = -1) : fd_(fd) {}
    ~Socket() { if (fd_ >= 0) ::close(fd_); }
    Socket(const Socket&) = delete;
    Socket& operator=(const Socket&) = delete;
    Socket(Socket&& o) noexcept : fd_(o.fd_) { o.fd_ = -1; }
    int fd() const { return fd_; }
private:
    int fd_;
};

// 读满 n 字节（处理半包）；0=对端关闭，<0=出错/超时
static ssize_t recv_full(int fd, char* buf, size_t n) {
    size_t got = 0;
    while (got < n) {
        ssize_t r = ::recv(fd, buf + got, n - got, 0);
        if (r <= 0) return r;
        got += static_cast<size_t>(r);
    }
    return static_cast<ssize_t>(got);
}

// 写满 n 字节；MSG_NOSIGNAL 防 SIGPIPE 杀进程
static bool send_full(int fd, const char* buf, size_t n) {
    size_t sent = 0;
    while (sent < n) {
        ssize_t w = ::send(fd, buf + sent, n - sent, MSG_NOSIGNAL);
        if (w <= 0) return false;
        sent += static_cast<size_t>(w);
    }
    return true;
}

static Socket make_server(int port) {
    int fd = ::socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) throw std::runtime_error(std::strerror(errno));
    Socket s(fd);
    int opt = 1;
    ::setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(static_cast<uint16_t>(port));
    if (::bind(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0 ||
        ::listen(fd, 16) < 0)
        throw std::runtime_error(std::strerror(errno));
    return s;
}

// 回显一个连接：收多少回多少，5 秒无数据则超时断开
static void echo_connection(int fd) {
    struct timeval tv{5, 0};
    ::setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    char buf[4096];
    for (;;) {
        ssize_t n = ::recv(fd, buf, sizeof(buf), 0);
        if (n <= 0) break;
        if (!send_full(fd, buf, static_cast<size_t>(n))) break;
    }
}

static int run_server(int port) {
    Socket s = make_server(port);
    std::cout << "echo server on " << port << " (Ctrl-C to stop)\n";
    for (;;) {
        Socket conn(::accept(s.fd(), nullptr, nullptr));
        if (conn.fd() < 0) continue;
        echo_connection(conn.fd());
    }
}

static int run_client(int port) {
    Socket c(::socket(AF_INET, SOCK_STREAM, 0));
    if (c.fd() < 0) throw std::runtime_error(std::strerror(errno));
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(static_cast<uint16_t>(port));
    ::inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);
    if (::connect(c.fd(), reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0)
        throw std::runtime_error(std::strerror(errno));
    const char* msg = "hello echo\n";
    if (!send_full(c.fd(), msg, std::strlen(msg))) return 1;
    char buf[128];
    const ssize_t n = recv_full(c.fd(), buf, std::strlen(msg));
    if (n < 0) throw std::runtime_error(std::strerror(errno));
    buf[n] = '\0';
    std::cout << "echo: " << buf << std::flush;
    return std::string(buf) == msg ? 0 : 1;
}

// 自测：fork 子进程当 client，父进程 accept 一次并回显
static int run_selftest() {
    Socket s = make_server(0);
    sockaddr_in addr{};
    socklen_t len = sizeof(addr);
    if (::getsockname(s.fd(), reinterpret_cast<sockaddr*>(&addr), &len) < 0)
        throw std::runtime_error(std::strerror(errno));
    const int port = ntohs(addr.sin_port);
    pid_t pid = ::fork();
    if (pid < 0) throw std::runtime_error("fork failed");
    if (pid == 0) {
        sleep(1);
        try {
            _exit(run_client(port));
        } catch (const std::exception& e) {
            std::cerr << "client error: " << e.what() << '\n';
            _exit(1);
        }
    }
    Socket conn(::accept(s.fd(), nullptr, nullptr));
    if (conn.fd() < 0) { ::kill(pid, SIGKILL); return 1; }
    echo_connection(conn.fd());
    int status = 0;
    ::waitpid(pid, &status, 0);
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "usage: ./sol-02 selftest | server <port> | client <port>\n";
        return 1;
    }
    try {
        const std::string mode = argv[1];
        if (mode == "selftest") return run_selftest();
        if (mode == "server" && argc >= 3) return run_server(std::stoi(argv[2]));
        if (mode == "client" && argc >= 3) return run_client(std::stoi(argv[2]));
        std::cerr << "usage: ./sol-02 selftest | server <port> | client <port>\n";
        return 1;
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << '\n';
        return 1;
    }
}
