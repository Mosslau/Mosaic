/* sol-03-uninit-fix.c —— 参考实现: 定位并修复未初始化变量
 * 坏版本(故意)的实测情况(Apple clang 21.0.0):
 *   编译期: cc -Wall -Wextra -O1 → warning: variable 'x' is uninitialized
 *     when used here [-Wuninitialized] —— 编译器先于运行时就发现了;
 *   运行时: 输出不确定值(本环境实测为稳定垃圾值; 换调用上下文/编译器/优化
 *     级别即变, 这正是"不确定值"的含义);
 *   Valgrind: valgrind --track-origins=yes 会报 Conditional jump or move
 *     depends on uninitialised value(s) —— 未在本环境验证(本机无 Valgrind)。
 * 修复思路: 声明即初始化(roadmap 必会概念"初始化是 C 代码的生命线"的一半)。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-03-uninit-fix.c -o sol03
// 运行：./sol03（输出 x=0, 退出码 0）
// 验证状态：已验证（零警告; 坏版本的 -Wuninitialized 警告与垃圾值输出均实测）
#include <stdio.h>

int main(void) {
    int x = 0;   /* 修复: 声明即初始化 */
    if (x > 0)
        printf("正数: %d\n", x);
    else
        printf("非正数: %d\n", x);
    return 0;
}
