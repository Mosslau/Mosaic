// sol-03-bounded-pc.cpp —— 练习 3 参考实现：生产者消费者（有界队列 + 双条件变量）
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra -pthread sol-03-bounded-pc.cpp -o sol-03
// 运行：./sol-03（断言通过、退出码 0，无挂起）
#include <cassert>
#include <condition_variable>
#include <cstddef>
#include <iostream>
#include <mutex>
#include <queue>
#include <thread>
#include <vector>

class BoundedQueue {
public:
    explicit BoundedQueue(std::size_t cap) : capacity_(cap) {}
    void produce(int v) {
        std::unique_lock<std::mutex> lock(mtx_);
        not_full_.wait(lock, [this] { return q_.size() < capacity_; });   // 满则等待
        q_.push(v);
        lock.unlock();
        not_empty_.notify_one();           // 唤醒消费者：方向不能反
    }
    int consume() {
        std::unique_lock<std::mutex> lock(mtx_);
        not_empty_.wait(lock, [this] { return !q_.empty(); });            // 空则等待
        int v = q_.front();
        q_.pop();
        lock.unlock();
        not_full_.notify_one();            // 唤醒生产者
        return v;
    }
private:
    std::mutex mtx_;
    std::condition_variable not_empty_, not_full_;
    std::queue<int> q_;
    std::size_t capacity_;
};

int main() {
    BoundedQueue q(4);                     // 容量 4 的有界队列
    constexpr int kCount = 20;

    std::vector<int> received;
    received.reserve(kCount);
    std::thread consumer([&] {
        for (int i = 0; i < kCount; ++i) received.push_back(q.consume());
    });
    std::thread producer([&] {
        for (int i = 0; i < kCount; ++i) q.produce(i);
    });
    producer.join();
    consumer.join();

    for (int i = 0; i < kCount; ++i) assert(received[i] == i);   // 0~19 顺序无丢失无重复
    std::cout << "produced & consumed " << received.size() << " items in order OK\n";
    return 0;
}
