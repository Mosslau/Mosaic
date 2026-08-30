// 来源：languages/cpp/ph07-exception-safety/project/logger.cpp
// 说明：日志模块实现
// 验证环境：Apple clang 17（g++ 兼容）
// 编译：g++ -Wall -Wextra -std=c++17 -c logger.cpp -pthread
// 验证状态：已验证
#include "logger.h"

#include <chrono>
#include <ctime>

namespace ph07 {

Logger::Logger(std::ostream& os) : os_(os) {}

void Logger::log(LogLevel lv, const std::string& msg) {
    if (lv < min_level_) return;
    std::lock_guard<std::mutex> lock(mutex_);
    os_ << "[" << level_name(lv) << "] " << timestamp() << " " << msg << "\n";
}

const char* Logger::level_name(LogLevel lv) noexcept {
    switch (lv) {
        case LogLevel::Debug: return "DEBUG";
        case LogLevel::Info:  return "INFO";
        case LogLevel::Warn:  return "WARN";
        case LogLevel::Error: return "ERROR";
    }
    return "?";
}

std::string Logger::timestamp() {
    const std::time_t t = std::chrono::system_clock::to_time_t(
                              std::chrono::system_clock::now());
    char buf[32];
    std::strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", std::localtime(&t));
    return buf;
}

}  // namespace ph07
