// ex05-data-race.cpp —— 数据竞争：C++ 内存模型下的未定义行为
// 主题：两个线程无同步地读写同一非原子对象 = 数据竞争（data race），C++ 标准明确
//       [intro.races]：数据竞争是未定义行为——不是“结果不确定”，是编译器可做任何
//       假设（roadmap 必会概念）。TSan（-fsanitize=thread）是运行时检测工具。
// 运行前提（本文件两个变体都必须用 -fsanitize=thread 编译，勿裸跑）：
//   默认（无 -D）     竞态版本：两线程无锁 ++shared → TSan 报 data race 并中止
//   -DEX05_FIXED      修复版本：scoped_lock 保护 → TSan 零报告，输出确定 200000
//   裸跑对照（不带 TSan）：-O0 下竞态版本退出码 0 但值不定（本机 6 次实测：
//   122984 / 117974 / 120359 / 112912 / 126519 / 110862，均小于 200000）；
//   -O1 下编译器按“无跨线程修改”假设把 ++shared 累加优化进寄存器，实测 6 次
//   恰为 200000 —— 两种“碰巧对”都不能证明无竞态，必须 TSan 复跑（修复版恒 200000）。
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra -O1 -g -fsanitize=thread ex05-data-race.cpp -o /tmp/ph15-ex05
// 运行：    /tmp/ph15-ex05              （竞态版本：TSan 报告）
//           /tmp/ph15-ex05-fixed        （-DEX05_FIXED 版本：零报告）
// 验证状态：已验证（两个变体均零警告；TSan 报告实测记录于本文件底部注释）
#include <cstdio>
#include <mutex>
#include <thread>

int main() {
#if defined(EX05_FIXED)
    // 修复版本：同一把互斥锁保护 ++shared（CP.2 避免数据竞争；CP.20 RAII 锁）
    int shared = 0;
    std::mutex m;
    auto bump = [&shared, &m] {
        for (int i = 0; i < 100000; ++i) {
            std::scoped_lock lk(m);        // RAII：临界区结束自动解锁
            ++shared;
        }
    };
#else
    // 竞态版本：两线程无同步并发 ++shared —— 数据竞争（UB）
    int shared = 0;
    auto bump = [&shared] {
        for (int i = 0; i < 100000; ++i) {
            ++shared;                      // 非原子读-改-写，无锁保护
        }
    };
#endif
    std::thread a(bump);
    std::thread b(bump);
    a.join();
    b.join();
#if defined(EX05_FIXED)
    std::printf("fixed: shared=%d（期望 200000，锁保护下确定）\n", shared);
#else
    std::printf("race:  shared=%d（竞态下值不定：常因丢失更新小于 200000，-O1+ 编译下可能被优化为 200000）\n", shared);
#endif
    return 0;
}
// 本机实测（Apple clang 21.0.0，-O1 -g -fsanitize=thread；两变体 -Wall -Wextra 零警告）：
//   [竞态版本] TSan 报告并中止（退出码 134）：
//     WARNING: ThreadSanitizer: data race (pid=...)
//       Write of size 4 at 0x... by thread T2:  ... ++shared ...
//       Previous write of size 4 ... by thread T1:  （线程号随运行调度变化）
//       两线程同一地址的读改写无同步 —— 报告给出冲突双方与位置
//     （stdout 先打印 race: shared=xxxxx，随后 TSan 报告中止）
//   [-DEX05_FIXED] stdout: fixed: shared=200000；stderr 空（零报告），退出码 0
//   [裸跑对照] -O0 裸跑（无 TSan）竞态版本退出码 0 但 shared 值不定（本机 6 次实测：
//     122984/117974/120359/112912/126519/110862，均小于 200000）；-O1 裸跑实测 6 次
//     恰为 200000（编译器把累加优化进寄存器）——
//     “碰巧对”正是竞态危险之处：必须 TSan 复跑，不能靠裸跑结果判断
//   （本环境 TSan 实测用 Apple clang 21.0.0（c++）：报告完整、退出码 134；
//     Homebrew clang 21.1.8 的 TSan 运行时在本机 arm64 上不稳定（实测崩溃，
//     exit 139），TSan 验证以 Apple clang 为准；TSan 与 ASan 不能同进程共存，
//     工程化组合见 ph16）
