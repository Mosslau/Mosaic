/* exercises/sol-04-reverse-strstr.c —— 数组反转/字符串反转/子串查找 参考实现
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 sol-04-reverse-strstr.c -o sol04
 * 运行：./sol04
 * 已验证：本环境编译零警告
 */
#include <stdio.h>

void reverse_array(int *arr, size_t n) {
    int *left = arr, *right = arr + n - 1;
    while (left < right) {
        int tmp = *left;
        *left = *right;
        *right = tmp;
        left++; right--;
    }
}

void reverse_string(char *s) {
    if (s == NULL || *s == '\0') return;
    char *left = s, *right = s;
    while (*right) right++;
    right--;
    while (left < right) {
        char tmp = *left;
        *left = *right;
        *right = tmp;
        left++; right--;
    }
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

int main(void) {
    int arr[] = {1, 2, 3, 4, 5, 6};
    size_t n = sizeof(arr) / sizeof(arr[0]);
    reverse_array(arr, n);
    printf("数组反转: ");
    for (size_t i = 0; i < n; i++) printf("%d ", arr[i]);
    printf("(期望 6 5 4 3 2 1)\n");

    char s1[] = "pointer";
    reverse_string(s1);
    printf("字符串反转: \"%s\" (期望 \"retniop\")\n", s1);

    char *pos = my_strstr("hello world", "world");
    if (pos)
        printf("找到 \"world\"，偏移 = %td (期望 6)\n", pos - "hello world");
    return 0;
}
