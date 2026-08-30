/* project/math_lib.h —— 小型数学工具库（头文件）
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 main.c math_lib.c -o mathlib
 * 已验证：本环境编译零警告
 */
#ifndef MATH_LIB_H
#define MATH_LIB_H

int add(int a, int b);
int sub(int a, int b);
int mul(int a, int b);
double divide(int a, int b);  /* b 为 0 时打印提示并返回 0.0 */
int power(int base, int exp); /* 非负整数次幂 */
int gcd(int a, int b);        /* 最大公约数（欧几里得算法） */
int lcm(int a, int b);        /* 最小公倍数，基于 gcd */

#endif /* MATH_LIB_H */
