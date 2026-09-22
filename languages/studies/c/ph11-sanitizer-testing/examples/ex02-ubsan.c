/* ex02-ubsan.c —— UBSan 抓逻辑型 UB: 有符号溢出 与 非法移位
 * 运行前提: 必须用 -fsanitize=undefined 编译运行, 否则勿运行
 *   （裸跑的 b/s 只是"碰巧回绕"的垃圾值, 输出无意义）
 * 编译（默认形态, 报错后继续）:
 *   cc -Wall -Wextra -std=c11 -fsanitize=undefined -g ex02-ubsan.c -o ex02
 * 运行: ./ex02 → 打印两条 runtime error 后继续执行, 退出码 0
 * 编译（中止形态, CI 里"报错即失败"靠它）:
 *   cc -Wall -Wextra -std=c11 -fsanitize=undefined -fno-sanitize-recover=undefined -g ex02-ubsan.c -o ex02halt
 * 运行: ./ex02halt → 第一个错误处 SIGABRT, 退出码 134
 * 验证环境: Apple clang 21.0.0（cc，macOS arm64）
 * 验证状态: 已验证（两种形态的报告与退出码见 README 表格与主文档示例 2）
 */
#include <limits.h>
#include <stdio.h>

int main(void) {
    int a = INT_MAX;
    int b = a + 1;        /* 故意有符号溢出 */
    printf("b = %d\n", b);

    int s = 1 << 31;      /* 故意非法移位: 位数 == int 位宽 */
    printf("s = %d\n", s);
    return 0;
}
