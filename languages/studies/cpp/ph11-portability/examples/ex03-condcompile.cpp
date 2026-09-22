// ex03-condcompile.cpp —— 平台宏与条件编译
// 主题：用 #if defined(...) 把平台差异编译期分流；配合 -D 命令行宏模拟其他平台。
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra ex03-condcompile.cpp -o /tmp/ex03-condcompile
//           c++ -D_WIN32 -std=c++20 -Wall -Wextra ex03-condcompile.cpp -o /tmp/ex03-win   # 模拟 Windows
// 运行：    /tmp/ex03-condcompile  与  /tmp/ex03-win
// 验证状态：已验证（两种编译器均零警告；-D_WIN32 模拟分支输出 platform: Windows）
#include <cstdio>

// 平台分支：只进一个 #elif 分支（顺序决定优先级）
const char* platform_name() {
#if defined(_WIN32)
    return "Windows";                  // 32/64 位 Windows 都定义 _WIN32
#elif defined(__APPLE__)
    return "macOS";                    // Apple 平台（macOS/iOS）
#elif defined(__linux__)
    return "Linux";
#else
    return "unknown";
#endif
}

// 编译器分支：判平台和判编译器要分开（MinGW 在 Windows 上两者同时定义）
const char* compiler_name() {
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

// 特性检测：__has_include 回答"这个头在不在"，比猜标准版本更贴近真相
#if defined(__has_include)
    #if __has_include(<optional>)
        #define HAS_OPTIONAL 1
    #else
        #define HAS_OPTIONAL 0
    #endif
#else
    #define HAS_OPTIONAL 0
#endif

int main() {
    std::printf("platform = %s\n", platform_name());
    std::printf("compiler = %s\n", compiler_name());
#if HAS_OPTIONAL
    std::printf("has <optional> = yes\n");
#else
    std::printf("has <optional> = no\n");
#endif
    return 0;
}
