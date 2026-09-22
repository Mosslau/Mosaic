/* project/math_lib.c —— 小型数学工具库（实现）
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 main.c math_lib.c -o mathlib
 * 已验证：本环境编译零警告
 */
#include <stdio.h>
#include "math_lib.h"

int add(int a, int b) { return a + b; }
int sub(int a, int b) { return a - b; }
int mul(int a, int b) { return a * b; }

double divide(int a, int b) {
    if (b == 0) {
        printf("错误: 除数为零\n");
        return 0.0;
    }
    return (double)a / b;
}

/* static 限制为内部链接：仅本文件可见 */
static int power_helper(int base, int exp) {
    if (exp == 0) return 1;
    return base * power_helper(base, exp - 1);
}

int power(int base, int exp) {
    if (exp < 0) return 0;
    return power_helper(base, exp);
}

int gcd(int a, int b) {
    if (a < 0) a = -a;
    if (b < 0) b = -b;
    while (b != 0) {
        int t = a % b;
        a = b;
        b = t;
    }
    return a;
}

int lcm(int a, int b) {
    if (a == 0 || b == 0) return 0;
    return a / gcd(a, b) * b;  /* 先除后乘，避免溢出 */
}
