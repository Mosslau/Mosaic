/* examples/ex01-basic-func.c —— 基础函数：声明与定义、按值传递
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 ex01-basic-func.c -o ex01
 * 运行：./ex01
 * 已验证：本环境编译零警告，输出 add(10, 20) = 30 / max(10, 20) = 20
 */
#include <stdio.h>

int add(int a, int b);
int max(int a, int b);

int main(void) {
    int x = 10, y = 20;
    printf("add(%d, %d) = %d\n", x, y, add(x, y));
    printf("max(%d, %d) = %d\n", x, y, max(x, y));
    return 0;
}

int add(int a, int b) {
    return a + b;
}

int max(int a, int b) {
    return (a > b) ? a : b;
}
