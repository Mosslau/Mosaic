// ex02-libmath.cpp —— 静态库成员 2：is_prime / factorial
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译（归档成员）：c++ -std=c++20 -Wall -Wextra -c ex02-libmath.cpp -o ex02-libmath.o
// 归档：ar rcs libex02.a ex02-libstat.o ex02-libmath.o
// 验证状态：已验证（编译零警告）
#include "ex02-math.h"

bool is_prime(int n) {
    if (n < 2) return false;
    for (int d = 2; static_cast<long long>(d) * d <= n; ++d) {
        if (n % d == 0) return false;
    }
    return true;
}

long long factorial(int n) {
    long long r = 1;
    for (int i = 2; i <= n; ++i) r *= i;
    return r;
}
