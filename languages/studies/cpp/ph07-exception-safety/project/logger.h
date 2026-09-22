// 来源：languages/cpp/ph07-exception-safety/project/logger.h
// 说明：日志模块头文件——级别过滤、时间戳、线程安全预留
// 验证环境：Apple clang 17（g++ 兼容）
// 编译：g++ -Wall -Wextra -std=c++17 -c logger.cpp
// 验证状态：已验证
#pragma once

#include <mutex>
#include <ostream>
#include <string>

namespace ph07 {

enum class LogLevel { Debug = 0, Info, Warn, Error };

class Logger {
public:
    explicit Logger(std::ostream& os);

    void set_min_level(LogLevel lv) noexcept { min_level_ = lv; }
    void log(LogLevel lv, const std::string& msg);

private:
    static const char* level_name(LogLevel lv) noexcept;
    static std::string timestamp();

    std::ostream& os_;
    LogLevel min_level_ = LogLevel::Debug;
    std::mutex mutex_;
};

}  // namespace ph07
