// ex04-symbols.cpp —— 符号表观察：nm / objdump 视角
// 本文件故意放置了"全局函数/静态函数/非零初始化全局/零初始化全局/静态变量"各一种，
// 编译成目标文件后用 nm / objdump 观察符号表里的类型字母。
// 验证环境：Apple clang 21（g++ 兼容），C++20（本机 nm/objdump 为 LLVM 实现，Mach-O 格式）
// 编译：c++ -std=c++20 -Wall -Wextra -c ex04-symbols.cpp -o ex04-symbols.o
// 观察：nm ex04-symbols.o            （T=全局函数 t=静态函数 D=数据段全局
//                                     S=零初始化全局（__common） b=静态变量 U=未定义）
//       objdump -t ex04-symbols.o    （带段信息的符号表）
//       objdump -h ex04-symbols.o    （段表：__text 代码段 / __data 数据段 / __bss）
// 链接+运行：c++ -std=c++20 -Wall -Wextra ex04-symbols.o -o ex04-app && ./ex04-app
// 平台说明：字母含义随平台微调——本机（Apple/LLVM nm，Mach-O）零初始化全局显示为 S
//          （__common），Linux（GNU nm，ELF）同一定义显示为 B（__bss）；T/t/U 两种实现一致。
//          符号名带前缀下划线（__Z... 双下划线 = 单下划线 + Itanium ABI 的 _Z）也是 Apple 惯例。
// 验证状态：已验证（编译零警告 + nm/objdump 输出核对 + 运行通过）
#include <cstdio>

int g_counter = 5;          // 非零初始化全局 → 符号表 D（__data 段）
int g_zero = 0;             // 零初始化全局   → 符号表 S（__common；Linux ELF 上是 B）
static int s_hits = 0;      // 静态变量       → 符号表 b（__bss，局部，仅本翻译单元）

int global_add(int a, int b)  // 已定义全局函数 → 符号表 T（__text 段）
{
    ++s_hits;
    return a + b + g_counter;
}

static int hidden_util(int x) // 静态函数 → 符号表 t（局部，仅本翻译单元）
{
    return x * 2;
}

int main() {
    const int r = global_add(hidden_util(3), 4);   // = 6 + 4 + 5 = 15
    std::printf("g_counter=%d  r=%d  g_zero=%d\n", g_counter, r, g_zero);
    return r == 15 ? 0 : 1;
}
