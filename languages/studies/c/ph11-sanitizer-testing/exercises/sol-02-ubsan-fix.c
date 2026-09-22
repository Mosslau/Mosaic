/* sol-02-ubsan-fix.c —— 参考实现: 用 UBSan 复现并修复整数类 UB
 * 坏版本(3 处整数 UB: 有符号溢出 / INT_MIN/-1 / 1<<31)的实测报告
 * (Apple clang 21.0.0, cc -fsanitize=undefined -g, 默认 recover 报错后继续):
 *   runtime error: signed integer overflow: 2147483647 + 1 cannot be
 *     represented in type 'int'
 *   runtime error: division of -2147483648 by -1 cannot be represented in
 *     type 'int'
 *   runtime error: left shift of 1 by 31 places cannot be represented in
 *     type 'int'
 *   （三行后程序继续打印垃圾值, 退出码 0; 加 -fno-sanitize-recover=undefined
 *     则在第一处溢出直接 SIGABRT, 退出码 134——CI 里"报错即失败"靠它）
 * 修复思路: 先判断再运算; 位运算改用无符号类型并把移位位数约束在 [0, 32)。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 -fsanitize=undefined -fno-sanitize-recover=undefined sol-02-ubsan-fix.c -o sol02
// 运行：./sol02（3 处 UB 全部被拦截并打印说明, 退出码 0）
// 验证状态：已验证（-Wall -Wextra 零警告; 加 -fsanitize=undefined 运行零报告）
#include <limits.h>
#include <stdio.h>

int main(void) {
    /* 修复 1: 有符号溢出 → 先判断再运算 */
    int a = INT_MAX;
    if (a > INT_MAX - 1)
        printf("加法溢出被拦截: %d + 1 无法表示\n", a);
    else
        printf("sum = %d\n", a + 1);

    /* 修复 2: INT_MIN / -1 → 先判断除数与被除数组合（商溢出 int） */
    int m = INT_MIN, d = -1;
    if (d == -1 && m == INT_MIN)
        printf("INT_MIN / -1 被拦截(商溢出 int)\n");
    else
        printf("q = %d\n", m / d);

    /* 修复 3: 非法移位 → 位数先检查, 且位运算一律用无符号类型 */
    int n = 31;
    if (n >= 0 && n < 32)
        printf("1u << %d = %u\n", n, 1u << n);   /* 1u << 31 是定义行为 */
    else
        printf("移位位数 %d 非法\n", n);
    return 0;
}
