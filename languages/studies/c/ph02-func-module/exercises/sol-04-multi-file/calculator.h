/* exercises/sol-04-multi-file/calculator.h —— 拆分单文件程序：头文件
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 main.c calculator.c -o sol04
 * 已验证：本环境编译零警告
 */
#ifndef CALCULATOR_H
#define CALCULATOR_H

int add(int a, int b);
int sub(int a, int b);
int mul(int a, int b);
double divide(int a, int b);  /* b 为 0 时返回 0.0 */

#endif /* CALCULATOR_H */
