// exercises/sol-02-string-ops.cpp —— 练习 2 参考实现：std::string 拼接 / find / substr
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-02-string-ops.cpp -o sol02
// 运行：./sol02
// 已验证：本环境编译零警告，输出 hello cpp world! / 6 / cpp
#include <iostream>
#include <string>

int main() {
    std::string s = "hello cpp world";

    s += "!";  // operator+= 直接拼接，无需关心缓冲区和 '\0'
    std::cout << s << '\n';

    const size_t pos = s.find("cpp");  // 找不到时返回 std::string::npos
    std::cout << pos << '\n';

    const std::string sub = s.substr(pos, 3);  // 从下标 pos 起截取 3 个字符
    std::cout << sub << '\n';
    return 0;
}
