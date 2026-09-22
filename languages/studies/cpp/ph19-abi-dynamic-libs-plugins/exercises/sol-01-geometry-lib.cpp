// exercises/sol-01-geometry-lib.cpp —— 练习 1 参考实现（动态库侧）
// 教学点：extern "C" 头声明一次、库实现与宿主都 include；C++ 函数与
// extern "C" 函数并存，nm 可对照两类符号。
//
// 验证环境：macOS arm64，Apple clang 21.0.0，libc++
// 编译（dylib；Linux 对照：-fPIC -shared）：
//   clang++ -std=c++20 -Wall -Wextra -dynamiclib sol-01-geometry-lib.cpp -o /tmp/libgeo.dylib
// 看导出符号（extern "C" 是 _rect_area 形态；C++ 是 __Z 开头的 mangled 形态）：
//   nm -gU /tmp/libgeo.dylib
// 验证状态：已验证（编译零警告；导出符号含 _rect_area/_rect_perimeter 与 C++ mangled 符号）
#include <cmath>

#include "sol-01-geometry.h"

// —— 故意放一个非 extern "C" 的 C++ 函数，供 nm 对照符号形态 ——
namespace cppside {
double rect_diagonal(double w, double h) {
    return sqrt(w * w + h * h);
}
}  // namespace cppside

double rect_area(double w, double h) { return w * h; }

double rect_perimeter(double w, double h) { return 2 * (w + h); }

int rect_api_version(void) { return 1; }
