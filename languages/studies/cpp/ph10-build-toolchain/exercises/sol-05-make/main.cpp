// main.cpp —— 练习 5 参考实现：入口 + 自检
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 构建/运行：make && make run
// 增量验证（touch 实测，先 sleep 1）：见 Makefile 头部注释
// 验证状态：已验证（make 构建零警告 + 运行断言通过 + touch 增量实测
//           —— touch calc.cpp 只重编 calc.o、touch calc.h 两个 .o 都重编）
#include "calc.h"
#include <cstdio>

int main() {
    const int a = 9;
    const int b = 3;
    std::printf("%d+%d=%d  %d-%d=%d  %d*%d=%d\n",
                a, b, add(a, b), a, b, sub(a, b), a, b, mul(a, b));
    const bool ok = (add(a, b) == 12) && (sub(a, b) == 6) && (mul(a, b) == 27);
    std::printf("assert: %s\n", ok ? "pass" : "FAIL");
    return ok ? 0 : 1;
}
