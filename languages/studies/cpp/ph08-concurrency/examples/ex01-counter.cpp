// ex01-counter.cpp —— 多线程计数器：mutex 保护与 atomic 无锁两种方式对比
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra -pthread ex01-counter.cpp -o ex01
// 运行：./ex01（两种方式都应输出 800000）
#include <atomic>
#include <iostream>
#include <mutex>
#include <thread>
#include <vector>

int main() {
    constexpr int kThreads = 8;
    constexpr int kPerThread = 100000;
    {   // 方式一：mutex 保护 —— 复合临界区，串行但正确
        int counter = 0;
        std::mutex mtx;
        std::vector<std::thread> ts;
        for (int i = 0; i < kThreads; ++i)
            ts.emplace_back([&] {
                for (int j = 0; j < kPerThread; ++j) {
                    std::lock_guard<std::mutex> lock(mtx);   // RAII：作用域结束自动解锁
                    ++counter;
                }
            });
        for (auto& t : ts) t.join();
        std::cout << "mutex  counter = " << counter << "\n";
    }
    {   // 方式二：atomic —— 单变量 RMW，无锁
        std::atomic<int> counter{0};
        std::vector<std::thread> ts;
        for (int i = 0; i < kThreads; ++i)
            ts.emplace_back([&] {
                for (int j = 0; j < kPerThread; ++j)
                    counter.fetch_add(1);
            });
        for (auto& t : ts) t.join();
        std::cout << "atomic counter = " << counter.load() << "\n";
    }
    return 0;
}
