# C++ 文件、网络与系统编程阶段

> 面向高性能系统、存储引擎方向，本阶段能用 C++ 写真实系统程序——从 fstream 文件读写、配置文件解析，到 socket 网络编程、Linux 系统调用与动态库插件机制，让代码真正"落地到操作系统"。

## 1. 概述

本阶段定位：**能用 C++ 写真实系统程序——用 fstream/std::filesystem 读写文件与目录，用标准库解析 key=value 配置（JSON 解析生态了解即可），用 POSIX socket 实现 TCP/HTTP 通信，用 RAII 封装系统资源（文件、socket、fd），并掌握进程、动态库与插件机制**。学完后能写出带完整错误处理的日志系统、TCP echo server、HTTP server 与文件传输工具，能说清"IO 为什么会失败、配置错误怎么报、粘包怎么解、插件接口为什么必须稳定"。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 文本与二进制文件 | fstream（ifstream/ofstream）、read/write、字节序 |
| 文件系统 | std::filesystem（路径、遍历、复制，C++17） |
| 配置解析 | key=value 解析（标准库实现）、可诊断错误；JSON 生态了解 |
| 网络基础 | socket、bind/listen/accept、connect、recv/send |
| 协议基础 | TCP 字节流与粘包/半包、length-prefix、HTTP 请求/响应 |
| Linux 系统调用 | open/read/write/close、EINTR、errno |
| 进程与线程 | fork/exec/waitpid、与 std::thread 的取舍 |
| 动态库与插件 | dlopen/dlsym、extern "C"、稳定接口与 ABI |

**范围边界**：本阶段承接 ph08 并发阶段——多线程程序要把日志刷盘、socket 收发放进独立线程；这个阶段只涉及文件 IO、文件系统、配置解析、阻塞 socket 网络编程、进程与动态库插件机制，**不涉及构建调试工具链（ph10）、C++ 标准/编译器可移植性（ph11）、对象生命周期、值类别与所有权深入（ph12 对象生命周期、值类别与所有权深入阶段）、ABI 与插件机制深入（ph19，目录待建）和性能优化（ph18，目录待建）** — 那些是后续阶段的内容；epoll/io_uring 异步 IO 与高性能网络框架也不展开——本阶段用阻塞 socket + 超时把协议写对，是异步化的前提，异步化留给 ph18 性能优化阶段与 ph22 存储引擎阶段（目录待建）的 IO 密集场景。

## 2. 来源与演变

文件 IO 是 C++ 最老的能力之一：C++98 把 iostream 家族（源自 AT&T 实验室的 streams 库）纳入标准，`fstream` 在 C stdio 之上提供类型安全的流式读写；但路径操作、目录遍历长期缺席，只能回到 POSIX 或平台 API。转折在 C++17：**`std::filesystem` 正式入标准**（源于 Boost.Filesystem），路径拼接、遍历、复制第一次有了跨平台标准写法。网络与配置的标准化走了另一条路：**POSIX socket（BSD sockets，1983 年）**至今仍是 Linux 系统编程的事实标准，C++ 标准迟迟没有网络库，社区用 **Boost.Asio**（2003 年起）填补跨平台异步 IO 空白；JSON 同样不在标准内，**nlohmann/json**（2013 年起）凭"单头文件 + 现代 C++ 风格"成为事实标准，HTTP 客户端常直接依赖 libcurl。主线是：**标准库管文件与流，系统调用与成熟生态管网络与配置**——网络库（std::net，基于 Asio）未随 C++26（2026 年发布）落地，标准化仍在推进（目标 C++29）。

| 阶段 | 代表 | 贡献 |
|------|------|------|
| 1983 | BSD sockets | socket/bind/listen/accept 成为网络编程事实标准 |
| C++98 | ISO C++98 | iostream/fstream 正式入标准，类型安全的文件流 |
| 2003 | Boost.Asio | 跨平台异步 IO 库，成为 std::net 提案的基础 |
| 2013 | nlohmann/json | 单头文件 JSON 库，C++ JSON 生态事实标准 |
| C++17 | ISO C++17 | std::filesystem 入标准（源自 Boost.Filesystem） |
| C++29 提案 | std::net | 基于 Asio 的 TCP 原语，未入 C++26（2026 发布），标准化推进中 |

本文示例以 **C++20** 为基线（std::filesystem 自 C++17 引入、C++20 下已稳定成熟；socket/系统调用为 POSIX API，不随 C++ 版本变化），验证工具链 Apple clang 21（g++ 兼容），编译选项统一 `-std=c++20 -Wall -Wextra`。文件 IO 与 socket 的接口自定形以来高度稳定——这个阶段的语法是 C++ 中最稳定的部分，示例代码用 C++17 特性也能编译，统一按 C++20 编译是为了与 ph08/ph10 阶段保持一致。

## 3. 语法与参数

### 3.1 fstream 文件读写与错误处理

`std::ifstream` / `std::ofstream` / `std::fstream` 是文件流三件套，RAII 设计——构造即打开、析构自动关闭。**流对象携带错误状态**（goodbit/failbit/badbit/eofbit），打开失败不抛异常而是置 failbit，必须显式检查。

```cpp
// 文件流读写最小演示；LogFile 追加写的完整实现见 examples/ex01-logfs.cpp（已验证：Apple clang 21，-std=c++20 -Wall -Wextra）
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
int main() {
    const std::string path = "/tmp/ph09_demo.txt";
    {   // 写：块作用域让 ofstream 析构落盘后再读
        std::ofstream out(path);                // 构造即打开；失败置 failbit
        if (!out) throw std::runtime_error("open failed: " + path);
        out << "hello filesystem\n" << 42 << "\n";
        if (!out) throw std::runtime_error("write failed");   // 写后必查
    }
    std::ifstream in(path);
    std::string line;
    while (std::getline(in, line))              // 用返回值做循环条件，别用 eof()
        std::cout << "line: " << line << "\n";
    return 0;
}
```

