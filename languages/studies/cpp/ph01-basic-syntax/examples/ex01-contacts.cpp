// examples/ex01-contacts.cpp —— 通讯录：用 struct + vector 组织数据，按名字查找
// 来源：languages/cpp/ph01-basic-syntax/01-basic-syntax.md 第 6 章示例 1
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex01-contacts.cpp -o ex01
// 运行：./ex01
// 已验证：本环境编译零警告，输出 Bob: 138-0002
#include <iostream>
#include <string>
#include <vector>

struct Contact {
    std::string name;
    std::string phone;
};

int main() {
    std::vector<Contact> contacts;

    // 添加联系人
    contacts.push_back({"Alice", "138-0001"});
    contacts.push_back({"Bob", "138-0002"});
    contacts.push_back({"Carol", "138-0003"});

    // 按名字查找
    const std::string query = "Bob";
    for (const auto& c : contacts) {  // const& 避免拷贝每个 Contact
        if (c.name == query) {
            std::cout << c.name << ": " << c.phone << '\n';
        }
    }
    return 0;
}
