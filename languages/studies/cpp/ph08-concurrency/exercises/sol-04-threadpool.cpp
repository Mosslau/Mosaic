// sol-04-threadpool.cpp —— 练习 4 参考实现：简单线程池（固定 worker + 任务队列）
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra -pthread sol-04-threadpool.cpp -o sol-04
// 运行：./sol-04（断言通过、退出码 0，无挂起）
#include <atomic>
#include <cassert>
#include <condition_variable>
#include <cstddef>
#include <functional>
#include <iostream>
#include <mutex>
#include <queue>
#include <thread>
#include <vector>

class ThreadPool {
public:
    explicit ThreadPool(std::size_t n) {
        for (std::size_t i = 0; i < n; ++i)
            workers_.emplace_back([this] { worker_loop(); });
    }
    ~ThreadPool() {
        { std::lock_guard<std::mutex> lock(mtx_); stop_ = true; }
        cv_.notify_all();                  // 顺序：置标志 → 唤醒 → join
        for (auto& w : workers_) w.join();
    }
    ThreadPool(const ThreadPool&) = delete;
    ThreadPool& operator=(const ThreadPool&) = delete;

    void submit(std::function<void()> task) {
        { std::lock_guard<std::mutex> lock(mtx_); tasks_.push(std::move(task)); }
        cv_.notify_one();
    }
private:
    void worker_loop() {
        for (;;) {
            std::function<void()> task;
            {
                std::unique_lock<std::mutex> lock(mtx_);
                cv_.wait(lock, [this] { return stop_ || !tasks_.empty(); });
                if (stop_ && tasks_.empty()) return;   // 已停止且队列排空才退出
                task = std::move(tasks_.front());
                tasks_.pop();
            }
            task();                          // 锁外执行任务
        }
    }
    std::vector<std::thread> workers_;
    std::queue<std::function<void()>> tasks_;
    std::mutex mtx_;
    std::condition_variable cv_;
    bool stop_ = false;
};

int main() {
    constexpr int kTasks = 12;
    std::atomic<int> done{0};
    {
        ThreadPool pool(4);                // 4 个 worker
        for (int i = 0; i < kTasks; ++i)
            pool.submit([&done] { done.fetch_add(1); });
    }                                      // 析构：任务全部执行完才返回
    assert(done.load() == kTasks);
    std::cout << "pool drained, " << done.load() << "/" << kTasks << " tasks done OK\n";
    return 0;
}