要点：

- **必会概念：IO 必须处理失败**——打开查 `!in`、写入后查 `!out`，否则坏块、磁盘满、权限错误全部静默吞掉
- **坑：用 `eof()` 做循环条件**——读到 EOF 时 failbit 与 eofbit 同时置位，最后一行会重复处理
- **坑：`endl` 会 flush**——高频写日志用 `'\n'`，需要落盘再显式 `flush()`；要"失败即抛"可用 `in.exceptions(std::ios::failbit | std::ios::badbit)`

### 3.2 二进制文件读写

二进制 IO 用 `read(char*, n)` / `write(const char*, n)`，把**内存字节原样搬进文件**，适合序列化紧凑结构、索引文件、WAL 日志。注意结构体存在**内存填充（padding）**，多字节整数有**字节序（endianness）**问题。

```cpp
// Record 二进制读写演示（本片段可直接编译运行）；分块读写与校验的完整实现见 examples/ex05-filexfer.cpp（已验证：Apple clang 21，-std=c++20 -Wall -Wextra）
#include <cstdint>
#include <fstream>
#include <iostream>
#include <vector>
struct Record { int32_t id; double value; };   // 含 padding，布局依赖编译器
int main() {
    const std::string path = "/tmp/ph09_bin.dat";
    {
        std::vector<Record> data{{1, 1.5}, {2, 2.5}, {3, 3.5}};
        std::ofstream out(path, std::ios::binary);  // 内存字节原样落盘
        out.write(reinterpret_cast<const char*>(data.data()),
                  static_cast<std::streamsize>(data.size() * sizeof(Record)));
    }   // 块作用域：析构落盘后再读
    std::ifstream in(path, std::ios::binary);
    in.seekg(0, std::ios::end);
    std::streamsize size = in.tellg();
    in.seekg(0);
    const size_t count = static_cast<size_t>(size) / sizeof(Record);  // 只读完整记录数
    std::vector<Record> loaded(count);
    // 按 count*sizeof(Record) 读：文件尾部的不完整记录直接忽略，避免 read 越过缓冲
    in.read(reinterpret_cast<char*>(loaded.data()),
            static_cast<std::streamsize>(count * sizeof(Record)));
    std::cout << "records=" << loaded.size() << "\n";
    return 0;
}
```

要点：

- **读写必须配对**：写几字节就按同样布局读几字节，布局变了旧文件就读不出来
- **坑：直接落结构体把 padding 与字节序一起写进文件**——跨机器/编译器不兼容；稳定格式应逐字段显式序列化或统一字节序（见 3.5 的 htonl/ntohl）
- **坑：`read` 可能读不满**（EOF 提前）——实际读入字节数用 `in.gcount()` 查询（见 examples/ex05-filexfer.cpp）

### 3.3 std::filesystem：路径、遍历、复制（C++17）

`std::filesystem` 提供跨平台路径与目录操作：路径拼接用 `operator/`、`create_directories` 递归建目录、`directory_iterator` 遍历、`copy`/`remove_all` 复制删除。每个操作都有**抛异常版**和 **`std::error_code` 版**两个重载。

```cpp
// filesystem 最小演示；目录遍历与复制的完整实现见 examples/ex06-fswalk.cpp（已验证：Apple clang 21，-std=c++20 -Wall -Wextra）
#include <filesystem>
#include <fstream>
#include <iostream>
namespace fs = std::filesystem;
int main() {
    fs::path dir = "/tmp/ph09_fs_demo";
    fs::create_directories(dir);                // 递归创建，已存在也不报错
    fs::path file = dir / "hello.txt";          // 拼接路径用 operator/
    { std::ofstream out(file); out << "hi\n"; }
    for (const auto& e : fs::directory_iterator(dir))  // 遍历一层
        std::cout << e.path().filename() << "\n";
    std::error_code ec;                         // error_code 重载：不抛异常
    fs::copy(file, dir / "copy.txt", fs::copy_options::overwrite_existing, ec);
    if (ec) std::cout << ec.message() << "\n";
    fs::remove_all(dir);                        // 递归删除整棵目录树
    return 0;
}
```

要点：

- 默认版本失败**抛 `fs::filesystem_error`**（含路径与系统错误码）；批量扫描用 error_code 版逐个容忍失败继续处理
- `recursive_directory_iterator` 递归遍历目录树；`fs::last_write_time` 拿修改时间，是文件同步工具做差异比对的基础（见 project/ 文件同步工具）
- **坑：路径编码**——Linux 文件名是任意字节序列，`fs::path` 用平台编码（约定 UTF-8），来自用户输入/网络的路径要先校验；**路径拼接永远用 `operator/`，不要手拼字符串**

### 3.4 配置文件解析：key=value（标准库实现）与 JSON 生态

JSON 不在 C++ 标准内，**nlohmann/json** 是事实标准：单头文件、类型安全访问、解析失败抛带字节偏移的 `json::parse_error`。本仓库代码层不引入第三方库（本机可能无法拉包），配置解析的教学以**标准库可实现的 key=value 格式**为准——它演示了配置解析的全部硬性要求：**可诊断错误**——报错必须说清"哪个文件、哪一行、为什么"。

