// async_logger.cpp —— 异步日志系统实现
// 验证环境：Apple clang 21（g++ 兼容），C++20
#include "async_logger.h"

#include <chrono>
#include <ctime>
#include <stdexcept>
#include <utility>

namespace ph08 {

AsyncLogger::AsyncLogger(const std::string& path, std::size_t capacity)
    : capacity_(capacity), out_(path) {
    if (!out_) throw std::runtime_error("cannot open log file: " + path);
    // 成员按声明顺序初始化，worker_ 最后构造：启动时其余成员已全部就绪
    worker_ = std::jthread([this](std::stop_token st) { run(st); });
}

void AsyncLogger::set_min_level(LogLevel level) {
    min_level_.store(level);
}

void AsyncLogger::log(LogLevel level, const std::string& message) {
    if (level < min_level_.load()) return;         // 级别过滤：不入队
    produced_.fetch_add(1);
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (queue_.size() >= capacity_) {          // 有界队列：满则丢弃，绝不阻塞业务线程
            dropped_.fetch_add(1);
            return;
        }
        queue_.push_back("[" + std::string(level_name(level)) + "] " +
                         timestamp() + " " + message);
    }
    not_empty_.notify_one();                       // 锁外 notify
}

LogStats AsyncLogger::stats() const {
    return {produced_.load(), written_.load(), dropped_.load()};
}

void AsyncLogger::run(std::stop_token st) {
    std::unique_lock<std::mutex> lock(mutex_);
    while (!st.stop_requested()) {
        // wait 的 stop_token 重载：收到停止请求立即返回 false，无需额外唤醒
        not_empty_.wait(lock, st, [this] { return !queue_.empty(); });
        drain();                                   // 批量写出本轮累积的日志
    }
    drain();                                       // 停止后排空残余，不丢已入队的日志
}

void AsyncLogger::drain() {                        // 调用方必须已持有 mutex_
    while (!queue_.empty()) {
        out_ << queue_.front() << '\n';
        queue_.pop_front();
        written_.fetch_add(1);
    }
    out_.flush();
}

const char* AsyncLogger::level_name(LogLevel level) {
    switch (level) {
        case LogLevel::debug: return "DEBUG";
        case LogLevel::info:  return "INFO";
        case LogLevel::warn:  return "WARN";
        case LogLevel::error: return "ERROR";
    }
    return "?";                                    // 不可达：enum class 穷尽
}

std::string AsyncLogger::timestamp() {
    const std::time_t t =
        std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
    std::tm tm{};
    localtime_r(&t, &tm);                          // 线程安全版本（POSIX）
    char buf[32];
    std::strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &tm);
    return buf;
}

}  // namespace ph08
