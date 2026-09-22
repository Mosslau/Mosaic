// sol-02-tsqueue.cpp —— 练习 2 参考实现：线程安全队列（push / pop / wait_pop）
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra -pthread sol-02-tsqueue.cpp -o sol-02
// 运行：./sol-02（断言通过、退出码 0）
#include <cassert>
#include <condition_variable>
#include <deque>
#include <iostream>
#include <mutex>
#include <optional>
#include <thread>
#include <vector>

template <typename T>
class ThreadSafeQueue {
public:
    void push(T v) {
        { std::lock_guard<std::mutex> lock(mtx_); data_.push_back(std::move(v)); }
        cv_.notify_one();                        // 锁外 notify
    }
    std::optional<T> pop() {              // 非阻塞
        std::lock_guard<std::mutex> lock(mtx_);
        if (data_.empty()) return std::nullopt;
        T v = std::move(data_.front());
        data_.pop_front();
        return v;
    }
    T wait_pop() {                        // 阻塞：谓词等待，防虚假/丢失唤醒
        std::unique_lock<std::mutex> lock(mtx_);
        cv_.wait(lock, [this] { return !data_.empty(); });
        T v = std::move(data_.front());
        data_.pop_front();
        return v;
    }
    bool empty() const {
        std::lock_guard<std::mutex> lock(mtx_);
        return data_.empty();
    }
private:
    mutable std::mutex mtx_;              // empty() 是 const 方法
    std::condition_variable cv_;
    std::deque<T> data_;
};

int main() {
    ThreadSafeQueue<int> q;
    constexpr int kCount = 10;

    std::vector<int> received;
    std::thread consumer([&] {
        for (int i = 0; i < kCount; ++i) received.push_back(q.wait_pop());
    });
    std::thread producer([&] {
        for (int i = 0; i < kCount; ++i) q.push(i * i);
    });
    producer.join();
    consumer.join();

    for (int i = 0; i < kCount; ++i) assert(received[i] == i * i);   // 值与顺序正确
    assert(q.empty());
    assert(q.pop() == std::nullopt);         // 非阻塞 pop 对空队列返回 nullopt

    std::cout << "received " << received.size() << " items in order, queue empty OK\n";
    return 0;
}
