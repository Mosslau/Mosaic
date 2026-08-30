// 来源：languages/cpp/ph07-exception-safety/07-exception-safety.md 第 6 章示例 4
// 说明：日志模块——级别过滤 + 时间戳 + 线程安全预留
// 验证环境：Apple clang 17（g++ 兼容）
// 编译：g++ -Wall -Wextra -std=c++17 examples/ex04-logger.cpp -o ex04 -pthread
// 运行：./ex04
// 验证状态：已验证
#include <chrono>
#include <ctime>
#include <iostream>
#include <mutex>
#include <string>

enum class LogLevel { Debug = 0, Info, Warn, Error };

class Logger {
public:
    static Logger& instance() {            // 简单单例（ph08 之前够用）
        static Logger inst;
        return inst;
    }
    void set_min_level(LogLevel lv) { min_level_ = lv; }
    void log(LogLevel lv, const std::string& msg) {
        if (lv < min_level_) return;                 // 级别过滤
        std::lock_guard<std::mutex> lock(mutex_);    // 线程安全预留
        std::cout << "[" << level_name(lv) << "] "
                  << timestamp() << " " << msg << "\n";
    }
private:
    Logger() = default;
    static const char* level_name(LogLevel lv) {
        switch (lv) {
            case LogLevel::Debug: return "DEBUG";
            case LogLevel::Info:  return "INFO";
            case LogLevel::Warn:  return "WARN";
            case LogLevel::Error: return "ERROR";
        }
        return "?";
    }
    static std::string timestamp() {
        std::time_t t = std::chrono::system_clock::to_time_t(
                            std::chrono::system_clock::now());
        char buf[32];
        std::strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", std::localtime(&t));
        return buf;
    }
    LogLevel min_level_ = LogLevel::Debug;
    std::mutex mutex_;
};

int main() {
    Logger& log = Logger::instance();
    log.set_min_level(LogLevel::Info);     // 过滤 Debug
    log.log(LogLevel::Debug, "this will be filtered");
    log.log(LogLevel::Info, "config loaded");
    log.log(LogLevel::Warn, "disk usage high");
    log.log(LogLevel::Error, "write failed: disk full");
    return 0;
}
