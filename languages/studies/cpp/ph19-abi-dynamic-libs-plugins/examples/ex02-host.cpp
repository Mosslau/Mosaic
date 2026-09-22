// examples/ex02-host.cpp —— 链接调用动态库的宿主
// 教学点：链接期（编译期静态链接）调动态库 vs 运行期 dlopen（ex03）是两条路；
// 本文件是前者：编译时给 -lmath，链接器把对 math_add/_ZN4math3addEii 的引用
// 记成对 dylib 的依赖，加载时由 dyld（macOS）/ ld.so（Linux）解析。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 前置：先按 ex02-extern-c-shared.cpp 文件头编译出 /tmp/libmath.dylib
// 编译宿主（macOS）：
//   clang++ -std=c++20 -Wall -Wextra ex02-host.cpp -L/tmp -lmath -o /tmp/ph19cpp-ex02-host
// 运行：/tmp/ph19cpp-ex02-host
// 看宿主对 dylib 的依赖记录（install_name）：
//   otool -L /tmp/ph19cpp-ex02-host        # macOS
//   readelf -d /tmp/ph19cpp-ex02-host      # Linux（未在本环境验证）
// 验证状态：已验证（双编译器实测：编译零警告、运行通过；退出码 0）

#include <iostream>

#include "ex02-math.h"

// C++ 侧链接 dylib 里普通 C++ 函数的演示：需要同签名声明，链接器才能对上
// mangled 符号。**教学说明**：这里故意演示「C++ 符号也能跨 dylib 链接」，
// 但真实插件边界不该依赖它（见库文件头注释）；C++ 调用方与库必须用同一
// 编译器/同一标准库 ABI 版本，耦合远比 C ABI 紧。
namespace math {
int add(int a, int b);
}

int main() {
    // extern "C" 路径：稳定、跨语言、可被任何 C ABI 绑定找到
    std::cout << "extern \"C\" math_add(20, 22) = " << math_add(20, 22)
              << "  (api version " << math_version() << ")\n";

    // C++ 路径：同编译器下也能工作，但把宿主绑死在 mangled 名 + C++ ABI 上
    std::cout << "C++ math::add(20, 22)      = " << math::add(20, 22) << "\n";

    return 0;
}
