/* project/mystr.c —— 字符串处理库（实现）
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 main.c mystr.c -o mystr
 * 已验证：本环境编译零警告
 */
#include "mystr.h"

size_t my_strlen(const char *s) {
    const char *p = s;
    while (*p) p++;
    return (size_t)(p - s);
}

char *my_strcpy(char *dst, const char *src) {
    char *d = dst;
    while ((*d++ = *src++) != '\0')
        ;
    return dst;
}

int my_strcmp(const char *s1, const char *s2) {
    while (*s1 && *s1 == *s2) { s1++; s2++; }
    return (unsigned char)*s1 - (unsigned char)*s2;
}

char *my_strcat(char *dst, const char *src) {
    char *d = dst;
    while (*d) d++;
    while ((*d++ = *src++) != '\0')
        ;
    return dst;
}

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
