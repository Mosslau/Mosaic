/* exercises/sol-01-strlen.c —— 手写 strlen 参考实现
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 sol-01-strlen.c -o sol01
 * 运行：./sol01
 * 已验证：本环境编译零警告
 */
#include <stdio.h>

size_t my_strlen(const char *s) {
    const char *p = s;
    while (*p) p++;
    return (size_t)(p - s);
}

int main(void) {
    printf("my_strlen(\"hello\") = %zu (期望 5)\n", my_strlen("hello"));
    printf("my_strlen(\"\") = %zu (期望 0)\n", my_strlen(""));
    return 0;
}