```cpp
// 完整可运行版见 examples/ex04-config.cpp（已验证：Apple clang 21，-std=c++20 -Wall -Wextra）
#include <fstream>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
class ConfigError : public std::runtime_error {   // 错误自带 文件:行号
public:
    ConfigError(const std::string& file, int line, const std::string& msg)
        : std::runtime_error(file + ":" + std::to_string(line) + ": " + msg) {}
};
class Config {
public:
    static Config load(const std::string& path) {
        std::ifstream in(path);
        if (!in) throw ConfigError(path, 0, "cannot open file");
        Config cfg;
        cfg.file_ = path;
        std::string raw;
        int line_no = 0;
        while (std::getline(in, raw)) {
            ++line_no;
            std::string line = trim(raw);
            if (line.empty() || line[0] == '#') continue;      // 空行与注释
            auto eq = line.find('=');
            if (eq == std::string::npos)
                throw ConfigError(path, line_no, "expected key=value, got: " + line);
            const std::string key = trim(line.substr(0, eq));
            cfg.values_[key] = trim(line.substr(eq + 1));
            cfg.lines_[key] = line_no;                        // 记录键定义行号
        }
        return cfg;
    }
    int get_int(const std::string& key, int def) const {
        auto it = values_.find(key);
        if (it == values_.end()) return def;
        try { return std::stoi(it->second); }
        catch (const std::exception&) {
            const auto ln = lines_.find(key);
            throw ConfigError(file_, ln == lines_.end() ? 0 : ln->second,
                              "key '" + key + "' value '" + it->second +
                                  "' is not an int");        // 类型错误同样带 文件:行号
        }
    }
private:
    static std::string trim(const std::string& s) {
        size_t b = s.find_first_not_of(" \t\r\n");
        if (b == std::string::npos) return "";
        size_t e = s.find_last_not_of(" \t\r\n");
        return s.substr(b, e - b + 1);
    }
    std::string file_;                          // 配置文件路径（错误消息用）
    std::map<std::string, int> lines_;          // 键 → 定义行号
    std::map<std::string, std::string> values_;
};
```

要点：

- **必会概念：配置解析要给出可诊断错误**——错误消息统一 `文件:行号: 原因`；JSON 生态中 `json::parse_error::what()` 带字节偏移、`json::type_error` 说明键的类型不对
- **坑：错误信息差**——只报 "parse failed" 等于没报；好错误 = 文件路径 + 位置 + 期望 + 实际值
- **nlohmann/json 用法（生态了解，未在本环境验证——需要第三方头文件，本仓库不引入）**：`json cfg = {{"port", 8080}};` 构造、`cfg.dump(4)` 语义保留的缩进输出、`json::parse(in)` 解析失败抛异常、读配置用 `cfg.value(key, 默认值)` 避免裸 `[]` 插入空值；`nlohmann::ordered_json` 保键的插入顺序（默认 json 底层是 std::map，会按键排序）

### 3.5 socket 编程基础（POSIX socket + RAII 封装）

POSIX socket 用裸 `int fd` 表达连接，**必须用 RAII 类封装**：构造时拿 fd、析构时 `close()`、禁拷贝允移动。核心流程：服务端 `socket → bind → listen → accept`，客户端 `socket → connect`，之后双方 `recv`/`send`（完整流程见 examples/ex02-echo.cpp）。

```cpp
// Socket RAII 封装最小演示；完整 echo 流程见 examples/ex02-echo.cpp（已验证：Apple clang 21，-std=c++20 -Wall -Wextra）
#include <iostream>
#include <sys/socket.h>
#include <unistd.h>
class Socket {                          // RAII 封装：析构自动 close
public:
    explicit Socket(int fd = -1) : fd_(fd) {}
    ~Socket() { if (fd_ >= 0) ::close(fd_); }
    Socket(const Socket&) = delete;              // 禁拷贝、允移动
    Socket& operator=(const Socket&) = delete;
    Socket(Socket&& o) noexcept : fd_(o.fd_) { o.fd_ = -1; }
    int fd() const { return fd_; }
private:
    int fd_;
};
int main() {
    Socket s(::socket(AF_INET, SOCK_STREAM, 0));  // 拿到 fd；离开作用域自动 close
    std::cout << "fd=" << s.fd() << "\n";
    return 0;
}
```

要点：

- **socket 错误都是 `-1` 返回 + `errno`**：用 `std::strerror(errno)` 生成消息；`accept` 返回的每个连接都是新 fd，也要交给 RAII
- **坑：`close` 后 fd 可能被复用**——裸 fd 到处传就是 use-after-close；RAII 让"谁拥有谁关闭"一目了然
- 端口与 IP 用 `htons`/`htonl` 转**网络字节序**（大端）；**坑：SIGPIPE**——向已关闭连接写数据默认杀进程，`send` 加 `MSG_NOSIGNAL`（见 3.6）

**UDP 基础（SOCK_DGRAM，对比 TCP）**

| 维度 | TCP（SOCK_STREAM） | UDP（SOCK_DGRAM） |
|------|-------------------|-------------------|
| 连接 | 面向连接（connect 三次握手） | 无连接（sendto/recvfrom 直发） |
| 边界 | 字节流，需应用层处理粘包 | 报文边界保留（一次 sendto = 一次 recvfrom） |
| 可靠性 | 可靠：重传、有序、拥塞控制 | 不可靠：丢包/乱序不通知 |
| 适用 | 文件传输、HTTP、需要可靠 | 实时音视频、DNS、游戏状态同步 |

UDP 编程更简单（无 listen/accept，直接 `sendto`/`recvfrom`），但**丢包必须自己处理**（序列号 + 超时重传）；本阶段重点掌握 TCP，UDP 作为对比理解「为什么 HTTP/文件传输选 TCP」即可，不展开可靠 UDP 实现。

### 3.6 TCP echo 与粘包处理

TCP 是**字节流**，不保留消息边界：一次 `recv` 可能拿到"半条消息"（半包），也可能一次拿到"多条消息"（粘包）。底层补救是**读满/写满**——循环直到凑够 n 字节；消息边界由**上层协议**负责（length-prefix，见 4.3）。

```cpp
// 完整可运行版见 examples/ex02-echo.cpp 的 recv_full/send_full（已验证）
#include <cstring>
#include <sys/socket.h>
#include <unistd.h>
// 读满 n 字节：处理"半包"——单次 recv 拿不满就继续（0=对端关闭，<0=出错/超时）
ssize_t recv_full(int fd, char* buf, size_t n) {
    size_t got = 0;
    while (got < n) {
        ssize_t r = ::recv(fd, buf + got, n - got, 0);
        if (r <= 0) return r;
        got += static_cast<size_t>(r);
    }
    return static_cast<ssize_t>(got);
}
// 写满 n 字节：处理"只发出一半"；MSG_NOSIGNAL 防 SIGPIPE 杀进程
bool send_full(int fd, const char* buf, size_t n) {
    size_t sent = 0;
    while (sent < n) {
        ssize_t w = ::send(fd, buf + sent, n - sent, MSG_NOSIGNAL);
        if (w <= 0) return false;
        sent += static_cast<size_t>(w);
    }
    return true;
}
```

