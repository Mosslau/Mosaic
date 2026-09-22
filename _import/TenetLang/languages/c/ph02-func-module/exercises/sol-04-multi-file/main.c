/* exercises/sol-04-multi-file/main.c —— 拆分单文件程序：入口
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 main.c calculator.c -o sol04
 * 运行：./sol04
 * 已验证：本环境编译零警告
 */
#include <stdio.h>
#include "calculator.h"

int main(void) {
    printf("add(3, 4) = %d\n", add(3, 4));
    printf("sub(10, 3) = %d\n", sub(10, 3));
    printf("mul(6, 7) = %d\n", mul(6, 7));
    printf("divide(10, 4) = %.2f\n", divide(10, 4));
    printf("divide(1, 0) = %.2f\n", divide(1, 0));
    return 0;
}
