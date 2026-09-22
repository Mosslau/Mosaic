// sol-01-cmake/text_utils.h —— 练习 1 参考实现：库头文件
// 验证环境：Apple clang 21（g++ 兼容），C++20
#ifndef SOL01_TEXT_UTILS_H
#define SOL01_TEXT_UTILS_H

#include <cstddef>
#include <string>

std::string to_upper(const std::string& s);
std::size_t count_vowels(const std::string& s);

#endif  // SOL01_TEXT_UTILS_H
