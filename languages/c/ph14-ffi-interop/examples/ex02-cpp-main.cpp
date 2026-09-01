/* ex02-cpp-main.cpp —— C++ 调 C：包含带 extern "C" 守卫的 C 头文件并链接动态库
 *
 * 编译（macOS）：
 *   cc  -Wall -Wextra -std=c11 -dynamiclib calc.c -o /tmp/ph14-ex/libcalc.dylib
 *   c++ -Wall -Wextra -std=c++17 ex02-cpp-main.cpp -L/tmp/ph14-ex -lcalc \
 *       -o /tmp/ph14-ex/ex02-cpp
 * 运行：/tmp/ph14-ex/ex02-cpp
 * 要点：calc.h 自带 #ifdef __cplusplus extern "C" 守卫 —— C++ 看到的是
 *   C 链接的声明，符号名不被 mangling，与 libcalc.dylib 导出的 _calc_add
 *   对得上；没有守卫就会链接失败（见 ex02-mangle-fail.cpp 的演示）。
 */
#include <cstdint>
#include <cstdio>

#include "calc.h"

int main() {
    std::int32_t sum = calc_add(20, 22);          /* 按 C 函数直接调用 */
    std::int32_t q = 0;
    int rc = calc_div(42, 2, &q);
    std::printf("cpp: calc_add(20,22)=%d calc_div(42,2)=rc=%d q=%d\n",
                static_cast<int>(sum), rc, static_cast<int>(q));
    return 0;
}
