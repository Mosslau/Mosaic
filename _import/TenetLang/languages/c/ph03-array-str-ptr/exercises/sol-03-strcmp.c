/* exercises/sol-03-strcmp.c —— 手写 strcmp 参考实现
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 sol-03-strcmp.c -o sol03
 * 运行：./sol03
 * 已验证：本环境编译零警告
 */
#include <stdio.h>

int my_strcmp(const char *s1, const char *s2) {
    while (*s1 && *s1 == *s2) { s1++; s2++; }
    return (unsigned char)*s1 - (unsigned char)*s2;
}

int main(void) {
    printf("my_strcmp(\"abc\",\"abc\") = %d (期望 0)\n", my_strcmp("abc", "abc"));
    printf("my_strcmp(\"abc\",\"abd\") = %d (期望 <0)\n", my_strcmp("abc", "abd"));
    printf("my_strcmp(\"xyz\",\"abc\") = %d (期望 >0)\n", my_strcmp("xyz", "abc"));
    return 0;
}
