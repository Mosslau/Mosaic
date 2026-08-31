/* ex04-feature-macros.c —— 特征宏检测:
 * __STDC_VERSION__ 判 C 标准版本(C99 起定义), 平台宏(_WIN32/__linux__/__APPLE__)
 * 与架构宏(__x86_64__/__aarch64__)由编译器预定义; 用 -std=c99/c11/c17 对比输出
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 ex04-feature-macros.c -o ex04
// 运行：./ex04；或分别用 -std=c99 / -std=c17 重编对比 C 标准输出
// 验证状态：已验证（-std=c99→C99、-std=c11→C11、-std=c17→C17 输出正确）
#include <stdio.h>

int main(void) {
#if defined(__STDC_VERSION__)
    printf("C 标准: C%d\n", (int)(__STDC_VERSION__ / 100 % 100));
#else
    printf("C 标准: C89 或更早\n");
#endif
#if defined(_WIN32)
    printf("平台: Windows\n");
#elif defined(__linux__)
    printf("平台: Linux\n");
#elif defined(__APPLE__)
    printf("平台: macOS\n");
#else
    printf("平台: 其他\n");
#endif
#if defined(_POSIX_C_SOURCE)
    printf("POSIX 可见级别: %ld\n", (long)_POSIX_C_SOURCE);
#else
    printf("POSIX 可见级别: 未定义\n");
#endif
#if defined(__x86_64__) || defined(_M_X64)
    printf("架构: x86-64\n");
#elif defined(__aarch64__)
    printf("架构: AArch64\n");
#else
    printf("架构: 其他\n");
#endif
    return 0;
}
