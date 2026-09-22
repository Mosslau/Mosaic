// ex01-logfs.cpp —— 日志文件系统：fstream 追加写 + 时间戳 + 错误处理
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra ex01-logfs.cpp -o ex01
// 运行：./ex01（追加 3 条日志到 /tmp/ph09_app.log 并回读显示）
// 验证状态：已验证（编译零警告 + 运行通过）
#include <chrono>
#include <ctime>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

class LogFile {                        // RAII：构造打开、析构自动关闭
public:
    explicit LogFile(const std::string& path) : out_(path, std::ios::app) {
        if (!out_) throw std::runtime_error("cannot open log: " + path);
    }
    void write(const std::string& level, const std::string& msg) {
        out_ << timestamp() << " [" << level << "] " << msg << '\n';
        if (!out_) throw std::runtime_error("log write failed");   // 写后必查
    }
private:
    static std::string timestamp() {
        const std::time_t t = std::chrono::system_clock::to_time_t(
            std::chrono::system_clock::now());
        std::tm tm{};
        localtime_r(&t, &tm);
        char buf[32];
        std::strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &tm);
        return buf;
    }
    std::ofstream out_;
};

int main() {
    try {
        LogFile log("/tmp/ph09_app.log");      // 追加模式：进程重启不丢历史
        log.write("INFO", "service started");
        log.write("ERROR", "disk full");
        log.write("INFO", "service stopped");
    } catch (const std::exception& e) {
        std::cerr << "log error: " << e.what() << '\n';
        return 1;
    }
    std::ifstream in("/tmp/ph09_app.log");     // 回读验证 3 行都在
    std::string line;
    while (std::getline(in, line)) std::cout << line << '\n';
    return 0;
}
