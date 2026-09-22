// exercises/sol-03-versioned-plugin.cpp —— 练习 3 参考实现（插件侧）
// 教学点：插件导出 major/minor 版本，同一个源用宏编出多个版本库，供宿主
// 在调用业务函数前做版本校验。
//
// 接口约定：
//   extern "C" int plugin_version_major(void);
//   extern "C" int plugin_version_minor(void);
//   extern "C" int plugin_behavior(void);       // 业务函数（版本差异可观察）
//   extern "C" const char* plugin_name(void);
//
// 验证环境：macOS arm64，Apple clang 21.0.0，libc++
// 编译（同一源码三个版本，靠 -D 宏区分）：
//   clang++ -std=c++20 -Wall -Wextra -dynamiclib -DPLUGIN_VERSION_MAJOR=1 -DPLUGIN_VERSION_MINOR=0 \
//       sol-03-versioned-plugin.cpp -o /tmp/libplugin_v1.dylib
//   clang++ -std=c++20 -Wall -Wextra -dynamiclib -DPLUGIN_VERSION_MAJOR=2 -DPLUGIN_VERSION_MINOR=0 \
//       sol-03-versioned-plugin.cpp -o /tmp/libplugin_v20.dylib
//   clang++ -std=c++20 -Wall -Wextra -dynamiclib -DPLUGIN_VERSION_MAJOR=2 -DPLUGIN_VERSION_MINOR=1 \
//       sol-03-versioned-plugin.cpp -o /tmp/libplugin_v21.dylib
// 验证状态：已验证（编译零警告）

#ifndef PLUGIN_VERSION_MAJOR
#define PLUGIN_VERSION_MAJOR 1
#endif
#ifndef PLUGIN_VERSION_MINOR
#define PLUGIN_VERSION_MINOR 0
#endif

extern "C" int plugin_version_major(void) { return PLUGIN_VERSION_MAJOR; }

extern "C" int plugin_version_minor(void) { return PLUGIN_VERSION_MINOR; }

// 行为随版本演进：v1.x=10+minor 档，v2.x=20+minor 档——宿主若在版本校验前
// 调用它并假设 v2 语义，v1 的返回值会让逻辑悄悄走错
extern "C" int plugin_behavior(void) {
    return PLUGIN_VERSION_MAJOR * 10 + PLUGIN_VERSION_MINOR;
}

extern "C" const char* plugin_name(void) {
    return "versioned-op";
}
