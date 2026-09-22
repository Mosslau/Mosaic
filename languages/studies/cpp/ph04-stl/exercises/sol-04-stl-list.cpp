// 来源：exercises/README.md 练习 4 —— 用 STL 重写链表项目参考实现
// 一句话说明：同一份「联系人名单」逻辑分别用 std::list 与 std::vector 实现，
//             中间插入/删除都通过 find 定位 + insert/erase 完成，注释对比复杂度。
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-04-stl-list.cpp -o sol-04-stl-list
// 运行：./sol-04-stl-list
// 验证状态：已验证
#include <algorithm>
#include <iostream>
#include <list>
#include <string>
#include <vector>

// std::list：双向链表。定位后插入/删除 O(1)，但每个节点带两个指针，cache 不友好
void list_version() {
    std::list<std::string> names;
    names.push_back("alice");
    names.push_back("bob");
    names.push_back("carol");
    names.push_back("dave");

    // 在 "carol" 之前插入 "amy"：O(n) 查找 + O(1) 插入
    auto it = std::find(names.begin(), names.end(), "carol");
    names.insert(it, "amy");

    // 删除 "bob"：O(n) 查找 + O(1) 删除
    auto bob = std::find(names.begin(), names.end(), "bob");
    if (bob != names.end()) names.erase(bob);

    // 按名字查找：O(n)
    auto dave = std::find(names.begin(), names.end(), "dave");
    std::cout << "list  version: dave "
              << (dave != names.end() ? "found" : "missing") << "\n";

    std::cout << "list  version:";
    for (const auto& n : names) std::cout << " " << n;
    std::cout << "\n";
}

// std::vector：连续内存。中间插入/删除 O(n)（元素整体搬移），但 cache 友好，遍历更快
void vector_version() {
    std::vector<std::string> names = {"alice", "bob", "carol", "dave"};

    // 在 "carol" 之前插入 "amy"：O(n) 查找 + O(n) 插入（后续元素后移）
    auto it = std::find(names.begin(), names.end(), "carol");
    names.insert(it, "amy");

    // 删除 "bob"：O(n) 查找 + O(n) 删除（后续元素前移）
    auto bob = std::find(names.begin(), names.end(), "bob");
    if (bob != names.end()) names.erase(bob);

    auto dave = std::find(names.begin(), names.end(), "dave");
    std::cout << "vector version: dave "
              << (dave != names.end() ? "found" : "missing") << "\n";

    std::cout << "vector version:";
    for (const auto& n : names) std::cout << " " << n;
    std::cout << "\n";
}

int main() {
    list_version();
    vector_version();
    return 0;
}
