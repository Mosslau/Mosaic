/* sol-02-uaf-fix.c —— 参考实现: 修复越界写与 use-after-free
 * 坏版本(故意)的实测报告(Apple clang 21.0.0, cc -fsanitize=address):
 *   ERROR: AddressSanitizer: stack-buffer-overflow on address ... WRITE of size 4
 *   ERROR: AddressSanitizer: heap-use-after-free on address ... READ of size 4
 *   ERROR: AddressSanitizer: attempting double-free on ...
 * 每处 UB 都会让 ASan 中止, 需逐个注释掉才能看到下一个报告 —— 这正是
 * "逐个修复、逐个复现"的练习方式。
 * 修复思路: 索引先检查; free 后立即置 NULL —— free(NULL) 合法, 置 NULL 后
 * 既防"再解引用"也把"重复 free"变成无害的 free(NULL)。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-02-uaf-fix.c -o sol02
// 运行：./sol02（越界被拦截、释放后不再访问, 退出码 0）
// 验证状态：已验证（-Wall -Wextra 零警告; 修复版加 -fsanitize=address 运行零报告）
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    /* 修复 1: 越界写 → 读写前检查索引(用 size_t 与长度比较, 防 off-by-one) */
    int arr[3] = {1, 2, 3};
    size_t i = 3;                    /* 想写"第 4 个元素" */
    if (i < 3)
        arr[i] = 100;
    else
        printf("越界写被拦截: i=%zu 超出长度 3\n", i);

    /* 修复 2: use-after-free → free 后立即置 NULL, 不再解引用 */
    int *p = malloc(sizeof(int));
    if (p == NULL) return 1;
    *p = 7;
    free(p);
    p = NULL;                        /* 置 NULL: 再解引用会立即崩(可发现), 重复 free 无害 */
    printf("p 已释放并置 NULL: 无 use-after-free、无 double free\n");
    return 0;
}
