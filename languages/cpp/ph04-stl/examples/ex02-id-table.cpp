// 来源：04-stl.md 第 6 章示例 2 —— ID 查询表（unordered_map 带 struct 值）
// 一句话说明：用 std::unordered_map<int, Record> 做 ID → 记录的 O(1) 查找表，
//             演示 find 命中/未命中的两种处理路径。
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex02-id-table.cpp -o ex02-id-table
// 运行：./ex02-id-table
// 验证状态：已验证
#include <iostream>
#include <string>
#include <unordered_map>
#include <vector>

struct Record {
    std::string name;
    int score;
};

int main() {
    std::unordered_map<int, Record> table;
    table[101] = {"alice", 95};
    table[102] = {"bob", 87};
    table[103] = {"carol", 92};

    const std::vector<int> queries = {102, 105, 101};
    for (int id : queries) {
        auto it = table.find(id);
        if (it != table.end())
            std::cout << "id=" << id << " name=" << it->second.name
                      << " score=" << it->second.score << "\n";
        else
            std::cout << "id=" << id << " not found\n";
    }
    return 0;
}
