// async_logger.h —— 异步日志系统接口
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 自包含头文件：只依赖标准库
#ifndef PH08_ASYNC_LOGGER_H
#define PH08_ASYNC_LOGGER_H

#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <fstream>
#include <mutex>
#include <string>
#include <thread>

namespace ph08 {

enum class LogLevel { debug = 0, info, warn, error };

struct LogStats {
    std::uint64_t produced = 0;   // 通过级别过滤、进入投递流程的条数
    std::uint64_t written = 0;    // 后台线程实际写出的条数
    std::uint64_t dropped = 0;    // 队列满被丢弃的条数
};

// 异步日志：业务线程把日志行投到有界队列，后台 jthread 批量写出。
// 生命周期：析构 = 请求停止（stop_token）→ 后台线程排空残余日志 → 自动 join。
class AsyncLogger {
public:
    // path 打开失败抛 std::runtime_error；capacity 是有界队列上限
    explicit AsyncLogger(const std::string& path, std::size_t capacity = 1024);
    ~AsyncLogger() = default;   // worker_ 是 jthread：析构自动 request_stop + join

    AsyncLogger(const AsyncLogger&) = delete;
    AsyncLogger& operator=(const AsyncLogger&) = delete;

    void set_min_level(LogLevel level);
    void log(LogLevel level, const std::string& message);   // 队列满则丢弃并计数
    LogStats stats() const;

private:
    void run(std::stop_token st);                  // 后台线程主循环
    void drain();                                  // 排空队列并 flush（调用方持锁）
    static const char* level_name(LogLevel level);
    static std::string timestamp();

    const std::size_t capacity_;
    std::ofstream out_;
    std::mutex mutex_;
    std::condition_variable_any not_empty_;        // _any 版本支持 stop_token 等待
    std::deque<std::string> queue_;
    std::atomic<LogLevel> min_level_{LogLevel::debug};
    std::atomic<std::uint64_t> produced_{0};
    std::atomic<std::uint64_t> written_{0};
    std::atomic<std::uint64_t> dropped_{0};
    std::jthread worker_;                          // 最后声明：最先析构，先停后台线程
};

}  // namespace ph08

#endif  // PH08_ASYNC_LOGGER_H
