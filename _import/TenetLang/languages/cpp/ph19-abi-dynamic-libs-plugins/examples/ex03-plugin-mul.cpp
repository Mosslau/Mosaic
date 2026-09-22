// examples/ex03-plugin-mul.cpp —— 乘法算子插件（dlopen 目标之二）
// 教学点：与 ex03-plugin-add.cpp 遵循完全相同的 C ABI 接口约定，实现不同。
// 宿主（ex03-host.cpp）无需重编译即可在两个插件之间切换——「运行期扩展」
// 正是动态库相对静态链接的核心价值。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 编译：
//   clang++ -std=c++20 -Wall -Wextra -dynamiclib ex03-plugin-mul.cpp -o /tmp/libop_mul.dylib
// 验证状态：已验证（双编译器实测：编译零警告）

extern "C" int plugin_kind(void) {
    return 2;  // 2 = 乘法算子
}

extern "C" double plugin_apply(double a, double b) {
    return a * b;
}