要点：

- **必会概念：网络协议要处理边界和粘包**——recv/send 的 n 是"最多/尝试"字节数不是"保证"；所有协议代码都要循环处理
- **坑：`recv` 返回 0 表示对端关闭**——不是"没数据"，当错误或继续读都会死循环
- **坑：用 `strlen` 处理二进制数据**——消息里可能含 `'\0'`，长度必须显式携带
- 帧格式三选一：定长 / 分隔符（如换行）/ **长度前缀**（推荐，见 4.3）

### 3.7 HTTP 基础与简单请求

HTTP 是基于 TCP 的文本协议：请求 = 请求行（`METHOD 路径 版本`）+ 头部 + 空行 + 可选 body；响应 = 状态行（`HTTP/1.1 200 OK`）+ 头部 + 空行 + body。手写极简 GET 能彻底搞懂协议，生产代码建议用 **libcurl**。

```cpp
// 已验证（本机外网可用时；Apple clang 21，-std=c++20 -Wall -Wextra）
#include <cstring>
#include <iostream>
#include <netdb.h>
#include <string>
#include <sys/socket.h>
#include <unistd.h>
int main() {
    struct addrinfo hints{};
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    struct addrinfo* res = nullptr;
    if (::getaddrinfo("example.com", "80", &hints, &res) != 0) return 1;  // DNS
    const int fd = ::socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (fd < 0) { ::freeaddrinfo(res); return 1; }        // 出错路径同样要释放 res
    const int ok = ::connect(fd, res->ai_addr, res->ai_addrlen);
    ::freeaddrinfo(res);                                   // 用完即释放
    if (ok < 0) { ::close(fd); return 1; }
    std::string req = "GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n";
    ::send(fd, req.data(), req.size(), 0);
    char buf[4096];
    ssize_t n = ::recv(fd, buf, sizeof(buf) - 1, 0);
    if (n > 0) { buf[n] = '\0'; std::cout << buf; }  // 首行应为 HTTP/1.1 200 OK
    ::close(fd);
    return 0;
}
```

要点：

- **请求行三要素**：方法、路径（含查询串）、版本，行尾 `\r\n`；头部以空行（`\r\n\r\n`）结束
- **响应体长度看 `Content-Length` 头**——要读完整响应必须解析头部、按长度循环 recv（粘包实战）；`Connection: close` 可简化：读到关闭即结束
- **坑：一次 recv 拿不到完整响应**——上面只读一次是教学简化（服务端同样为聚焦解析主题只读一次请求，见 §6 示例 3 代码注释）；**生产用 libcurl**（`-lcurl`）处理重定向、TLS、超时、cookie，手写 HTTP 只用于学习和极简内部协议（server 侧见 examples/ex03-http.cpp）

### 3.8 Linux 系统调用封装（open/read/write RAII）

文件 IO 的另一条路是直接调 POSIX 系统调用 `open/read/write/close`：返回 `ssize_t` 实际字节数、用 `errno` 报错、无流缓冲，适合性能敏感与需要精确控制的场景。**同样必须 RAII 封装**。

```cpp
// 已验证（macOS 的 open/read/write 与 Linux 语义一致；Apple clang 21，-std=c++20 -Wall -Wextra）
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unistd.h>
class PosixFile {                    // open/read/write/close 的 RAII 封装
public:
    explicit PosixFile(const std::string& path, int flags, mode_t mode = 0644)
        : fd_(::open(path.c_str(), flags, mode)) {
        if (fd_ < 0) throw std::runtime_error("open " + path + ": " + std::strerror(errno));
    }
    ~PosixFile() { if (fd_ >= 0) ::close(fd_); }
    PosixFile(const PosixFile&) = delete;
    PosixFile& operator=(const PosixFile&) = delete;
    int fd() const { return fd_; }
    ssize_t read(void* buf, size_t n) {      // EINTR：被信号打断要重试，不是错误
        for (;;) {
            ssize_t r = ::read(fd_, buf, n);
            if (r < 0 && errno == EINTR) continue;
            return r;
        }
    }
private:
    int fd_;
};
```

要点：

- **`open` flags**：`O_RDONLY/O_WRONLY/O_RDWR` 必选其一，`O_CREAT|O_TRUNC|O_APPEND` 按需叠加；带 `O_CREAT` 必须给 mode
- **坑：`read`/`write` 返回"实际字节数"**——小于请求数不算错，必须循环；返回 0 = EOF，-1 = 错误（看 errno）
- **坑：EINTR**——被信号中断的慢系统调用返回 -1/EINTR，正确语义是重试，当错误处理会让程序莫名失败
- fstream vs POSIX：fstream 类型安全、自带缓冲；POSIX 精确可控、无缓冲——日志刷盘、WAL 落盘常两者结合（缓冲 + `fsync` 保持久性）

### 3.9 进程与线程系统编程补充（fork/system/exec 与 std::thread 取舍）

进程与线程是两种并发原语：**进程**（fork/exec）隔离内存、可跑外部程序；**线程**（std::thread，ph08）共享地址空间、切换轻。**取舍**：需要隔离/崩溃不牵连/调用外部工具 → 进程；共享数据高频协作 → 线程。

