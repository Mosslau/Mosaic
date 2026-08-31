// ex02-tsqueue.cpp —— 线程安全队列：mutex + condition_variable（pop 非阻塞 / wait_pop 阻塞）
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra -pthread ex02-tsqueue.cpp -o ex02
// 运行：./ex02（输出 got 0 4 16 ... 81，最后 queue empty: true）
#include <condition_variable>
#include <deque>
#include <iostream>
#include <mutex>
#include <optional>
#include <thread>

template <typename T>
class ThreadSafeQueue {
public:
    void push(T v) {
        { std::lock_guard<std::mutex> lock(mtx_); data_.push_back(std::move(v)); }
        cv_.notify_one();                        // 锁外 notify，避免唤醒后立即抢锁
    }
    std::optional<T> pop() {              // 非阻塞：空队列返回 nullopt
        std::lock_guard<std::mutex> lock(mtx_);
        if (data_.empty()) return std::nullopt;
        T v = std::move(data_.front());
        data_.pop_front();
        return v;
    }
    T wait_pop() {                        // 阻塞：谓词等待直到有元素
        std::unique_lock<std::mutex> lock(mtx_);
        cv_.wait(lock, [this] { return !data_.empty(); });   // 谓词循环防虚假/丢失唤醒
        T v = std::move(data_.front());
        data_.pop_front();
        return v;
    }
    bool empty() const {
        std::lock_guard<std::mutex> lock(mtx_);
        return data_.empty();
    }
private:
    mutable std::mutex mtx_;              // empty() 是 const 方法，锁要 mutable
    std::condition_variable cv_;
    std::deque<T> data_;
};

int main() {
    ThreadSafeQueue<int> q;
    std::thread producer([&] { for (int i = 0; i < 10; ++i) q.push(i * i); });
    std::thread consumer([&] {
        for (int i = 0; i < 10; ++i) {
            int v = q.wait_pop();
            std::cout << "got " << v << "\n";   // 取值与输出分离，避免锁内 IO
        }
    });
    producer.join();
    consumer.join();
    std::cout << "queue empty: " << std::boolalpha << q.empty() << "\n";
    return 0;
}
