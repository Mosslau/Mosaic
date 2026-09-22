/* examples/ex03-strstr.c —— 子串查找（朴素匹配）
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 ex03-strstr.c -o ex03
 * 运行：./ex03
 * 已验证：本环境编译零警告，输出 找到 "world"，偏移 = 6
 */
#include <stdio.h>

char *my_strstr(const char *str, const char *sub) {
    if (*sub == '\0') return (char *)str;
    while (*str) {
        const char *s = str, *p = sub;
        while (*s && *p && *s == *p) { s++; p++; }
        if (*p == '\0') return (char *)str;
        str++;
    }
    return NULL;
}

int main(void) {
    const char *text = "hello world, welcome to C";
    const char *pattern = "world";
    char *pos = my_strstr(text, pattern);
    if (pos)
        printf("找到 \"%s\"，偏移 = %td\n", pattern, pos - text);
    else
        printf("未找到 \"%s\"\n", pattern);
    return 0;
}
