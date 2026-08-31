// math.cpp —— CMake 多目标示例：实现
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 构建：由 ex06-cmake/CMakeLists.txt 的 add_library(math ...) 负责
#include "math.h"

int gcd(int a, int b) {
    while (b != 0) {
        const int t = a % b;
        a = b;
        b = t;
    }
    return a < 0 ? -a : a;
}

bool is_prime(int n) {
    if (n < 2) return false;
    for (int d = 2; static_cast<long long>(d) * d <= n; ++d) {
        if (n % d == 0) return false;
    }
    return true;
}
