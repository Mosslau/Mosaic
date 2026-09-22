/* examples/ex04-math-utils/math_utils.h —— 多文件项目：小型数学工具库（头文件）
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 main.c math_utils.c -o ex04
 * 运行：./ex04
 * 已验证：本环境编译零警告，输出 add(2, 3) = 5 / multiply(4, 5) = 20 / power(2, 10) = 1024
 */
#ifndef MATH_UTILS_H
#define MATH_UTILS_H

int add(int a, int b);
int multiply(int a, int b);
int power(int base, int exp);

#endif /* MATH_UTILS_H */
