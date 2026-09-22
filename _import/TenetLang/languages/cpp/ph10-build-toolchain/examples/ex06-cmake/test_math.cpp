// test_math.cpp —— CMake 多目标示例：测试（ctest 注册）
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 运行：ctest --test-dir build --output-on-failure（或直接 ./build/test_math）
// 验证状态：已验证（编译零警告 + ctest 通过）
#include "math.h"
#include <cstdio>

int main() {
    int failed = 0;
    if (gcd(48, 36) != 12) { std::printf("FAIL gcd(48,36)\n"); ++failed; }
    if (gcd(7, 13) != 1) { std::printf("FAIL gcd(7,13)\n"); ++failed; }
    if (!is_prime(2) || !is_prime(97)) { std::printf("FAIL is_prime pos\n"); ++failed; }
    if (is_prime(1) || is_prime(21)) { std::printf("FAIL is_prime neg\n"); ++failed; }
    if (failed == 0) std::printf("all tests pass\n");
    return failed == 0 ? 0 : 1;
}
