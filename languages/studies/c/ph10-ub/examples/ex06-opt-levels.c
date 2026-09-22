/* ex06-opt-levels.c —— 优化级别改变 UB 表现（UB 演示）
 * 运行前提: 建议用 -fsanitize=undefined -fno-sanitize-recover=all 编译观察
 * UBSan 报告; -O0/-O2 裸跑不会崩溃但包含 UB, 输出随优化级别变化(本环境实测
 * -O0 → 0, -O1/-O2 → 1)。不要在生产代码里依赖任何一种输出。
 * 教学点: 编译器假设有符号加法不会溢出, 于是把 (a+1) > a 常量折叠为恒真(1);
 * 这正是"UB 可能在优化级别变化后暴露"(roadmap 必会概念)的活教材。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 -O0 ex06-opt-levels.c -o ex06o0   （-O2 同理换 -o ex06o2）
//       cc -Wall -Wextra -std=c11 -O1 -fsanitize=undefined -fno-sanitize-recover=all -g ex06-opt-levels.c -o ex06ub
// 运行：./ex06o0（输出 0）; ./ex06o2（输出 1）; ./ex06ub（UBSan 报错中止）
// 验证状态：已验证（-O0→0、-O1/-O2→1; UBSan 报 signed integer overflow 并中止,
//           见主文档 6 章示例 6）
#include <limits.h>
#include <stdio.h>

/* 编译器假设 a+1 不会溢出: 若 a == INT_MAX 则 a+1 是 UB, 而 UB 允许任意假设,
 * 于是 (a+1) > a 被当作恒真, -O2 下整个比较折叠成常量 1 */
static int f(int a) {
    return (a + 1) > a;
}

int main(void) {
    printf("%d\n", f(INT_MAX));
    return 0;
}