```cpp
// 已验证（macOS 支持 fork/waitpid，Apple clang 21，-std=c++20 -Wall -Wextra）
#include <cstring>
#include <iostream>
#include <sys/wait.h>
#include <unistd.h>
int main() {
    pid_t pid = ::fork();            // 子进程 = 父进程的复制品（写时复制 COW）
    if (pid < 0) { std::cerr << "fork failed\n"; return 1; }
    if (pid == 0) {                  // 子进程：exec 替换成 ls，只有失败才返回
        ::execlp("/bin/ls", "ls", "-l", nullptr);
        return 127;
    }
    int status = 0;
    ::waitpid(pid, &status, 0);      // 父进程回收子进程，防止僵尸进程
    std::cout << "child exit=" << WEXITSTATUS(status) << "\n";
    return 0;
}
```

要点：

- **fork + exec 两步走**：fork 复制当前进程，exec 族（execlp/execvp）把子进程替换成目标程序；`system(cmd)` 是"fork+exec+waitpid"封装，简单但**不检查中间错误、有注入风险**，生产慎用
- **坑：不 waitpid 会产生僵尸进程**——进程已退出但 PCB 未回收；`waitpid(pid, &status, 0)` 阻塞等待，`WNOHANG` 非阻塞轮询
- **坑：fork 后的多线程程序**——只有调用线程被复制，锁状态可能不一致；多线程进程 fork 后再 exec 才安全
- **std::thread 不能表达"换一个程序"**——执行外部命令、内存隔离、崩溃互不牵连只能用进程；进程间通信（IPC）本阶段掌握 socket 即可（examples/ex02 的 selftest 模式就是 fork + 回环 socket 的组合）

### 3.10 动态库与插件机制入门（dlopen/dlsym）

插件机制 = **运行时加载动态库**：Linux 用 `dlopen/dlsym/dlclose`（glibc 2.34+ 已并入 libc，无需 `-ldl`；macOS 在 libSystem 内，同样无需链接选项），Windows 用 `LoadLibrary/GetProcAddress`。核心纪律：**插件接口必须稳定**——用 `extern "C"` 关掉 C++ 名字修饰（name mangling），用固定签名、固定结构体布局作为插件 ABI。

```cpp
// 已验证（macOS Apple clang 21；插件侧编译：c++ -std=c++20 -shared -fPIC plugin.cpp -o libplugin.so）
#include <dlfcn.h>
#include <iostream>
int main(int argc, char** argv) {
    void* h = ::dlopen(argc > 1 ? argv[1] : "./libplugin.so", RTLD_NOW);
    if (!h) { std::cerr << "dlopen: " << ::dlerror() << "\n"; return 1; }
    using AddFn = int (*)(int, int);
    auto add = reinterpret_cast<AddFn>(::dlsym(h, "plugin_add"));
    if (!add) { std::cerr << "dlsym: " << ::dlerror() << "\n"; return 1; }
    std::cout << "plugin_add(2,3)=" << add(2, 3) << "\n";
    ::dlclose(h);
    return 0;
}
```

要点：

- **必会概念：动态库接口要稳定**——插件协议一旦发布，函数签名、结构体布局、语义都不能变；主程序与插件必须约定同一套接口头文件
- **`extern "C"` 是必须的**：C++ 会把函数名修饰成 `_Z10plugin_addii` 之类符号，不加它 `dlsym("plugin_add")` 找不到
- **坑：函数指针与声明不匹配是 UB**——插件接口变更后旧插件还在，按新签名调用就崩；导出 `plugin_api_version` 整数、加载时检查是标准解法（见 4.4）
- **坑：插件与主程序各持一份运行时（libstdc++）**——跨 .so 边界传 `std::string` 依赖 ABI 兼容，安全做法是接口只传 C 类型（指针 + 长度）

## 4. 底层原理

### 4.1 iostream 缓冲与同步（tie / sync_with_stdio）

iostream 的读写不直接碰系统调用，而是走**内存缓冲（streambuf）**：`cout` 攒满缓冲或遇到 flush 才真正 write，`fstream` 同理。三个影响行为的开关：

| 机制 | 默认 | 作用 |
|------|------|------|
| `cin.tie(&cout)` | cin 绑定 cout | 输入前自动 flush cout，交互场景先显示提示语 |
| `sync_with_stdio(true)` | true | 允许与 C stdio（printf/scanf）混用，代价是每次操作同步、性能大降 |
| `std::endl` | — | 输出换行 + flush；高频输出用它性能差一个数量级 |

性能关键：**`std::ios::sync_with_stdio(false)` + 用 `'\n'` 代替 `endl`** 让 iostream 吞吐接近 C stdio。flush 语义要分清：`flush()` 把用户缓冲交给内核（page cache），**不等于落盘**——要保证断电不丢数据必须 `fsync`（可仿照 3.8 的 PosixFile 自行封装 `fsync(fd)` 调用）。此外流状态（failbit/badbit）是**粘滞的**：一旦置位后续操作全部短路，必须 `clear()` 才恢复——"IO 失败必须显式处理"的底层原因：错误会静默扩散到所有后续读写。

### 4.2 socket 的阻塞与超时（SO_RCVTIMEO、非阻塞 + poll）

默认 socket 是**阻塞模式**：`recv` 没数据就一直睡，`send` 缓冲满也一直睡。阻塞模型代码简单，但**必须配超时**，否则一个不发的对端就能永久挂死你的线程：

| 方案 | 实现 | 超时行为 | 适用 |
|------|------|---------|------|
| 阻塞 + SO_RCVTIMEO | `setsockopt(SOL_SOCKET, SO_RCVTIMEO, timeval)` | 超时返回 -1，errno=EAGAIN/EWOULDBLOCK | 本阶段首选：简单直观 |
| 非阻塞 + poll | `fcntl(O_NONBLOCK)` + `poll(fds, n, timeout_ms)` | poll 返回就绪事件，再 recv 不阻塞 | 单线程多连接的基础 |
| 非阻塞 + epoll | epoll 事件驱动 | 内核通知就绪 | 高并发服务器（ph18 性能优化阶段与 ph22 存储引擎阶段触及） |

