// sol-05-uninit-fix.cpp —— 练习 5 参考实现：未初始化变量的识别与修复
// 练习 5 要求：识别“读取未初始化变量”的 UB（C++ 中读内置类型的不确定值是不确定行为/UB
//   ——[dcl.init] 不确定值；ES.20：总是初始化对象），用编译期警告定位并修复（覆盖 roadmap
//   学习内容「未初始化变量」）。
//
// 坏版本（有 bug，勿这样写）：
//   struct Stats { int hits; int misses; };   // 平凡类型：缺省初始化不置位
//   int x;                                    // 未初始化局部变量
//   Stats s;                                  // hits/misses 未初始化
//   std::printf("x=%d s.hits=%d\n", x, s.hits);   // 读不确定值
//
// 本机实测（坏版本，Apple clang 21.0.0，-O0~-O2 均触发）：
//   编译警告：warning: variable 'x' is uninitialized when used here [-Wuninitialized]
//            （note: initialize the variable 'x' to silence this warning —— 编译器第一道防线）
//   运行输出：x=-248938240 s.hits=-248938408（垃圾值；两次运行相同纯属栈布局巧合，
//             换调用上下文/编译器/优化级别即变 —— 不确定值的“确定性”不可依赖）
//   注：成员未初始化（s.hits）多数情况下编译器不警告 —— 这正是默认成员初始化要上场的地方。
//
// 修复思路（C++ 的两道编译期护栏，ES.20/ES.23）：
//   1. 局部变量声明即初始化（int x = 0; / int x{};）；
//   2. 成员用默认成员初始化器（int hits = 0;）——构造对象即全初始化，杜绝“忘了初始化成员”。
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-05-uninit-fix.cpp -o /tmp/ph15-sol-05
// 运行：    /tmp/ph15-sol-05
// 验证状态：已验证（两种编译器零警告、输出一致；+ASan+UBSan 复跑零报告）
#include <cstdio>

struct Stats {
    int hits = 0;      // 默认成员初始化器：任何构造路径都不留未初始化成员（ES.20）
    int misses = 0;
    Stats() = default; // 显式默认构造：仍会应用上面的成员初始化器
};

int main() {
    std::printf("[A] 坏版本实测（见文件头）：-Wuninitialized 编译警告触发；\n");
    std::printf("    运行输出垃圾值（x=-248938240 s.hits=-248938408，值随环境而变）\n");

    std::printf("[B] 修复：声明即初始化 + 默认成员初始化器\n");
    {
        int x = 0;                           // 声明即初始化
        if (x > 3) {
            std::printf("    x > 3 分支\n");
        } else {
            std::printf("    x=%d（初始化后分支确定，输出稳定）\n", x);
        }
    }
    {
        Stats s;                             // 默认成员初始化器接管：hits/misses 必为 0
        std::printf("    Stats s: hits=%d misses=%d（任何构造路径都初始化）\n",
                    s.hits, s.misses);
    }
    std::printf("[C] 要点：编译器 -Wuninitialized 能拦一部分局部变量，但拦不全（如成员）；\n");
    std::printf("    运行时 ASan/UBSan 不查未初始化 —— 声明即初始化是唯一可靠的防线\n");
    return 0;
}
// 本机实测（两种编译器一致，零警告；+ASan+UBSan 零报告，退出码 0）：
//   [B] x=0（初始化后分支确定，输出稳定）
//       Stats s: hits=0 misses=0
