// sol-03-std-probe.cpp —— 练习 3 参考实现：检查项目使用的 C++ 标准特性
// 练习 3 要求：打印当前编译模式（__cplusplus）、头文件可用性（__has_include）、
// 标准库特性宏（__cpp_lib_*），并用 -std=c++17 与 -std=c++20 分别编译对比差异。
//
// 本机实测输出（已验证，Apple clang 21.0.0）：
//   c++ -std=c++17 -Wall -Wextra sol-03-std-probe.cpp -o /tmp/sol-03-17 && /tmp/sol-03-17
//     __cplusplus = 201703 (C++17)
//     __has_include(<optional>) = yes
//     __has_include(<format>)   = yes
//     __cpp_lib_filesystem = 201703
//     __cpp_lib_optional   = 201606
//     __cpp_lib_format     = (not defined)
//   c++ -std=c++20 -Wall -Wextra sol-03-std-probe.cpp -o /tmp/sol-03-20 && /tmp/sol-03-20
//     __cplusplus = 202002 (C++20)
//     __has_include(<optional>) = yes
//     __has_include(<format>)   = yes
//     __cpp_lib_filesystem = 201703
//     __cpp_lib_optional   = 202106
//     __cpp_lib_format     = 202110
//   差异结论：__cpp_lib_optional 从 201606 升到 202106（libc++ 在 C++20 下给新版宏），
//   __cpp_lib_format 在 C++17 下未定义、C++20 下为 202110——这就是"特性宏随标准模式变化"。
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++）
// 验证状态：已验证（两种编译器、两个 -std 均零警告，输出一致）
#include <cstdio>

// 标准库特性宏必须在 include 对应头文件之后才会定义（坑：不 include 就没有）
#include <filesystem>
#include <format>
#include <optional>

// __has_include 只能在预处理指令里用（不能在表达式里），所以先转成宏常量
#if defined(__has_include)
    #if __has_include(<optional>)
        #define HAS_OPTIONAL "yes"
    #else
        #define HAS_OPTIONAL "no"
    #endif
    #if __has_include(<format>)
        #define HAS_FORMAT "yes"
    #else
        #define HAS_FORMAT "no"
    #endif
#else
    #define HAS_OPTIONAL "n/a (pre-C++17)"
    #define HAS_FORMAT "n/a (pre-C++17)"
#endif

int main() {
#if defined(__cplusplus)
    std::printf("__cplusplus = %ld", static_cast<long>(__cplusplus));
#if __cplusplus >= 202002L
    std::printf(" (C++20)\n");
#elif __cplusplus >= 201703L
    std::printf(" (C++17)\n");
#else
    std::printf("\n");
#endif
#endif

    std::printf("__has_include(<optional>) = %s\n", HAS_OPTIONAL);
    std::printf("__has_include(<format>)   = %s\n", HAS_FORMAT);

#ifdef __cpp_lib_filesystem
    std::printf("__cpp_lib_filesystem = %ld\n", static_cast<long>(__cpp_lib_filesystem));
#else
    std::printf("__cpp_lib_filesystem = (not defined)\n");
#endif
#ifdef __cpp_lib_optional
    std::printf("__cpp_lib_optional   = %ld\n", static_cast<long>(__cpp_lib_optional));
#else
    std::printf("__cpp_lib_optional   = (not defined)\n");
#endif
#ifdef __cpp_lib_format
    std::printf("__cpp_lib_format     = %ld\n", static_cast<long>(__cpp_lib_format));
#else
    std::printf("__cpp_lib_format     = (not defined)\n");
#endif
    return 0;
}
