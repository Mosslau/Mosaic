// exercises/sol-01-greeting.cpp —— 练习 1 参考实现：getline 读整行姓名 + cin 读年龄
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-01-greeting.cpp -o sol01
// 运行：./sol01   （先输入姓名回车，再输入年龄回车）
// 已验证：本环境编译零警告；输入 "Li Ming" / 30 输出完整含空格姓名
#include <iostream>
#include <string>

int main() {
    std::string name;
    int age = 0;

    std::cout << "姓名: ";
    std::getline(std::cin, name);  // getline 读整行，空格不被截断

    std::cout << "年龄: ";
    std::cin >> age;               // >> 按空白分隔，适合读数值

    std::cout << "你好，" << name << "！今年 " << age << " 岁。" << '\n';
    return 0;
}
