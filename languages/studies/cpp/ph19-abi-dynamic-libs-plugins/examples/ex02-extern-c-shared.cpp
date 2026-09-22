// examples/ex02-extern-c-shared.cpp —— extern "C" 动态库实现
// 教学点：roadmap 学习内容「extern C」「动态库构建」。同一份源码里同时放
// extern "C" 函数（C 链接、符号不 mangling）与普通 C++ 函数（Itanium
// mangling）——用 nm 看导出表就能直观看到两类符号形态的差别，这是
// 「C ABI 稳定、C++ ABI 不稳」的起点。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 编译（动态库，产物写 /tmp）：
//   macOS dylib：
//     clang++ -std=c++20 -Wall -Wextra -dynamiclib ex02-extern-c-shared.cpp -o /tmp/libmath.dylib
//   Linux .so（对照，未在本环境验证——本机是 macOS）：
//     clang++ -std=c++20 -Wall -Wextra -fPIC -shared ex02-extern-c-shared.cpp -o /tmp/libmath.so
// 看导出符号（本机已验证；Mach-O 会给符号加 _ 前缀，C++ 符号因此显示为双下划线开头）：
//     nm -gU /tmp/libmath.dylib
//     nm -gU /tmp/libmath.dylib | c++filt
// 宿主链接与运行见 ex02-host.cpp 文件头。
// 验证状态：已验证（双编译器 -dynamiclib 实测：编译零警告；nm 可见
//   extern "C" 导出 _math_add/_math_version，C++ 导出 __ZN4math3addEii）

#include "ex02-math.h"

namespace math {

// 普通 C++ 函数：跨 dylib 链接它的代价是绑定 Itanium mangled 名
// （Mach-O nm 显示 __ZN4math3addEii；ELF 显示 _ZN4math3addEii）。
// 工程实践中**不推荐**把它当作动态库的公共接口——编译器/标准库版本一变，
// mangling 或 ABI 就可能变（见主文档 3.7），宿主就崩在链接或运行期。
int add(int a, int b) { return a + b; }

}  // namespace math

// extern "C" 函数：符号不 mangling，任何语言（C/C++/Rust 的 C ABI 绑定）都能
// 稳定地按名字找到它。动态库/插件边界的公共函数几乎都走这条路。
// 实现处由头文件里的 extern "C" 声明统一了链接方式，无需重复写 extern "C"。

// math_add 的签名后面若变化（参数/返回类型），C 链接没有 mangling 护栏——
// 宿主与库必须同步升级，或靠本文件对外的 ABI 版本约定兜底（见 ex06）。
int math_add(int a, int b) { return a + b; }

int math_version(void) { return 1; }
