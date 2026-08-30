/* exercises/sol-04-multi-file/calculator.c —— 拆分单文件程序：实现
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 main.c calculator.c -o sol04
 * 已验证：本环境编译零警告
 */
#include "calculator.h"

int add(int a, int b) { return a + b; }
int sub(int a, int b) { return a - b; }
int mul(int a, int b) { return a * b; }

double divide(int a, int b) {
    if (b == 0) return 0.0;
    return (double)a / b;
}
