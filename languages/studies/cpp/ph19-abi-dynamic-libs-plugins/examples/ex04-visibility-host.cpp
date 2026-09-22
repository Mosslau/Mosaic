// examples/ex04-visibility-host.cpp —— 链接调用「白名单导出」库的宿主
// 教学点：宿主只应依赖库的导出白名单（默认隐藏下的 EXPORT 函数）。普通
// 全局/匿名命名空间函数即便声明了也无法链接——这层「链接期护栏」把插件
// 库的公共表面（C ABI）与实现细节（C++ 符号、内部 helper）切开。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 前置：先按 ex04-visibility-lib.cpp 文件头编译 /tmp/libstore.dylib
// 编译宿主：
//   clang++ -std=c++20 -Wall -Wextra ex04-visibility-host.cpp -L/tmp -lstore -o /tmp/ph19cpp-ex04-host
// 运行：/tmp/ph19cpp-ex04-host
// 故意失败的对照（注释掉也能试——链接期报 undefined symbol，证明隐藏生效）：
//   extern "C" int ts_internal_impl(int);   // 声明了也没用：符号未导出
//   int main(){ return ts_internal_impl(1); }
// 验证状态：已验证（双编译器实测：编译零警告、运行通过、退出码 0）

#include <cstdint>
#include <cstdio>

// 宿主侧声明库的白名单接口（无需 attribute——那只是库实现侧的控制）
extern "C" int store_version(void);
extern "C" std::int64_t store_touch(std::int64_t x);

int main() {
    std::printf("store_version() = %d\n", store_version());
    const std::int64_t input = 21;
    std::printf("store_touch(%lld) = %lld  (库内部实现: *2)\n",
                static_cast<long long>(input), static_cast<long long>(store_touch(input)));
    return 0;
}
