// ex02-libstat.cpp —— 静态库成员 1：gcd / lcm
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译（归档成员）：c++ -std=c++20 -Wall -Wextra -c ex02-libstat.cpp -o ex02-libstat.o
// 归档：ar rcs libex02.a ex02-libstat.o ex02-libmath.o
// 验证状态：已验证（编译零警告）
#include "ex02-math.h"

int gcd(int a, int b) {
    while (b != 0) {
        const int t = a % b;
        a = b;
        b = t;
    }
    return a < 0 ? -a : a;   // 归一化到非负
}

int lcm(int a, int b) {
    return a / gcd(a, b) * b;
}
