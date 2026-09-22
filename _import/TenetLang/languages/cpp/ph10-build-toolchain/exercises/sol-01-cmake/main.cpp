// sol-01-cmake/main.cpp —— 练习 1 参考实现入口：CMake 组织"库 + 可执行"
// 验证环境：Apple clang 21（g++ 兼容），CMake 4.2.3，C++20
// 构建（Debug）：cmake -B build && cmake --build build
// 运行：./build/app（to_upper/count_vowels 断言通过，退出码 0）
// 双轨（Release）：cmake -B build-rel -DCMAKE_BUILD_TYPE=Release && cmake --build build-rel
// 清理：rm -rf build build-rel（产物全部在 build* 目录）
// 验证状态：已验证（Debug/Release 双构建零警告 + 运行通过）
#include "text_utils.h"
#include <cstdio>

int main() {
    const std::string s = "cmake demo";
    const std::string up = to_upper(s);
    const std::size_t v = count_vowels(s);
    std::printf("%s  vowels=%zu\n", up.c_str(), v);
    const bool ok = (up == "CMAKE DEMO") && (v == 4);   // cmake demo 的元音: a,e,e,o
    std::printf("assert: %s\n", ok ? "pass" : "FAIL");
    return ok ? 0 : 1;
}