设置超时：`struct timeval tv{5, 0}; setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));`（`SO_SNDTIMEO` 同理管发送）；超时后 `recv` 返回 -1 且 `errno == EAGAIN || errno == EWOULDBLOCK`。

要点：

- **超时不是"可选优化"而是"必须"**——存储引擎里任何一次网络等待都要有上限，否则单点故障拖垮整个服务
- **坑：`EAGAIN` 与 `EWOULDBLOCK` 是同一个值（Linux）**——两个都要查；其他 errno 才是真错误
- 阻塞 + 多线程（thread-per-connection）代码最直白，几十上百连接没问题；非阻塞 + poll 是事件驱动的基础；`send` 超时用 `SO_SNDTIMEO`

### 4.3 TCP 粘包成因与 length-prefix 解决

**TCP 是字节流，不是消息流**：内核只保证"字节按序到达"，不保证"一次 write 对应一次 read"。粘包两个来源：**发送侧**——Nagle 算法把多个小包合并成一个 TCP 段；**接收侧**——内核缓冲区攒了多条消息，一次 recv 全拿出来。半包同理。**这是协议层问题，TCP 本身无解**，必须由应用层定义消息边界：

| 方案 | 做法 | 优缺点 |
|------|------|--------|
| 定长消息 | 每条固定 N 字节 | 简单，但浪费空间、不支持变长 |
| 分隔符 | 消息以 `\n` 等结尾 | 简单，但内容里不能出现分隔符（需转义） |
| **length-prefix** | 头 4 字节 = 载荷长度，后跟载荷 | **推荐**：变长、无转义、解析确定 |

length-prefix 的收包状态机：**读满 4 字节头 → 解析长度 L → 读满 L 字节载荷 → 拼成一条消息 → 回到读头**，多余的字节（下一条消息的头）留在缓冲区——这正是"粘包被正确切分"的样子：

```text
|  4 字节长度 (uint32, 网络字节序)  |  L 字节载荷  |  4 字节长度  |  ...  |
└───────── 消息 1 ─────────┘
```

实现要点：长度用 `ntohl` 转主机字节序（写端 `htonl`）；**长度必须校验**（如上限 16MB），否则恶意/损坏的头部会让 recv_full 尝试读巨量字节；练习 2 的升级方向就是把"读到 \n 即一条消息"改成 length-prefix。

### 4.4 动态库符号解析与 ABI 稳定性

`dlopen` 的底层是 **ELF 动态链接**：可执行文件与 .so 各自携带**动态符号表**（.dynsym），符号引用在**加载时/首次调用时**解析——`RTLD_LAZY` 首次调用才解析（经 GOT/PLT 跳板），`RTLD_NOW` 加载即全部解析（失败立即可报）。macOS 为 Mach-O 格式、由 dyld 负责加载与符号解析，机制同理。C++ 函数名经过**名字修饰**变成 `_Z…` 形式，`extern "C"` 就是告诉编译器"别修饰"。

**ABI（Application Binary Interface）**是比源码接口更脆弱的契约：源码兼容（重编译能过）≠ 二进制兼容（不重编译直接换 .so 能跑）。常见 ABI 破坏因素：

| 变更 | 为什么破坏 ABI |
|------|---------------|
| 结构体加字段/改顺序 | 布局（偏移）变了，已编译插件按旧偏移读 → 错位/越界 |
| 加虚函数/改虚表 | 虚表布局变了，旧代码取错槽位 |
| 函数签名改变 | 修饰后的符号名都变了，dlsym 直接找不到 |
| 跨 .so 边界传 std::string | 依赖 STL 内联实现与堆分配约定，两端 libstdc++ 版本不一致即崩 |
| 异常穿过 .so 边界 | typeinfo 跨模块匹配依赖 ABI 一致 |

稳定插件接口的工程做法：**接口头文件只含 C 类型与 `extern "C"` 函数**、导出结构体用固定大小字段（显式 int32_t/uint64_t，不用 size_t）、**导出 `plugin_api_version` 整数**（加载时检查，不匹配拒绝加载）、构建用 `-fvisibility=hidden` + 显式导出防符号泄漏（ph19 深入）。**一句话：插件协议按"网络协议"的标准设计**——版本化、定长、明确类型。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 日志与审计落盘 | fstream 追加写、flush、写后错误检查 |
| 数据持久化 / 序列化 | 二进制读写、字节序、结构布局、校验和 |
| 目录扫描 / 文件同步 | std::filesystem 遍历、复制、时间戳比对 |
| 程序配置加载 | key=value 解析、可诊断错误；JSON 生态了解 |
| 网络服务（echo、HTTP） | socket RAII、recv/send 循环、协议边界 |
| 调用外部命令与子进程 | fork/exec/waitpid、system |
| 系统资源封装 | open/read/write RAII、EINTR 重试 |
| 插件与扩展机制 | dlopen/dlsym、extern "C"、稳定接口 + 版本号 |

**不适合**此阶段的事项：

- **构建、调试与工具链**（ph10 构建、调试与工具链阶段）：CMake 深入、vcpkg/conan 依赖管理、Sanitizer、性能分析工具——本阶段示例全部单文件 `c++` 编译即可
- **C++ 标准、编译器与可移植性**（ph11 C++ 标准、编译器与可移植性阶段）：平台宏、条件编译、标准库实现差异——本阶段只用 POSIX，不展开跨平台
- **ABI 与插件机制深入**（ph19 ABI、动态库与插件机制阶段，目录待建）：符号版本控制、visibility 精细管理、跨语言异常边界——本阶段掌握"接口要稳定 + 版本号"的纪律
- **异步 IO 与高性能网络**（ph18 性能优化与 Profiling 阶段、ph22 存储引擎与数据库内核专项阶段，均目录待建）：epoll 事件驱动、io_uring、Boost.Asio 异步模型——本阶段用阻塞 socket + 超时把协议写对，是异步化的前提

## 6. 代码示例

