/* vector_math.c —— ex04 C 侧实现：头文件 vector_math.h 的朴素 C 实现。
 * 由 build.rs 在构建期自动调用 clang/cc 编译成静态库，再被 Rust 绑定调用。
 * 验证环境：Apple clang 21.0.0（macOS arm64）；-Wall -Wextra 零警告。 */
#include "vector_math.h"
#include <math.h>

double vm_dot(const double *a, const double *b, size_t n) {
    double acc = 0.0;
    for (size_t i = 0; i < n; i++) {
        acc += a[i] * b[i];
    }
    return acc;
}

double vm_euclidean(const double *a, const double *b, size_t n) {
    double acc = 0.0;
    for (size_t i = 0; i < n; i++) {
        double d = a[i] - b[i];
        acc += d * d;
    }
    return sqrt(acc);
}
