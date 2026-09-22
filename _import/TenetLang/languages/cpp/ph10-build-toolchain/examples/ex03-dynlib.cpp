// ex03-dynlib.cpp —— 动态库源码：编译为 libex03.dylib
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 构建（macOS）：c++ -std=c++20 -Wall -Wextra -dynamiclib \
//                   -install_name @rpath/libex03.dylib ex03-dynlib.cpp -o libex03.dylib
// 构建（Linux 对应）：c++ -std=c++20 -Wall -Wextra -shared -fPIC \
//                   ex03-dynlib.cpp -o libex03.so
// 验证状态：已验证（编译零警告 + 导出符号 nm 验证）
#include "ex03-text.h"

#include <cctype>

std::string to_upper(const std::string& s) {
    std::string out = s;
    for (char& c : out) {
        // 先转 unsigned char 再调用 ctype 函数，避免负值 UB（本阶段只需知道这条纪律）
        c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
    }
    return out;
}

std::size_t count_vowels(const std::string& s) {
    std::size_t n = 0;
    for (const char c : s) {
        const char lc = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
        if (lc == 'a' || lc == 'e' || lc == 'i' || lc == 'o' || lc == 'u') ++n;
    }
    return n;
}
