// ex03-main.cpp —— 动态库消费者：链接 libex03.dylib
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译+链接：c++ -std=c++20 -Wall -Wextra ex03-main.cpp -L. -lex03 -o ex03-app
// 运行：
//   ./ex03-app                              # 失败：dyld 找不到 @rpath/libex03.dylib（无 rpath）
//   DYLD_LIBRARY_PATH=. ./ex03-app          # 成功：环境变量指定查找路径
//   或链接时加 -Wl,-rpath,@loader_path/. 后直接运行（见 examples/README.md 示例 3）
// 验证状态：已验证（编译零警告 + 三种运行路径逐一验证）
#include "ex03-text.h"
#include <cstdio>

int main() {
    const std::string s = "hello dylib";
    const std::string up = to_upper(s);
    const std::size_t v = count_vowels(s);
    std::printf("%s  vowels=%zu\n", up.c_str(), v);
    const bool ok = (up == "HELLO DYLIB") && (v == 3);
    std::printf("assert: %s\n", ok ? "pass" : "FAIL");
    return ok ? 0 : 1;
}
