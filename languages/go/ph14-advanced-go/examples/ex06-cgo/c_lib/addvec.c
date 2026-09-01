/*
 * addvec.c —— ph14-advanced-go 示例 6 的 C 库实现。
 * 验证环境：Apple clang 21.0.0（本机 cc），零第三方依赖。
 * 构建（在 c_lib/ 目录下）：
 *   cc -c -o /tmp/addvec.o addvec.c
 *   ar rcs /tmp/libaddvec.a /tmp/addvec.o
 * 或用一行：cc -c addvec.c && ar rcs /tmp/libaddvec.a addvec.o
 */
#include "addvec.h"

void addvec(const int *a, const int *b, int *out, size_t n) {
    for (size_t i = 0; i < n; i++) {
        out[i] = a[i] + b[i];
    }
}

int add(int a, int b) {
    return a + b;
}
