/* exercises/sol-01-string-utils.c —— 字符串工具库参考实现
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 sol-01-string-utils.c -o sol01
 * 运行：./sol01
 * 已验证：本环境编译零警告
 */
#include <stdio.h>

int my_strlen(const char *s) {
    int len = 0;
    while (s[len] != '\0') len++;
    return len;
}

void my_strcpy(char *dest, const char *src) {
    int i = 0;
    while ((dest[i] = src[i]) != '\0') i++;
}

int my_strcmp(const char *a, const char *b) {
    while (*a && (*a == *b)) { a++; b++; }
    return (unsigned char)*a - (unsigned char)*b;
}

int main(void) {
    char buf[64];
    printf("my_strlen(\"hello\") = %d\n", my_strlen("hello"));

    my_strcpy(buf, "world");
    printf("my_strcpy 后 buf = %s\n", buf);

    printf("my_strcmp(\"abc\",\"abc\") = %d\n", my_strcmp("abc", "abc"));
    printf("my_strcmp(\"abc\",\"abd\") = %d\n", my_strcmp("abc", "abd"));
    return 0;
}
