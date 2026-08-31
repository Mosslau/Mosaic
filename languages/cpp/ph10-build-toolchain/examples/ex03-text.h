// ex03-text.h —— 动态库示例：头文件（声明）
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 使用方式：ex03-dynlib.cpp 编译为动态库 libex03.dylib，ex03-main.cpp 链接之
#ifndef EX03_TEXT_H
#define EX03_TEXT_H

#include <cstddef>
#include <string>

std::string to_upper(const std::string& s);   // 全转大写
std::size_t count_vowels(const std::string& s);  // 统计元音个数

#endif  // EX03_TEXT_H
