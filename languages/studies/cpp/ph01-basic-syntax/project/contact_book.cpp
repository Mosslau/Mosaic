// project/contact_book.cpp —— 简单通讯录（ph01 阶段项目）
// 来源：languages/cpp/ph01-basic-syntax/project/，对应 cpp.md ph01「推荐项目」第一个
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 contact_book.cpp -o contact_book
// 运行：./contact_book   （按菜单输入数字；姓名可能含空格，内部用 getline 读取）
// 已验证：本环境编译零警告；添加/列出/查找/删除/非法输入/退出均正常（见 README 验收标准）
#include <iostream>
#include <string>
#include <vector>

struct Contact {
    std::string name;
    std::string phone;
};

// 读取一行非空输入；姓名可能含空格，因此统一用 getline
static std::string read_line(const std::string& prompt) {
    std::string line;
    for (;;) {
        std::cout << prompt;
        if (!std::getline(std::cin, line)) {
            return line;  // EOF：返回当前内容，由调用方处理
        }
        if (!line.empty()) {
            return line;
        }
        std::cout << "输入不能为空，请重试。\n";
    }
}

static void add_contact(std::vector<Contact>& contacts) {
    Contact c;
    c.name = read_line("姓名: ");
    c.phone = read_line("电话: ");
    contacts.push_back(c);  // Contact 很小，直接拷贝进 vector
    std::cout << "已添加: " << c.name << '\n';
}

static void list_contacts(const std::vector<Contact>& contacts) {
    if (contacts.empty()) {
        std::cout << "（通讯录为空）\n";
        return;
    }
    for (size_t i = 0; i < contacts.size(); ++i) {
        std::cout << i + 1 << ". " << contacts[i].name
                  << "  " << contacts[i].phone << '\n';
    }
}

// 按姓名查找，返回下标；未找到返回 contacts.size()
static size_t find_index(const std::vector<Contact>& contacts,
                         const std::string& name) {
    for (size_t i = 0; i < contacts.size(); ++i) {
        if (contacts[i].name == name) {
            return i;
        }
    }
    return contacts.size();
}

static void find_contact(const std::vector<Contact>& contacts) {
    const std::string name = read_line("要查找的姓名: ");
    const size_t idx = find_index(contacts, name);
    if (idx < contacts.size()) {
        std::cout << contacts[idx].name << "  " << contacts[idx].phone << '\n';
    } else {
        std::cout << "未找到: " << name << '\n';
    }
}

static void remove_contact(std::vector<Contact>& contacts) {
    const std::string name = read_line("要删除的姓名: ");
    const size_t idx = find_index(contacts, name);
    if (idx < contacts.size()) {
        contacts.erase(contacts.begin() + static_cast<long>(idx));
        std::cout << "已删除: " << name << '\n';
    } else {
        std::cout << "未找到: " << name << '\n';
    }
}

int main() {
    std::vector<Contact> contacts;

    std::cout << "简单通讯录（命令：1 添加 / 2 列出 / 3 查找 / 4 删除 / 0 退出）\n";
    for (;;) {
        const std::string choice = read_line("> ");

        if (choice == "0") {
            break;
        } else if (choice == "1") {
            add_contact(contacts);
        } else if (choice == "2") {
            list_contacts(contacts);
        } else if (choice == "3") {
            find_contact(contacts);
        } else if (choice == "4") {
            remove_contact(contacts);
        } else {
            std::cout << "无效命令，请输入 0~4。\n";
        }
    }
    std::cout << "再见！\n";
    return 0;
}
