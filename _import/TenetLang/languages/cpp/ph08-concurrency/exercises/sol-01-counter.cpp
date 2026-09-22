// sol-01-counter.cpp —— 练习 1 参考实现：多线程计数器（mutex 版 + atomic 版）
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra -pthread sol-01-counter.cpp -o sol-01
// 运行：./sol-01（断言通过、退出码 0）
// 附：观察数据竞争——去掉保护后用 -fsanitize=thread 编译运行，TSan 会报告 race
#include <atomic>
#include <cassert>
#include <iostream>
#include <mutex>
#include <thread>
#include <vector>

int main() {
    constexpr int kThreads = 8;
    constexpr int kPerThread = 100000;
    constexpr int kExpected = kThreads * kPerThread;

    int mutex_count = 0;                   // 版本 A：mutex 保护
    std::mutex mtx;
    {
        std::vector<std::thread> ts;
        for (int i = 0; i < kThreads; ++i)
            ts.emplace_back([&] {
                for (int j = 0; j < kPerThread; ++j) {
                    std::lock_guard<std::mutex> lock(mtx);
                    ++mutex_count;
                }
            });
        for (auto& t : ts) t.join();
    }
    assert(mutex_count == kExpected);

    std::atomic<int> atomic_count{0};      // 版本 B：atomic 无锁 RMW
    {
        std::vector<std::thread> ts;
        for (int i = 0; i < kThreads; ++i)
            ts.emplace_back([&] {
                for (int j = 0; j < kPerThread; ++j) atomic_count.fetch_add(1);
            });
        for (auto& t : ts) t.join();
    }
    assert(atomic_count.load() == kExpected);

    std::cout << "mutex=" << mutex_count << " atomic=" << atomic_count.load()
              << " expected=" << kExpected << " OK\n";
    return 0;
}
