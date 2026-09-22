// main.cpp —— Makefile 增量构建示例：入口 + 自检
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 构建/运行：make && make run（或 ./build/calc）
// 验证状态：已验证（make 构建零警告 + 运行通过 + touch 增量实测）
#include "calc.h"
#include <cstdio>

int main() {
    const int a = 6;
    const int b = 4;
    std::printf("%d+%d=%d  %d-%d=%d  %d*%d=%d\n",
                a, b, add(a, b), a, b, sub(a, b), a, b, mul(a, b));
    const bool ok = (add(a, b) == 10) && (sub(a, b) == 2) && (mul(a, b) == 24);
    std::printf("assert: %s\n", ok ? "pass" : "FAIL");
    return ok ? 0 : 1;
}
