/* project/main.c —— 小型数学工具库（演示入口）
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 main.c math_lib.c -o mathlib
 * 运行：./mathlib
 * 已验证：本环境编译零警告
 */
#include <stdio.h>
#include "math_lib.h"

int main(void) {
    printf("add(3, 4) = %d\n", add(3, 4));
    printf("sub(10, 3) = %d\n", sub(10, 3));
    printf("mul(6, 7) = %d\n", mul(6, 7));
    printf("divide(10, 4) = %.2f\n", divide(10, 4));
    printf("divide(1, 0) = %.2f\n", divide(1, 0));
    printf("power(2, 10) = %d\n", power(2, 10));
    printf("gcd(48, 36) = %d\n", gcd(48, 36));
    printf("lcm(4, 6) = %d\n", lcm(4, 6));
    return 0;
}
