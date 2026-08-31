/* ex04-uninit.c —— 未初始化变量（UB 演示）
 * 运行前提: 这是"故意读未初始化变量"的演示 —— 读的是栈上残留的垃圾值,
 * 不会崩溃但输出无意义; 建议用 -Wall -Wextra 编译观察编译期警告
 * (-Wuninitialized, Apple clang 实测 -O0~-O2 均触发), 再用 Valgrind 观察运行时报告。
 * 注: 本机(Apple clang 21.0.0, macOS arm64)无 Valgrind, 运行时检测未在本环境验证。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 -O1 -g ex04-uninit.c -o ex04
// 运行：./ex04（输出不确定值; Valgrind 检测命令见主文档 6 章示例 4, 未在本环境验证）
// 验证状态：已验证（编译期 -Wuninitialized 警告实测触发; 运行时输出垃圾值;
//           Valgrind --track-origins=yes 未在本环境验证——本机无 Valgrind）
#include <stdio.h>

int main(void) {
    int x;                   /* 未初始化: 栈垃圾值(不确定值) */
    if (x > 0)               /* UB: 条件依赖不确定值 */
        printf("正数: %d\n", x);
    else
        printf("非正数: %d\n", x);
    return 0;
}
