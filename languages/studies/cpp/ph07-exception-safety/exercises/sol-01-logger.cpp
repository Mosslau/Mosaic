// 来源：languages/cpp/ph07-exception-safety/exercises/README.md 练习 1
// 说明：日志模块——级别过滤 + 时间戳 + 线程安全预留，支持 stdout/stderr
// 验证环境：Apple clang 17（g++ 兼容）
// 编译：g++ -Wall -Wextra -std=c++17 exercises/sol-01-logger.cpp -o sol01 -pthread
// 运行：./sol01
// 验证状态：已验证
#include <chrono>
#include <ctime>
#include <iostream>
#include <mutex>
#include <string>

namespace ph07 {

enum class LogLevel { Debug = 0, Info, Warn, Error };

class Logger {
public:
    explicit Logger(std::ostream& os) : os_(os) {}

    void set_min_level(LogLevel lv) { min_level_ = lv; }

    void log(LogLevel lv, const std::string& msg) {
        if (lv < min_level_) return;
        std::lock_guard<std::mutex> lock(mutex_);
        os_ << "[" << level_name(lv) << "] " << timestamp() << " " << msg << "\n";
    }

private:
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
        const std::time_t t = std::chrono::system_clock::to_time_t(
                                  std::chrono::system_clock::now());
        char buf[32];
        std::strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", std::localtime(&t));
        return buf;
    }

    std::ostream& os_;
    LogLevel min_level_ = LogLevel::Debug;
    std::mutex mutex_;
};

}  // namespace ph07

int main() {
    ph07::Logger out_log(std::cout);
    out_log.set_min_level(ph07::LogLevel::Info);
    out_log.log(ph07::LogLevel::Debug, "filtered");      // 被过滤
    out_log.log(ph07::LogLevel::Info, "config loaded");
    out_log.log(ph07::LogLevel::Warn, "disk usage high");

    ph07::Logger err_log(std::cerr);
    err_log.log(ph07::LogLevel::Error, "write failed: disk full");
    return 0;
}
