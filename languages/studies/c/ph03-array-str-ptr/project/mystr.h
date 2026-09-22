/* project/mystr.h —— 字符串处理库（头文件）
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 main.c mystr.c -o mystr
 * 已验证：本环境编译零警告
 */
#ifndef MYSTR_H
#define MYSTR_H

#include <stddef.h>

size_t my_strlen(const char *s);
char *my_strcpy(char *dst, const char *src);
int my_strcmp(const char *s1, const char *s2);
char *my_strcat(char *dst, const char *src);
char *my_strstr(const char *str, const char *sub);

#endif /* MYSTR_H */
