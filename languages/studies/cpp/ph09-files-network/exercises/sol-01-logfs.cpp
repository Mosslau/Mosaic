// sol-01-logfs.cpp —— 练习 1 参考实现：日志文件系统（追加 + 时间戳 + 级别过滤 + 错误检查）
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra sol-01-logfs.cpp -o sol-01
// 运行：./sol-01（追加 3 条日志到 /tmp/ph09_ex1.log，级别过滤后至少 2 条落盘）
// 验证状态：已验证（编译零警告 + 运行通过）
#include <chrono>
#include <ctime>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

// 日志级别：数值越大越严重，min_level 决定哪些级别放行
enum class Level { info = 0, warn = 1, error = 2 };

class LogFile {                        // RAII：构造打开（追加）、析构自动关闭
public:
    LogFile(const std::string& path, Level min_level)
        : out_(path, std::ios::app), min_level_(min_level) {
        if (!out_) throw std::runtime_error("cannot open log: " + path);
    }
    void write(Level level, const std::string& msg) {
        if (level < min_level_) return;              // 级别过滤：低于阈值直接丢弃
        out_ << timestamp() << " [" << level_name(level) << "] " << msg << '\n';
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
    static const char* level_name(Level l) {
        switch (l) {
            case Level::info:  return "INFO";
            case Level::warn:  return "WARN";
            case Level::error: return "ERROR";
        }
        return "?";
    }
    std::ofstream out_;
    Level min_level_;
};

int main() {
    try {
        // 阈值 warn：info 被过滤，warn/error 落盘
        LogFile log("/tmp/ph09_ex1.log", Level::warn);
        log.write(Level::info, "debug detail (filtered)");
        log.write(Level::warn, "low disk space");
        log.write(Level::error, "disk full");
    } catch (const std::exception& e) {
        std::cerr << "log error: " << e.what() << '\n';
        return 1;
    }
    // 回读验证：本次写入的 WARN/ERROR 两条都在（追加模式可能已有历史行）
    std::ifstream in("/tmp/ph09_ex1.log");
    std::string line;
    bool seen_warn = false, seen_error = false;
    while (std::getline(in, line)) {
        std::cout << line << '\n';
        seen_warn = seen_warn || line.find("[WARN]") != std::string::npos;
        seen_error = seen_error || line.find("[ERROR]") != std::string::npos;
    }
    std::cout << "warn=" << seen_warn << " error=" << seen_error
              << " (info filtered, append keeps history)\n";
    return (seen_warn && seen_error) ? 0 : 1;
}