> 每个示例的完整可运行文件在 [`examples/`](./examples/) 目录（ex01~ex06，与下面示例 1~6 一一对应），验证环境 Apple clang 21（g++ 兼容），编译命令统一 `c++ -std=c++20 -Wall -Wextra`，运行产物全部落在 `/tmp`，不污染仓库。全部示例已在本环境编译零警告并运行验证（已验证）。

### 示例 1：日志文件系统（fstream 追加 + 时间戳 + 错误处理）

完整文件：`examples/ex01-logfs.cpp` — 追加模式写日志，写后检查流状态，回读验证。编译 `c++ -std=c++20 -Wall -Wextra ex01-logfs.cpp -o ex01`，运行 `./ex01` 后 `/tmp/ph09_app.log` 出现 3 行带时间戳日志。

```cpp
// examples/ex01-logfs.cpp —— 日志文件系统：fstream 追加写 + 时间戳 + 错误处理
class LogFile {                        // RAII：构造打开、析构自动关闭
public:
    explicit LogFile(const std::string& path) : out_(path, std::ios::app) {
        if (!out_) throw std::runtime_error("cannot open log: " + path);
    }
    void write(const std::string& level, const std::string& msg) {
        out_ << timestamp() << " [" << level << "] " << msg << '\n';
        if (!out_) throw std::runtime_error("log write failed");   // 写后必查
    }
};
```

### 示例 2：TCP echo server（RAII 封装 socket + 超时 + 自测）

完整文件：`examples/ex02-echo.cpp` — 三种模式：`selftest`（fork 子进程连本机回环自动校验）、`server <port>`、`client <port>`。编译 `c++ -std=c++20 -Wall -Wextra ex02-echo.cpp -o ex02`，自测运行 `./ex02 selftest` 输出 `echo: hello echo` 且退出码 0。

```cpp
// examples/ex02-echo.cpp —— TCP echo server：RAII 封装 socket + 阻塞收发 + 超时
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
// 回显一个连接：收多少回多少，直到对端关闭或超时
static void echo_connection(int fd) {
    struct timeval tv{5, 0};                     // 5 秒读超时：对端不发也不挂死
    ::setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    char buf[4096];
    for (;;) {
        ssize_t n = ::recv(fd, buf, sizeof(buf), 0);
        if (n <= 0) break;                       // 0=对端关闭，<0=超时/出错
        if (!send_full(fd, buf, static_cast<size_t>(n))) break;
    }
}
```

### 示例 3：简单 HTTP server（解析请求行 + 200/404）

完整文件：`examples/ex03-http.cpp` — 两种模式：`selftest`（发 `GET /` 与 `GET /nope`，校验 200/404）、`<port>` 手动起服务。编译 `c++ -std=c++20 -Wall -Wextra ex03-http.cpp -o ex03`，自测运行 `./ex03 selftest` 输出 `GET / -> HTTP/1.1 200 OK`、`GET /nope -> HTTP/1.1 404 Not Found`。

```cpp
// examples/ex03-http.cpp —— 简单 HTTP server：解析请求行 + 200/404 响应（Content-Length）
// 构造 HTTP 响应：状态行 + Content-Length 头部 + body
static std::string make_response(const std::string& status,
                                 const std::string& content_type,
                                 const std::string& body) {
    return "HTTP/1.1 " + status + "\r\n"
           "Content-Type: " + content_type + "\r\n"
           "Content-Length: " + std::to_string(body.size()) + "\r\n"
           "Connection: close\r\n\r\n" + body;
}
```

### 示例 4：配置文件解析（key=value，可诊断错误）

完整文件：`examples/ex04-config.cpp` — 解析 `key = value` 配置，错误消息带 文件:行号。编译 `c++ -std=c++20 -Wall -Wextra ex04-config.cpp -o ex04`，运行 `./ex04` 输出 `port=8080 workers=4`；传入含非法行的配置（如 `./ex04 /tmp/ph09_bad.conf`）输出 `xxx.conf:2: expected key=value` 并返回非零。

```cpp
// examples/ex04-config.cpp —— key=value 配置文件解析：可诊断错误（文件:行号）
class ConfigError : public std::runtime_error {
public:
    ConfigError(const std::string& file, int line, const std::string& msg)
        : std::runtime_error(file + ":" + std::to_string(line) + ": " + msg) {}
};
            const size_t eq = line.find('=');
            if (eq == std::string::npos)
                throw ConfigError(path, line_no,
                                  "expected key=value, got: " + line);
```

### 示例 5：文件传输工具（二进制分块 + 校验和）

完整文件：`examples/ex05-filexfer.cpp` — `selftest` 生成 256KB 随机文件 → 分块复制 → 校验源/目标 FNV-1a 一致；`<src> <dst>` 手动复制。编译 `c++ -std=c++20 -Wall -Wextra ex05-filexfer.cpp -o ex05`，自测运行 `./ex05 selftest` 输出 `copied 262144 bytes, checksum=0x... (src == dst) OK`。

```cpp
// examples/ex05-filexfer.cpp —— 文件传输工具：二进制分块读写 + 校验和
// FNV-1a 滚动校验：state 跨块累积，保证"读到的字节就是写出的字节"
static uint32_t checksum(uint32_t state, const char* buf, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        state ^= static_cast<uint8_t>(buf[i]);
        state *= 16777619u;
    }
    return state;
}
        in.read(buf, sizeof(buf));               // 一次最多读一块
        const std::streamsize n = in.gcount();   // 实际读到的字节数（可能不满）
        if (n > 0) {
            out.write(buf, n);
            sum = checksum(sum, buf, static_cast<size_t>(n));
        }
```

### 示例 6：std::filesystem 目录遍历与复制（递归统计 + error_code）

完整文件：`examples/ex06-fswalk.cpp` — `selftest` 在 `/tmp` 建 3 层目录树 → 递归统计文件数/大小 → 复制到目标 → 逐项比对；`<dir>` 手动统计。编译 `c++ -std=c++20 -Wall -Wextra ex06-fswalk.cpp -o ex06`，自测运行 `./ex06 selftest` 输出 `scanned/copied` 各 3 文件 2 目录且字节数一致。

