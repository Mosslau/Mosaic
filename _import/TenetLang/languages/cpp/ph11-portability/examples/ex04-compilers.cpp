// ex04-compilers.cpp —— 编译器差异宏实测（GCC / Clang / MSVC）
// 主题：同一段源码在不同编译器下，预定义宏的值各不相同——用宏检测编译器家族与版本。
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra ex04-compilers.cpp -o /tmp/ex04-compilers
// 运行：    /tmp/ex04-compilers   （另用 clang++ 编译对比，见 examples/README.md）
// 验证状态：已验证（Apple clang 与 Homebrew clang 均零警告；实测宏值见文件尾注释；
//           GCC/MSVC 分支代码可在对应编译器上编译，本机无这两家编译器，未在本环境验证）
#include <cstdio>

// 编译器家族判断：_MSC_VER 只由 MSVC 定义，__clang__ 只由 Clang 定义，
// __GNUC__ 由 GCC 定义、且 Clang 为兼容也会定义——所以判断顺序很关键：
// 先查 _MSC_VER，再查 __clang__，最后才轮到 __GNUC__。
const char* family() {
#if defined(_MSC_VER)
    return "MSVC";
#elif defined(__clang__)
    return "Clang";
#elif defined(__GNUC__)
    return "GCC";
#else
    return "unknown";
#endif
}

// 版本号：各家宏的语义完全不同，不能直接比大小
void version() {
#if defined(_MSC_VER)
    // MSVC：_MSC_VER 是"编译期版本戳"，如 1938 = VS2022 17.8（微软文档值，本机未验证）
    std::printf("  _MSC_VER        = %d (MSVC 版本戳)\n", _MSC_VER);
#endif
#if defined(__clang__)
    std::printf("  __clang_major__ = %d, __clang_minor__ = %d\n",
                __clang_major__, __clang_minor__);
#endif
#if defined(__GNUC__)
    // 注意：Clang 为兼容也会定义 __GNUC__ = 4.2.1（实测），它不是"真实 GCC 版本"！
    std::printf("  __GNUC__        = %d.%d.%d (GCC 主版本号；Clang 下是兼容值)\n",
                __GNUC__, __GNUC_MINOR__, __GNUC_PATCHLEVEL__);
#endif
#if defined(__cplusplus)
    std::printf("  __cplusplus     = %ld\n", static_cast<long>(__cplusplus));
#endif
#if defined(__VERSION__)
    std::printf("  __VERSION__     = \"%s\"\n", __VERSION__);
#endif
}

int main() {
    std::printf("compiler family: %s\n", family());
    version();
    return 0;
}

// 本机实测（已验证，C++20）：
//   Apple clang 21.0.0（c++）:
//     compiler family: Clang
//     __clang_major__ = 21, __clang_minor__ = 0
//     __GNUC__        = 4.2.1 (Clang 兼容值)
//     __cplusplus     = 202002
//     __VERSION__     = "Apple LLVM 21.0.0 (clang-2100.1.1.101)"
//   Homebrew clang 21.1.8（clang++）:
//     compiler family: Clang
//     __clang_major__ = 21, __clang_minor__ = 1
//     __GNUC__        = 4.2.1 (Clang 兼容值)
//     __cplusplus     = 202002
//     __VERSION__     = "Homebrew Clang 21.1.8"
//   对比结论：两家 Clang 的 __GNUC__ 都是 4.2.1——用 __GNUC__ 判断"是不是 GCC"会误判；
//   判 Clang 必须用 __clang__，判 GCC 才用 __GNUC__（且 GCC 真机未在本环境验证）。
