// ex04-threadpool.cpp —— 简单线程池：固定 N 个 worker + 任务队列，析构自动 drain
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra -pthread ex04-threadpool.cpp -o ex04
// 运行：./ex04（输出 12 行 task i done，顺序不定；任务必定全部执行完）
#include <condition_variable>
#include <cstddef>
#include <functional>
#include <iostream>
#include <mutex>
#include <queue>
#include <sstream>
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
        cv_.notify_all();                 // 先置标志 → 唤醒所有 worker → join（顺序不能错）
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
                if (stop_ && tasks_.empty()) return;   // 停止且无任务 → 退出
                task = std::move(tasks_.front());
                tasks_.pop();
            }
            task();                       // 锁外执行任务，长任务不阻塞队列
        }
    }
    std::vector<std::thread> workers_;
    std::queue<std::function<void()>> tasks_;
    std::mutex mtx_;
    std::condition_variable cv_;
    bool stop_ = false;
};

int main() {
    ThreadPool pool(4);                   // 4 个 worker 线程
    for (int i = 0; i < 12; ++i)
        pool.submit([i] {
            std::ostringstream line;      // 先拼好整行再一次输出，避免多线程输出交错
            line << "task " << i << " done by " << std::this_thread::get_id() << "\n";
            std::cout << line.str();
        });
    return 0;                             // 析构：停止 → 唤醒 → join，任务全部执行完
}
