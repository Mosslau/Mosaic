// sol-03-http.cpp —— 练习 3 参考实现：简单 HTTP server（解析请求行 + 200/404 + Content-Length）
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra sol-03-http.cpp -o sol-03
// 运行：
//   ./sol-03 selftest               —— 自动验证：fork 子进程发 GET / 与 GET /nope
//   ./sol-03 <port>                 —— 手动模式：起服务，curl http://127.0.0.1:<port>/
// 验证状态：已验证（编译零警告 + selftest 通过）
#include <arpa/inet.h>
#include <cerrno>
#include <csignal>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <sys/socket.h>
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

static bool send_full(int fd, const char* buf, size_t n) {
    size_t sent = 0;
    while (sent < n) {
        ssize_t w = ::send(fd, buf + sent, n - sent, MSG_NOSIGNAL);
        if (w <= 0) return false;
        sent += static_cast<size_t>(w);
    }
    return true;
}

// 构造 HTTP 响应：状态行 + Content-Length 头部 + body
static std::string make_response(const std::string& status,
                                 const std::string& body) {
    return "HTTP/1.1 " + status + "\r\n"
           "Content-Type: text/html\r\n"
           "Content-Length: " + std::to_string(body.size()) + "\r\n"
           "Connection: close\r\n\r\n" + body;
}

// 读请求 → 解析请求行 → 按路径回 200 或 404
static void handle_connection(int fd) {
    char buf[4096];
    // 教学简化：为聚焦 HTTP 解析主题，省略 recv 循环与 Content-Length 读取（单次 recv 只够极短请求）
    const ssize_t n = ::recv(fd, buf, sizeof(buf) - 1, 0);
    if (n <= 0) return;
    const std::string req(buf, static_cast<size_t>(n));
    const std::string line = req.substr(0, req.find("\r\n"));   // 请求行
    const size_t sp1 = line.find(' ');                           // 方法结束
    const size_t sp2 = sp1 == std::string::npos
                           ? std::string::npos
                           : line.find(' ', sp1 + 1);            // 路径结束
    if (line.empty() || sp1 == std::string::npos ||
        sp2 == std::string::npos) return;                        // 非法请求
    const std::string path = line.substr(sp1 + 1, sp2 - sp1 - 1);
    std::string status = "404 Not Found";
    std::string body = "<html><body><h1>404 Not Found</h1>"
                       "<p>no such path: " + path + "</p></body></html>\n";
    if (path == "/") {
        status = "200 OK";
        body = "<html><body><h1>hello http</h1>"
               "<p>GET / 200 OK</p></body></html>\n";
    }
    const std::string resp = make_response(status, body);
    send_full(fd, resp.data(), resp.size());
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

static int run_server(int port) {
    Socket s = make_server(port);
    std::cout << "http server on " << port << " (Ctrl-C to stop)\n";
    for (;;) {
        Socket conn(::accept(s.fd(), nullptr, nullptr));
        if (conn.fd() < 0) continue;
        handle_connection(conn.fd());
    }
}

// 自测客户端：连本地端口发 GET，返回状态行
static int http_get(int port, const std::string& path, std::string* status_out) {
    Socket c(::socket(AF_INET, SOCK_STREAM, 0));
    if (c.fd() < 0) throw std::runtime_error(std::strerror(errno));
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(static_cast<uint16_t>(port));
    ::inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);
    if (::connect(c.fd(), reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0)
        throw std::runtime_error(std::strerror(errno));
    const std::string req = "GET " + path + " HTTP/1.1\r\n"
                            "Host: 127.0.0.1\r\nConnection: close\r\n\r\n";
    if (!send_full(c.fd(), req.data(), req.size())) return 1;
    char buf[4096];
    const ssize_t n = ::recv(c.fd(), buf, sizeof(buf) - 1, 0);
    if (n <= 0) return 1;
    buf[n] = '\0';
    const std::string resp(buf, static_cast<size_t>(n));
    *status_out = resp.substr(0, resp.find("\r\n"));
    return 0;
}

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
        std::string s200, s404;
        int rc = 0;
        try {
            if (http_get(port, "/", &s200) != 0) rc = 1;
            if (http_get(port, "/nope", &s404) != 0) rc = 1;
            if (s200 != "HTTP/1.1 200 OK") { std::cerr << "got: " << s200 << '\n'; rc = 1; }
            if (s404 != "HTTP/1.1 404 Not Found") { std::cerr << "got: " << s404 << '\n'; rc = 1; }
            std::cout << "GET / -> " << s200 << "\nGET /nope -> " << s404
                      << std::flush;
        } catch (const std::exception& e) {
            std::cerr << "client error: " << e.what() << '\n';
            rc = 1;
        }
        _exit(rc);
    }
    for (int i = 0; i < 2; ++i) {
        Socket conn(::accept(s.fd(), nullptr, nullptr));
        if (conn.fd() >= 0) handle_connection(conn.fd());
    }
    int status = 0;
    ::waitpid(pid, &status, 0);
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "usage: ./sol-03 selftest | <port>\n";
        return 1;
    }
    try {
        if (std::string(argv[1]) == "selftest") return run_selftest();
        return run_server(std::stoi(argv[1]));
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << '\n';
        return 1;
    }
}
