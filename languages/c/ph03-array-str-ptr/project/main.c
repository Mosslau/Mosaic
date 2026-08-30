/* project/main.c —— 字符串处理库（演示入口 + 断言式测试）
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 main.c mystr.c -o mystr
 * 运行：./mystr
 * 已验证：本环境编译零警告，全部断言通过
 */
#include <stdio.h>
#include <assert.h>
#include "mystr.h"

int main(void) {
    /* 用 assert 验证每个函数的正确性，全部通过则打印成功 */
    assert(my_strlen("hello") == 5);
    assert(my_strlen("") == 0);

    char buf[64];
    assert(my_strcpy(buf, "abc") == buf);      /* 返回目标指针 */
    assert(my_strcmp(buf, "abc") == 0);        /* 复制内容正确 */

    assert(my_strcmp("abc", "abc") == 0);
    assert(my_strcmp("abc", "abd") < 0);
    assert(my_strcmp("xyz", "abc") > 0);

    my_strcpy(buf, "hello");
    assert(my_strcat(buf, " world") == buf);   /* 返回目标指针 */
    assert(my_strcmp(buf, "hello world") == 0);

    const char *hello = "hello world";
    assert(my_strstr(hello, "world") == &hello[6]);
    assert(my_strstr(hello, "xyz") == NULL);

    const char *abc = "abc";
    assert(my_strstr(abc, "") == abc);         /* 空子串返回原串 */

    printf("全部断言通过\n");
    return 0;
}
