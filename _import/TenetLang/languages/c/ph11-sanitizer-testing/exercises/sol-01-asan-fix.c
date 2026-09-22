/* sol-01-asan-fix.c —— 参考实现: 用 ASan 复现并修复越界
 * 坏版本(故意 arr[3]=100 越界写)的实测报告(Apple clang 21.0.0,
 * cc -Wall -Wextra -std=c11 -fsanitize=address -g):
 *   ERROR: AddressSanitizer: stack-buffer-overflow on address ... at pc ...
 *   WRITE of size 4 at ... thread T0
 *   SUMMARY: AddressSanitizer: stack-buffer-overflow (...) in demo+0x...
 *   （退出码 134; 编译期另触发 -Warray-bounds 警告——编译器内建的静态检查）
 * 修复思路: 裸下标访问全部收进"带边界检查的接口", 越界请求返回 -1
 *   而不是访问 arr[i]——把"长度"与"访问"绑定, 越界从 UB 变成可处理的行为。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 -fsanitize=address -g sol-01-asan-fix.c -o sol01
// 运行：./sol01（输出 sum=6 与 越界被拦截 两行, 退出码 0）
// 验证状态：已验证（-Wall -Wextra 零警告; 加 -fsanitize=address 运行零报告）
#include <stddef.h>
#include <stdio.h>

/* 带边界检查的求和: n > len 时返回 -1, 绝不访问 arr[i] 越界 */
static int sum_first(const int *arr, size_t len, size_t n, long *out) {
    if (arr == NULL || out == NULL) return -1;
    if (n > len) return -1;               /* 边界检查: 越界请求直接拒绝 */
    long s = 0;
    for (size_t i = 0; i < n; i++)
        s += arr[i];
    *out = s;
    return 0;
}

int main(void) {
    int arr[3] = {1, 2, 3};
    long s = 0;
    if (sum_first(arr, 3, 3, &s) == 0)
        printf("sum = %ld\n", s);          /* 边界内: 正常求和 */
    if (sum_first(arr, 3, 5, &s) != 0)
        printf("n=5 越界被拦截\n");        /* 越界请求: 返回 -1 而非 UB */
    return 0;
}
