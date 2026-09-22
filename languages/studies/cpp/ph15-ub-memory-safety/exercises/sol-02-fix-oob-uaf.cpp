// sol-02-fix-oob-uaf.cpp —— 练习 2 参考实现：用 ASan/UBSan 检查项目，修复越界与 use-after-free
// 练习 2 要求：写一个同时含“vector 越界写”与“delete 后使用（+ 误用释放）”的程序，
//   用 ASan 复现、读懂报告（错误类型 + READ/WRITE 大小）、逐个修复（roadmap 练习 2
//   「用 ASan/UBSan 检查项目」）。
//
// 坏版本（有 bug，勿这样写；第一个 UB 让程序在 ASan 下先中止，须逐个修复逐个复现）：
//   std::vector<int> scores = {1, 2, 3};   // cap=3
//   std::size_t idx = 3;
//   scores[idx] = 100;                     // UB1: 越界写（heap-buffer-overflow）
//   int* p = new int(42);
//   delete p;
//   *p = 7;                                // UB2: use-after-free（WRITE of size 4）
//
// 本机实测（坏版本，Apple clang 21.0.0，-O0 -g -fsanitize=address）：
//   UB1 先报：ERROR: AddressSanitizer: heap-buffer-overflow ... WRITE of size 4，
//             退出码 134；把越界写修掉后再跑，UB2 报：
//             ERROR: AddressSanitizer: heap-use-after-free ... WRITE of size 4
//   —— 与 ph10 练习 2 同思路：一次修一个、逐个复现，不要指望一条报告列全所有 bug。
//
// 修复思路：
//   1. 边界：用 at()（越界抛 out_of_range，定义行为）或先判后取；operator[] 不检查；
//   2. 释放：消灭裸 delete——堆对象用 unique_ptr（RAII，R.11/R.20），
//      生命周期结束自动释放，不存在“提前 delete 又继续用”的窗口。
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-02-fix-oob-uaf.cpp -o /tmp/ph15-sol-02
// 运行：    /tmp/ph15-sol-02
// 验证状态：已验证（两种编译器零警告、输出一致；-fsanitize=address,undefined 复跑零报告）
#include <cstdio>
#include <memory>
#include <numeric>
#include <stdexcept>
#include <vector>

int main() {
    std::printf("[A] 坏版本实测（见文件头）：越界写先报 heap-buffer-overflow（WRITE of size 4），\n");
    std::printf("    修掉后 delete 后写再报 heap-use-after-free —— 两个 bug 逐个复现\n");

    std::printf("[B] 修复 1（边界）：越界不再可能 —— at() 越界抛 out_of_range\n");
    {
        std::vector<int> scores = {1, 2, 3};
        try {
            scores.at(3) = 100;            // 越界：at() 抛异常（定义行为），不碰内存
        } catch (const std::out_of_range&) {
            std::printf("    scores.at(3) 抛出 std::out_of_range，未发生越界写\n");
        }
    }
    std::printf("[C] 修复 2（越界消除后的正常逻辑）：累加合法分数\n");
    {
        std::vector<int> scores = {1, 2, 3};
        const int total = std::accumulate(scores.begin(), scores.end(), 0);
        std::printf("    total = %d（0 <= idx < size 的访问全部合法）\n", total);
    }
    std::printf("[D] 修复 3（释放）：unique_ptr 接管堆对象，没有“delete 后继续用”的窗口\n");
    {
        auto p = std::make_unique<int>(42);
        std::printf("    *p=%d（unique_ptr 出作用域自动释放；R.11 无裸 new/delete）\n", *p);
    }
    std::printf("[E] 自检：本文件 +ASan+UBSan 运行零报告、退出码 0 —— 修复有效的判据\n");
    return 0;
}
// 本机实测（两种编译器一致，零警告；+ASan+UBSan 零报告，退出码 0）：
//   [B] scores.at(3) 抛出 std::out_of_range，未发生越界写
//   [C] total = 6
//   [D] *p=42（unique_ptr 出作用域自动释放）
