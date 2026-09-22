// race.cpp —— C++ UB 示例集：数据竞争坏/好版本（TSan 专用，独立于 ub_catalog）
// 为什么独立：TSan 与 ASan/UBSan 不能同进程共存（都拦截同一批运行时函数），
//   所以数据竞争条目不在 ub_catalog（ASan+UBSan 构建）里，单独用
//   -fsanitize=thread 编译本文件。
// 用法：./race_demo race | good
//   race  竞态版本：两线程无锁 ++shared（UB）——TSan 报 data race 并中止
//   good  修复版本：scoped_lock 保护（CP.2/CP.20）——TSan 零报告，输出确定 200000
// 运行前提：必须用 -fsanitize=thread 编译运行（Makefile: make race），勿裸跑竞态版本。
// 验证环境：Apple clang 21.0.0（c++），C++20；TSan 实测见 project/README.md 实测表
//   （Homebrew clang 21.1.8 的 TSan 运行时在本机 arm64 上不稳定（实测崩溃），未使用）
#include <cstdio>
#include <cstring>
#include <mutex>
#include <thread>

int main(int argc, char** argv) {
    const bool fixed = argc > 1 && std::strcmp(argv[1], "good") == 0;
    if (argc < 2 || (!fixed && std::strcmp(argv[1], "race") != 0)) {
        std::printf("用法: ./race_demo race | good\n");
        return 1;
    }

    int shared = 0;
    if (fixed) {
        // 修复版本：同一把互斥锁保护 ++shared
        std::mutex m;
        auto bump = [&shared, &m] {
            for (int i = 0; i < 100000; ++i) {
                std::scoped_lock lk(m);      // RAII：临界区结束自动解锁
                ++shared;
            }
        };
        std::thread a(bump);
        std::thread b(bump);
        a.join();
        b.join();
        std::printf("good: shared=%d（期望 200000，锁保护下确定）\n", shared);
    } else {
        // 竞态版本：两线程无同步并发 ++shared —— 数据竞争（UB）
        auto bump = [&shared] {
            for (int i = 0; i < 100000; ++i) {
                ++shared;                    // 非原子读-改-写，无锁保护
            }
        };
        std::thread a(bump);
        std::thread b(bump);
        a.join();
        b.join();
        std::printf("race: shared=%d（竞态下值不定；TSan 将报 data race）\n", shared);
    }
    return 0;
}
