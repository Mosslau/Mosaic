// sol-01-cmake/text_utils.cpp —— 练习 1 参考实现：库实现
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 构建：由 CMakeLists.txt 的 add_library(text_utils STATIC ...) 负责
#include "text_utils.h"

#include <cctype>

std::string to_upper(const std::string& s) {
    std::string out = s;
    for (char& c : out) {
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
