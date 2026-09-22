/* sol-04-opt-levels.c —— 参考实现: 观察优化级别改变 UB 表现
 * 运行前提: 这是故意含 UB 的演示代码 —— 建议用 -fsanitize=undefined
 * -fno-sanitize-recover=all 编译观察 UBSan 报告; -O0/-O2 裸跑不会崩溃,
 * 但输出随优化级别变化, 不要在生产代码里依赖任何一种输出。
 * 实测(Apple clang 21.0.0): -O0 → 0; -O1/-O2 → 1;
 *   UBSan: runtime error: signed integer overflow: 2147483647 + 1 cannot
 *   be represented in type 'int'
 * 原理(主文档 4.1/4.2): 编译器假设有符号加法不会溢出, 于是 (a+1) > a 恒真,
 * -O2 把整个比较折叠成常量 1 —— 这就是"UB 可能在优化级别变化后暴露"。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 -O0 sol-04-opt-levels.c -o sol04o0
//       cc -Wall -Wextra -std=c11 -O2 sol-04-opt-levels.c -o sol04o2
// 运行：./sol04o0（输出 0）; ./sol04o2（输出 1）
// 验证状态：已验证（-O0→0、-O2→1 的差异实测; UBSan 复现报告见注释）
#include <limits.h>
#include <stdio.h>

/* 编译器假设 a+1 不会溢出: 若 a == INT_MAX 则 a+1 是 UB, UB 允许任意假设,
 * 于是 (a+1) > a 被当作恒真, -O2 下折叠成常量 1 */
static int f(int a) {
    return (a + 1) > a;
}

int main(void) {
    printf("%d\n", f(INT_MAX));
    return 0;
}