```cpp
// examples/ex06-fswalk.cpp —— std::filesystem 目录遍历：递归统计文件数/大小 + 复制演示
// 递归遍历目录树统计；单条错误通过 error_code 容忍，不中断整体
static TreeStats scan_tree(const fs::path& root) {
    TreeStats st;
    std::error_code ec;
    for (fs::recursive_directory_iterator it(root, ec), end; it != end;
         it.increment(ec)) {
        if (ec) {                                   // 某个子目录不可读：跳过继续
            std::cerr << "warn: " << ec.message() << '\n';
            ec.clear();
            continue;
        }
        if (it->is_directory(ec)) {
            ++st.dirs;
        } else if (it->is_regular_file(ec)) {
            ++st.files;
            st.bytes += it->file_size(ec);
        }
    }
    return st;
}
```

## 7. 总结

### 关键要点

1. **IO 必须处理失败与超时**：文件打开/写入后要检查流状态，socket 收发要设超时——失败与超时是常态不是意外
2. **二进制文件是内存字节的搬运**：read/write + sizeof 配对使用，警惕结构体 padding 与字节序，跨机器格式要逐字段显式序列化
3. **std::filesystem 是 C++17 的文件系统标准库**：路径拼接用 `operator/`、目录遍历、复制删除，批量操作用 error_code 版逐个容忍失败
4. **配置解析要给出可诊断错误**：错误必须带文件与行号（JSON 带字节偏移）——"parse failed"等于没报
5. **网络协议要处理边界和粘包**：TCP 是字节流，recv/send 要循环（recv_full/send_full），消息边界用 length-prefix
6. **socket 与 fd 一律 RAII 封装**：构造打开、析构关闭、禁拷贝允移动——杜绝 use-after-close
7. **动态库接口要稳定**：extern "C" 关名字修饰、固定签名与结构体布局、导出版本号、跨 .so 边界只传 C 类型
8. **系统调用要封装并处理 EINTR**：open/read/write 走 RAII 类，被信号打断要重试，errno 转可读消息
9. **进程与线程按场景取舍**：隔离/外部程序用 fork/exec，共享数据高频协作用 std::thread；waitpid 防僵尸
10. **阻塞模型先写对再谈性能**：本阶段用阻塞 socket + 超时把协议写对，epoll/io_uring 是 ph18 性能优化与 Profiling 阶段、ph22 存储引擎与数据库内核专项阶段的事

### 跨语言对比：文件与网络编程

| 维度 | C++ | C | Go | Java | Rust |
|------|-----|---|----|------|------|
| 文件 API | fstream / std::filesystem | fopen / open+read | os.Open / io | java.nio.file | std::fs |
| 网络编程 | POSIX socket + RAII 封装 | POSIX socket（裸 fd） | net 包（goroutine + conn） | java.net / NIO | std::net（TcpStream/TcpListener） |
| 错误处理 | 异常 + 流状态 / errno | errno | error 值 | 受检/非受检异常 | Result\<T, E\> |
| 配置/序列化 | key=value 手写 / nlohmann::json | cJSON / jansson | encoding/json | Jackson / Gson | serde_json |
| 资源管理 | RAII（析构自动关闭） | 手动 close | defer | try-with-resources | Drop + 所有权 |
| 并发配套 | std::thread + 阻塞 socket | pthread + 阻塞 socket | goroutine + net（天然配合） | 线程 + NIO | 线程 + async（tokio） |

一句话：C++ 与 C 共享同一套 POSIX 系统编程基座，但 **RAII 把"忘记 close/泄漏 fd"从惯例层消灭**；Go 的 goroutine 让阻塞式网络代码天然并发，Java/Rust 各自用 NIO/async 生态走向事件驱动——**本阶段的收获是先把 C++ 的文件与网络编程写得正确、可诊断、可复用**。

### 阶段验收清单

- [ ] 能写**文件和网络错误处理**：打开/写入/收发失败全部被检查，超时被处理，错误信息可诊断（含路径/行号/errno）
- [ ] 能**封装系统资源**：文件、socket、fd 全部 RAII 封装，禁拷贝允移动，异常路径自动释放
- [ ] 能设计**基础配置模块**：key=value 解析，支持注释与类型转换，错误带文件与行号
- [ ] 能处理**网络协议边界**：recv/send 循环 + length-prefix 解决粘包/半包，socket 带超时
- [ ] 能写出**稳定插件接口**：extern "C" + 固定签名 + 版本号检查
- [ ] 能独立完成五个练习：日志文件系统、TCP echo server、简单 HTTP server、文件传输工具、配置文件解析

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：日志文件系统、TCP echo server、简单 HTTP server、文件传输工具、配置文件解析，共 5 题——其中练习 1~4 与 roadmap ph09「练习」小节的四项承诺一一对应，练习 5（配置文件解析）对应 roadmap「学习内容」中的 JSON/配置文件。完成 5 题后继续。进阶（可选）：给 echo server 加 length-prefix 帧格式；用 fork + exec 实现"命令执行器"；用 std::filesystem 递归统计目录大小。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**文件同步工具**——std::filesystem 递归扫描 → 按大小/修改时间做差异比对 → 分块复制 + FNV-1a 校验 → 统计输出，roadmap 推荐项目，也是存储引擎数据搬迁的雏形。roadmap 的另一个推荐项目「配置中心客户端」（HTTP 拉取 JSON → 本地缓存）依赖第三方 HTTP/JSON 库，本阶段不引入第三方库未在 project/ 落地，可作为扩展方向（见 project/README.md 扩展方向）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[构建、调试与工具链阶段](../ph10-build-toolchain/10-build-toolchain.md) —— CMake 深入、vcpkg/conan 依赖管理、Sanitizer、性能分析工具，把本阶段的单文件 `c++` 编译升级为工程化构建。
