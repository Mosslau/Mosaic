// examples/ex03-plugin-add.cpp —— 加法算子插件（dlopen 目标之一）
// 教学点：插件 = 一组遵循约定签名的 extern "C" 函数，编成独立动态库；
// 宿主在运行期 dlopen/dlsym 按名字找它们。这个文件与 ex03-plugin-mul.cpp
// 是「同一接口、不同实现」的两个插件——宿主源码一行不改就能换实现。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 编译（macOS dylib；Linux 换成 -fPIC -shared 输出 .so）：
//   clang++ -std=c++20 -Wall -Wextra -dynamiclib ex03-plugin-add.cpp -o /tmp/libop_add.dylib
// 验证状态：已验证（双编译器实测：编译零警告）

// 插件公共接口（无共享头文件——dlopen 场景里接口就是这份「约定」）：
//   extern "C" int    plugin_kind(void)        // 算子类型标识
//   extern "C" double plugin_apply(double, double)
// 宿主 ex03-host.cpp 里用同签名函数指针接收，签名不一致会在 dlsym 拿到后
// 调用时出错——这正是 C ABI 边界「声明即契约、没有编译期检查」的体现。

extern "C" int plugin_kind(void) {
    return 1;  // 1 = 加法算子
}

extern "C" double plugin_apply(double a, double b) {
    return a + b;
}
