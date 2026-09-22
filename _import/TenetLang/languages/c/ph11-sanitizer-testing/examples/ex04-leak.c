/* ex04-leak.c —— 泄漏检测: 分配后不释放（跨平台检测方式对照）
 * 运行前提: 这是"故意泄漏"的演示——内存泄漏不崩溃, 裸跑"看不出问题",
 *   "看不出问题"正是泄漏要工具才能发现的原因。
 * 编译（普通构建即可, 泄漏检测不需要编译期插桩）:
 *   cc -Wall -Wextra -std=c11 -g ex04-leak.c -o ex04
 * 检测方式（三选一, 按平台）:
 *   1. Linux: 用 ASan 构建后直接运行, 退出时内建 LeakSanitizer 报
 *      "Direct leak of 64 byte(s) in 1 object(s)"（LSan 随 ASan 内建, 仅 Linux）
 *   2. macOS: ASan 内建 LSan 不可用（实测报
 *      "AddressSanitizer: detect_leaks is not supported on this platform."）,
 *      改用系统自带 leaks:  leaks --atExit -- ./ex04
 *      → 实测 "Process ...: 1 leak for 80 total leaked bytes."（80 含 malloc 开销）
 *   3. Linux/macOS(Intel): Valgrind memcheck（不需重编译, 20~50 倍开销）
 *      valgrind --leak-check=full ./ex04 → "64 bytes in 1 blocks are definitely lost"
 *      （本机 Apple Silicon 官方不支持 Valgrind, 未在本环境验证）
 * 验证环境: Apple clang 21.0.0（cc，macOS arm64）
 * 验证状态: 已验证（macOS 上 LSan 不可用 + leaks 报告均实测, 见主文档示例 4）
 */
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    int *p = malloc(16 * sizeof(int));   /* 64 字节: 分配后从不释放 */
    if (p == NULL) return 1;
    p[0] = 1;
    printf("p[0]=%d (程序正常退出, 但 64 字节泄漏)\n", p[0]);
    return 0;                            /* 没有 free(p) */
}
