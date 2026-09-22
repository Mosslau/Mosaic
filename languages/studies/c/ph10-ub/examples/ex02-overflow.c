/* ex02-overflow.c —— 有符号整数溢出 vs 无符号回绕（UB 演示）
 * 运行前提: 必须用 cc -fsanitize=undefined -fno-sanitize-recover=all 编译运行,
 * 否则勿运行 —— 有符号溢出是 UB, 结果随优化级别/编译器变化, 无意义。
 * 演示顺序: 先打印无符号回绕(定义行为, 稳定), 再触发有符号溢出(UBSan 报错中止)。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 -fsanitize=undefined -fno-sanitize-recover=all -g ex02-overflow.c -o ex02
// 运行：./ex02（先输出 u = 4294967295, 随后 UBSan 报 signed integer overflow 并中止）
// 验证状态：已验证（实测报告见主文档 6 章示例 2; 无符号回绕不报错, 有符号溢出中止）
#include <limits.h>
#include <stdio.h>

int main(void) {
    unsigned int u = 0u - 1u;      /* 无符号回绕: 定义行为, UBSan 不报 */
    printf("u = %u\n", u);         /* 稳定输出 4294967295 (UINT_MAX) */

    int a = INT_MAX;
    a = a + 1;                     /* UB: 有符号整数溢出 */
    printf("a = %d\n", a);         /* 到不了这行: -fno-sanitize-recover=all 在溢出处中止 */
    return 0;
}
