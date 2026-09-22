// ex03-bounded-pc.cpp —— 生产者消费者模型：有界队列 + 双条件变量（not_full / not_empty）
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra -pthread ex03-bounded-pc.cpp -o ex03
// 运行：./ex03（produce/consume 各 20 行，交错出现，队列容量恒不超过 4）
#include <condition_variable>
#include <cstddef>
#include <iostream>
#include <mutex>
#include <queue>
#include <thread>

class BoundedQueue {
public:
    explicit BoundedQueue(std::size_t cap) : capacity_(cap) {}
    void produce(int v) {
        std::unique_lock<std::mutex> lock(mtx_);
        not_full_.wait(lock, [this] { return q_.size() < capacity_; });   // 满则生产者等待
        q_.push(v);
        lock.unlock();                    // 先解锁再 IO 与 notify，缩小临界区
        std::cout << "produced " << v << "\n";
        not_empty_.notify_one();
    }
    int consume() {
        std::unique_lock<std::mutex> lock(mtx_);
        not_empty_.wait(lock, [this] { return !q_.empty(); });            // 空则消费者等待
        int v = q_.front();
        q_.pop();
        lock.unlock();
        std::cout << "consumed " << v << "\n";
        not_full_.notify_one();
        return v;
    }
private:
    std::mutex mtx_;
    std::condition_variable not_empty_, not_full_;
    std::queue<int> q_;
    std::size_t capacity_;
};

int main() {
    BoundedQueue q(4);                    // 有界缓冲：容量 4
    std::thread producer([&] { for (int i = 0; i < 20; ++i) q.produce(i); });
    std::thread consumer([&] { for (int i = 0; i < 20; ++i) q.consume(); });
    producer.join();
    consumer.join();
    std::cout << "done\n";
    return 0;
}
