// exercises/sol-03-sanitizer-builds.cpp —— 练习 3 参考实现：ASan/TSan 构建开关（已验证）
// 同一份源码三种构建，全部应零报告通过；本文件本身不含 bug——Sanitizer 构建的意义是
// 「在插桩下复跑既有测试/负载」，让潜伏的 UB 现形（承接 ph15：工具是复现手段）。
//
// 验证环境：macOS arm64，Apple clang 21.0.0（c++）
// ⚠️ Sanitizer 构建一律用 Apple clang：Homebrew clang 21.1.8 的 ASan 运行时在本机
//    初始化即挂起、TSan 崩溃（examples/ex04 Makefile 文件头有实测记录）。
//
// 构建矩阵（三条命令即「开启 ASan/TSan 构建」的最小答案；已验证均零报告、退出码 0）：
//   # 1. 常规构建（基线）
//   c++ -std=c++20 -Wall -Wextra -O1 -g sol-03-sanitizer-builds.cpp -o /tmp/ph16cpp-sol03
//   # 2. ASan+UBSan 构建（内存错误 + 逻辑 UB）
//   c++ -std=c++20 -Wall -Wextra -O1 -g -fsanitize=address,undefined \
//       -fno-sanitize-recover=all sol-03-sanitizer-builds.cpp -o /tmp/ph16cpp-sol03-asan
//   # 3. TSan 构建（数据竞争；与 ASan 互斥，必须独立二进制）
//   c++ -std=c++20 -Wall -Wextra -O1 -g -fsanitize=thread \
//       sol-03-sanitizer-builds.cpp -o /tmp/ph16cpp-sol03-tsan
// 运行：三个二进制各跑一遍，预期输出相同（见下），退出码均 0：
//   sum=500500 counter=20000
#include <cstdio>
#include <mutex>
#include <numeric>
#include <thread>
#include <vector>

namespace {

// 内存负载：vector 填充 + 求和（ASan 盯着越界/UAF）
long vector_sum() {
    std::vector<int> v(1000);
    std::iota(v.begin(), v.end(), 1);
    long sum = 0;
    for (std::size_t i = 0; i < v.size(); ++i) {
        sum += v[i];
    }
    return sum;
}

// 并发负载：两线程各加 10000 次（scoped_lock 保护，TSan 盯着竞争；CP.20/CP.44）
int parallel_counter() {
    int counter = 0;
    std::mutex mtx;
    auto worker = [&counter, &mtx] {
        for (int i = 0; i < 10000; ++i) {
            const std::lock_guard<std::mutex> lock(mtx);
            ++counter;
        }
    };
    std::thread t1(worker);
    std::thread t2(worker);
    t1.join();
    t2.join();
    return counter;
}

}  // namespace

int main() {
    std::printf("sum=%ld counter=%d\n", vector_sum(), parallel_counter());
    return 0;
}
