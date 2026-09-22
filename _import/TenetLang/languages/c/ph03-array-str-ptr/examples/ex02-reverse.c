/* examples/ex02-reverse.c —— 数组反转与字符串反转（双指针）
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 ex02-reverse.c -o ex02
 * 运行：./ex02
 * 已验证：本环境编译零警告，输出 数组反转 6 5 4 3 2 1 / 字符串反转 "retniop"
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
    while (*right) right++;      /* right 走到 \0 */
    right--;                     /* right 指向最后一个字符 */
    while (left < right) {
        char tmp = *left;
        *left = *right;
        *right = tmp;
        left++; right--;
    }
}

int main(void) {
    int arr[] = {1, 2, 3, 4, 5, 6};
    size_t n = sizeof(arr) / sizeof(arr[0]);

    reverse_array(arr, n);
    printf("数组反转: ");
    for (size_t i = 0; i < n; i++) printf("%d ", arr[i]);
    printf(" (期望 6 5 4 3 2 1)\n");

    char s1[] = "pointer";
    reverse_string(s1);
    printf("字符串反转: \"%s\"  (期望 \"retniop\")\n", s1);
    return 0;
}
