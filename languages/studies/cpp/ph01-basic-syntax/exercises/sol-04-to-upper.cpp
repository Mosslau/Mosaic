// exercises/sol-04-to-upper.cpp —— 练习 4 参考实现：std::string 版大写转换
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-04-to-upper.cpp -o sol04
// 运行：./sol04   （输入一行字符串）
// 已验证：本环境编译零警告；输入 "hello World 123" 输出 "HELLO WORLD 123"
#include <cctype>
#include <iostream>
#include <string>

// 传值拿一个副本，在副本上原地修改后返回（移动语义保证返回值无拷贝开销）
std::string to_upper(std::string s) {
    for (auto& ch : s) {
        // toupper 接收/返回 int，需先转 unsigned char 避免负值 UB，再转回 char
        ch = static_cast<char>(
            std::toupper(static_cast<unsigned char>(ch)));
    }
    return s;
}

int main() {
    std::string line;
    std::cout << "输入一行字符串: ";
    std::getline(std::cin, line);
    std::cout << to_upper(line) << '\n';
    return 0;
}
