// ex05-path.cpp —— 用平台宏隔离实现：POSIX 用 '/', Windows 用 '\'
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra ex05-path.cpp ex05-main.cpp -o /tmp/ex05-path
//           c++ -D_WIN32 -std=c++20 -Wall -Wextra ex05-path.cpp ex05-main.cpp -o /tmp/ex05-path-win
// 运行：    /tmp/ex05-path  与  /tmp/ex05-path-win（-D_WIN32 模拟 Windows 实现分支）
// 验证状态：已验证（两种编译器、两个分支均零警告，输出见 examples/README.md）
#include "ex05-path.h"

namespace path {

#if defined(_WIN32)
    const char kSep = '\\';     // Windows 路径分隔符
#else
    const char kSep = '/';      // POSIX 路径分隔符
#endif

    char separator() { return kSep; }

    std::string join(const std::string& base, const std::string& rel) {
        if (base.empty()) return rel;
        if (base.back() == kSep) return base + rel;   // 已带分隔符，不重复加
        return base + kSep + rel;
    }

}  // namespace path
