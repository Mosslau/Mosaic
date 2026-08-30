/* exercises/sol-02-strcpy.c —— 手写 strcpy 参考实现
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 sol-02-strcpy.c -o sol02
 * 运行：./sol02
 * 已验证：本环境编译零警告
 */
#include <stdio.h>

char *my_strcpy(char *dst, const char *src) {
    char *d = dst;
    while ((*d++ = *src++) != '\0')
        ;
    return dst;
}

int main(void) {
    char buf[64];
    my_strcpy(buf, "C pointer");
    printf("my_strcpy: \"%s\" (期望 \"C pointer\")\n", buf);
    return 0;
}
