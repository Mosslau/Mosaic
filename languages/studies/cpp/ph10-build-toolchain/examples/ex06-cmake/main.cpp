// main.cpp —— CMake 多目标示例：入口
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 构建/运行：cmake -B build && cmake --build build && ./build/app
// 验证状态：已验证（Debug/Release 双构建零警告 + 运行通过）
#include "math.h"
#include <cstdio>

int main() {
    const int g = gcd(48, 36);
    std::printf("gcd(48,36)=%d  is_prime(17)=%d  is_prime(21)=%d\n",
                g, is_prime(17), is_prime(21));
    const bool ok = (g == 12) && is_prime(17) && !is_prime(21);
    std::printf("assert: %s\n", ok ? "pass" : "FAIL");
    return ok ? 0 : 1;
}
