/* examples/ex01-strlib.c —— 手写 strlen/strcpy/strcmp/strcat（带测试）
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 ex01-strlib.c -o ex01
 * 运行：./ex01
 * 已验证：本环境编译零警告，输出与注释中期望值一致
 */
#include <stdio.h>

/* 计算字符串长度（不含 \0） */
size_t my_strlen(const char *s) {
    const char *p = s;
    while (*p) p++;
    return (size_t)(p - s);
}

/* 复制 src 到 dst（含 \0），返回 dst */
char *my_strcpy(char *dst, const char *src) {
    char *d = dst;
    while ((*d++ = *src++) != '\0')
        ;
    return dst;
}

/* 按字典序比较 s1 和 s2 */
int my_strcmp(const char *s1, const char *s2) {
    while (*s1 && *s1 == *s2) { s1++; s2++; }
    return (unsigned char)*s1 - (unsigned char)*s2;
}

/* 把 src 追加到 dst 末尾（覆盖 dst 的 \0），返回 dst */
char *my_strcat(char *dst, const char *src) {
    char *d = dst;
    while (*d) d++;                    /* 走到 dst 的 \0 */
    while ((*d++ = *src++) != '\0')    /* 从这里开始追加 src */
        ;
    return dst;
}

int main(void) {
    const char *test = "hello world";
    printf("my_strlen(\"%s\") = %zu  (期望 11)\n", test, my_strlen(test));

    char buf[64];
    my_strcpy(buf, "C pointer");
    printf("my_strcpy: \"%s\"  (期望 \"C pointer\")\n", buf);

    my_strcat(buf, " is power");
    printf("my_strcat: \"%s\"  (期望 \"C pointer is power\")\n", buf);

    printf("my_strcmp(\"abc\",\"abc\") = %d  (期望 0)\n", my_strcmp("abc", "abc"));
    printf("my_strcmp(\"abc\",\"abd\") = %d  (期望 <0)\n", my_strcmp("abc", "abd"));
    printf("my_strcmp(\"xyz\",\"abc\") = %d  (期望 >0)\n", my_strcmp("xyz", "abc"));
    return 0;
}
