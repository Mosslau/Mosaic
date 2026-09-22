// ex02-main.cpp —— 静态库消费者：链接 libex02.a
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译+链接：c++ -std=c++20 -Wall -Wextra ex02-main.cpp libex02.a -o ex02-app
// 运行：./ex02-app（全部断言通过退出码 0）
// 说明：本文件只引用 gcd/lcm，is_prime/factorial 所在成员 ex02-libmath.o
//       未被引用——链接器按需抽取，可执行文件里没有这两个符号（nm 验证）。
// 验证状态：已验证（编译零警告 + 运行通过 + nm 按需抽取验证）
#include "ex02-math.h"
#include <cstdio>

int main() {
    const int g = gcd(48, 36);
    const int l = lcm(6, 8);
    std::printf("gcd(48,36)=%d  lcm(6,8)=%d\n", g, l);
    const bool ok = (g == 12) && (l == 24);
    std::printf("assert: %s\n", ok ? "pass" : "FAIL");
    return ok ? 0 : 1;
}
