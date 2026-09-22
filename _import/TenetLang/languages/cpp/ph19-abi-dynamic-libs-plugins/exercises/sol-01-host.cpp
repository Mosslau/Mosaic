// exercises/sol-01-host.cpp —— 练习 1 参考实现（链接调用动态库的宿主）
// 教学点：链接期绑定 dylib；host 里声明 cppside::rect_diagonal 展示 C++ 符号
// 也能跨库链接（练习要求之外的小对照，见文件头注释）。
//
// 验证环境：macOS arm64，Apple clang 21.0.0，libc++
// 前置：先按 sol-01-geometry-lib.cpp 文件头编译 /tmp/libgeo.dylib
// 编译宿主：
//   clang++ -std=c++20 -Wall -Wextra sol-01-host.cpp -L/tmp -lgeo -o /tmp/ph19cpp-sol01-host
// 运行：/tmp/ph19cpp-sol01-host
// 验证状态：已验证（编译零警告、运行输出 面积=20 周长=18、退出码 0）
#include <cstdio>

#include "sol-01-geometry.h"

// 链接库里 C++ 函数的演示：需要与库实现完全一致的签名声明
namespace cppside {
double rect_diagonal(double w, double h);
}

int main() {
    const double w = 4.0;
    const double h = 5.0;
    const double area = rect_area(w, h);
    const double perimeter = rect_perimeter(w, h);
    std::printf("rect(%.1f x %.1f): area=%.1f perimeter=%.1f (api v%d)\n", w, h, area,
                perimeter, rect_api_version());
    std::printf("cppside::rect_diagonal = %.4f  (C++ 符号同样可跨库链接)\n",
                cppside::rect_diagonal(w, h));

    if (area == 20.0 && perimeter == 18.0) {
        std::printf("[PASS]\n");
        return 0;
    }
    std::fprintf(stderr, "[FAIL] 几何结果不符\n");
    return 1;
}
