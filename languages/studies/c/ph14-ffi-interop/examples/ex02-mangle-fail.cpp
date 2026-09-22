// ex02-mangle-fail.cpp —— 【故意出错】演示 C++ 忘记 extern "C" 守卫时的链接失败
//
// 运行前提：本文件预期【链接失败】——它演示 name mangling 的后果，
//   不要期望它能生成可执行文件；编译命令：
//   c++ -Wall -Wextra -std=c++17 ex02-mangle-fail.cpp -L/tmp/ph14-ex -lcalc \
//       -o /tmp/ph14-ex/ex02-mangle-fail
//   预期输出（链接错误）：Undefined symbols ... "_calc_add(int, int)"
//   —— mangled 后的符号名在 libcalc.dylib 里找不到（库里只有 _calc_add）。
#include <cstdint>

#include "ex02-bad-header.h"   // 无 extern "C" 守卫 → calc_add 被 C++ 名字改编

int main() {
    std::int32_t sum = calc_add(20, 22);
    return sum == 42 ? 0 : 1;
}
