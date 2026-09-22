// examples/ex04-visibility-lib.cpp —— 符号可见性控制（动态库侧）
// 教学点：roadmap 学习内容「符号隐藏与可见性」。不加控制时动态库把所有
// 全局符号都导出（Mach-O/ELF 默认行为），内部实现细节暴露给全世界：符号
// 撞名、加载变慢、接口失控。标准姿势是「默认隐藏 + 白名单导出」：
//   -fvisibility=hidden 把默认可见性收为 hidden；
//   公共接口逐个加 __attribute__((visibility("default"))) 回到导出表。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 编译（-fvisibility=hidden 是本例关键）：
//   clang++ -std=c++20 -Wall -Wextra -fvisibility=hidden -dynamiclib \
//       ex04-visibility-lib.cpp -o /tmp/libstore.dylib
// 看导出表（本机已验证）：应只剩 _store_version/_store_touch 两个白名单符号
//   nm -gU /tmp/libstore.dylib
// 对照：去掉 -fvisibility=hidden 重编后，nm 会看到 ts_internal_impl 的 mangled 名
//   （形如 __Z16ts_internal_impl…）也出现在导出表——那就是「默认全导出」的样子
// 验证状态：已验证（双编译器实测：编译零警告；nm 导出表只剩白名单符号）

// 白名单宏：显式放行到导出表的函数。插件库的「公共 C ABI」只应包含这些
#define EXPORT __attribute__((visibility("default")))

#include <cstdint>

// 内部工具函数：只给本 dylib 自己用，不该出现在导出表。
// -fvisibility=hidden 生效时它不在导出表，宿主即使声明了也链接不到。
// 教学对照：把下面 -fvisibility=hidden 从编译命令里去掉重新编译，nm -gU
// 会看到它（以 mangled 名）也出现在导出表里——这就是「默认全导出」的样子。
std::int64_t ts_internal_impl(std::int64_t x) {
    return x * 2;  // 假装是某种内部加速路径
}

// —— 以下是「想对外开放的公共接口」，逐个 EXPORT ——

extern "C" EXPORT int store_version(void) {
    return 1;
}

extern "C" EXPORT std::int64_t store_touch(std::int64_t x) {
    // 宿主只能看到这个名字；ts_internal_impl 在默认隐藏下不出现在导出表（见 L24 教学对照）
    return ts_internal_impl(x);
}
