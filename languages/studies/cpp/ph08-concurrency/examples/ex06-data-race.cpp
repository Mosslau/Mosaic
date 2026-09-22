// 故意出错示例：本程序含数据竞争（UB），结果小于 200000 属预期。
// 运行前提：观察数据竞争请用 TSan 编译运行——
//   c++ -std=c++20 -Wall -Wextra -pthread -fsanitize=thread -g ex06-data-race.cpp -o ex06_tsan && ./ex06_tsan
// TSan 会精确定位 counter++ 的竞争；普通编译裸跑只是结果不确定，看不到诊断信息。
#include <iostream>
#include <thread>
#include <vector>

int main() {
    int counter = 0;                       // 故意不加保护：两个线程的 ++ 互相覆盖
    constexpr int kThreads = 2;
    constexpr int kPerThread = 100000;
    std::vector<std::thread> ts;
    for (int i = 0; i < kThreads; ++i)
        ts.emplace_back([&] {
            for (int j = 0; j < kPerThread; ++j) ++counter;   // 非原子 RMW：读-改-写有窗口
        });
    for (auto& t : ts) t.join();
    std::cout << "counter = " << counter << " (expected " << kThreads * kPerThread
              << "; 小于期望值即数据竞争导致的丢失更新)\n";
    return 0;
}
