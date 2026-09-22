// 来源：04-stl.md 第 6 章示例 4 —— 用 STL 重写链表操作（list vs vector 对比）
// 一句话说明：ph02 手动实现的链表查找/插入/删除，在 STL 中由 std::list 与
//             <algorithm> 直接提供；同逻辑用 std::vector 写更贴近默认选择。
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex04-stl-list.cpp -o ex04-stl-list
// 运行：./ex04-stl-list
// 验证状态：已验证
#include <algorithm>
#include <iostream>
#include <list>
#include <string>
#include <vector>

int main() {
    // std::list 替代手动链表
    std::list<std::string> names = {"alice", "bob", "carol", "dave"};

    // O(n) 查找
    auto it = std::find(names.begin(), names.end(), "carol");
    if (it != names.end()) std::cout << "found: " << *it << "\n";

    // O(1) 插入（在找到位置之前）
    names.insert(it, "inserted");
    // O(1) 删除
    names.remove("bob");

    std::cout << "after insert/remove:";
    for (const auto& n : names) std::cout << " " << n;
    std::cout << "\n";

    // std::vector 实现相同逻辑（更好的默认选择）
    std::vector<std::string> v = {"alice", "bob", "carol", "dave"};
    auto vit = std::find(v.begin(), v.end(), "carol");
    if (vit != v.end()) v.insert(vit, "inserted"); // O(n)
    v.erase(std::remove(v.begin(), v.end(), "bob"), v.end()); // erase-remove idiom
    std::cout << "vector result:";
    for (const auto& n : v) std::cout << " " << n;
    std::cout << "\n";

    return 0;
}
