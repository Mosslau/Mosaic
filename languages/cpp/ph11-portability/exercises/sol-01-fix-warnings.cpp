// sol-01-fix-warnings.cpp —— 练习 1 参考实现（修复后版本，零警告）
// 练习 1 要求：同一份代码用 Apple clang 与 Homebrew clang 分别编译，记录两家
// 告警措辞，修复到"双编译器零警告"。
//
// 修复前的故意出错代码（题目给的是这个版本）：
//   int check(int x) {
//       if (x = 42) { return x; }     // 赋值被当条件（-Wparentheses）
//       return 0;
//   }
//   int main() {
//       int a = 3, b = 4;
//       if (a < b < 0) { ... }        // 链式比较（clang 21 是 error，GCC 是 -Wparentheses 警告）
//   }
//
// 本机实测修复前两家输出（已验证）：
//   Apple clang 21.0.0（c++ -std=c++20 -Wall -c）:
//     warning: using the result of an assignment as a condition without parentheses [-Wparentheses]
//     note: place parentheses around the assignment to silence this warning
//     note: use '==' to turn this assignment into an equality comparison
//     error: chained comparison 'X < Y < Z' does not behave the same as a mathematical expression [-Wparentheses]
//     warning: result of comparison of constant 0 with expression of type 'bool' is always false [-Wtautological-constant-compare]
//     （2 warnings and 1 error generated.）
//   Homebrew clang 21.1.8 输出与 Apple clang 完全一致（同为 clang 系，诊断共享）。
//   GCC 的告警命名不同（如 -Wbool-compare），本机无 GCC，未在本环境验证。
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-01-fix-warnings.cpp -o /tmp/sol-01
// 运行：    /tmp/sol-01
// 验证状态：已验证（修复后两家编译器均零警告，输出 check=42）
#include <cstdio>

int check(int x) {
    if (x == 42) {          // 修复 1：赋值 → 相等比较
        return x;
    }
    return 0;
}

int main() {
    const int a = 3;
    const int b = 4;
    if (a < b && b < 0) {   // 修复 2：链式比较 → 显式 &&（原式恒为 false）
        std::printf("yes\n");
    }
    std::printf("check=%d\n", check(42));
    return 0;
}
