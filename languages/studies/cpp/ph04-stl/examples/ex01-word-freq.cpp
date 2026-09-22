// 来源：04-stl.md 第 6 章示例 1 —— 词频统计（map vs unordered_map）
// 一句话说明：同一份词表分别用 std::map 与 std::unordered_map 统计词频，
//             对比「有序遍历」与「O(1) 查找」两种语义，再按频率降序输出 Top-K。
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex01-word-freq.cpp -o ex01-word-freq
// 运行：./ex01-word-freq
// 验证状态：已验证
#include <algorithm>
#include <iostream>
#include <map>
#include <string>
#include <unordered_map>
#include <vector>

int main() {
    const std::vector<std::string> words = {
        "apple", "banana", "apple", "cherry", "banana", "apple", "date"
    };

    // map：红黑树，输出自动按 key 排序
    std::map<std::string, int> freq_ordered;
    for (const auto& w : words) ++freq_ordered[w];
    std::cout << "=== map (ordered by key) ===\n";
    for (const auto& [word, count] : freq_ordered)
        std::cout << word << ": " << count << "\n";

    // unordered_map：哈希表，O(1) 均摊，输出无序
    std::unordered_map<std::string, int> freq_hash;
    for (const auto& w : words) ++freq_hash[w];
    std::cout << "\n=== unordered_map (any order) ===\n";
    for (const auto& [word, count] : freq_hash)
        std::cout << word << ": " << count << "\n";

    // 按频率降序排序输出（拷到 vector 再 sort，因为 map 按 key 有序）
    std::vector<std::pair<std::string, int>> sorted(
        freq_hash.begin(), freq_hash.end());
    std::sort(sorted.begin(), sorted.end(),
        [](const auto& a, const auto& b) { return a.second > b.second; });
    std::cout << "\n=== sorted by frequency desc ===\n";
    for (const auto& [word, count] : sorted)
        std::cout << word << ": " << count << "\n";

    return 0;
}
