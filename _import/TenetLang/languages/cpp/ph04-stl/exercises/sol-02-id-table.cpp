// 来源：exercises/README.md 练习 2 —— ID 查询表参考实现
// 一句话说明：unordered_map<int, User> 做用户表，insert_or_assign 处理「已存在则更新」，
//             批量查询用 find 区分命中/未命中。
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-02-id-table.cpp -o sol-02-id-table
// 运行：./sol-02-id-table
// 验证状态：已验证
#include <iostream>
#include <string>
#include <unordered_map>
#include <vector>

struct User {
    std::string name;
    int age;
};

// 已存在则更新，不存在则插入 —— insert_or_assign（C++17）
void upsert(std::unordered_map<int, User>& table, int id, const User& user) {
    table.insert_or_assign(id, user);
}

int main() {
    std::unordered_map<int, User> table;
    upsert(table, 101, {"alice", 21});
    upsert(table, 102, {"bob", 24});
    upsert(table, 103, {"carol", 23});
    upsert(table, 101, {"alice", 22});  // 更新 alice 的年龄

    const std::vector<int> queries = {101, 102, 104, 105, 103};
    std::cout << "=== query results ===\n";
    std::vector<int> missed;
    for (int id : queries) {
        auto it = table.find(id);
        if (it != table.end())
            std::cout << "id=" << id << " name=" << it->second.name
                      << " age=" << it->second.age << "\n";
        else
            missed.push_back(id);
    }

    std::cout << "not found:";
    for (int id : missed) std::cout << " " << id;
    std::cout << "\n";
    return 0;
}
