// 来源：exercises/README.md 练习 1 —— 词频统计与 Top-K 参考实现
// 一句话说明：unordered_map 统计词频 → vector 排序输出 Top-3，
//             频次并列时按词典序稳定排序（比较器二次比较）。
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-01-word-freq.cpp -o sol-01-word-freq
// 运行：./sol-01-word-freq
// 验证状态：已验证
#include <algorithm>
#include <iostream>
#include <string>
#include <unordered_map>
#include <vector>

int main() {
    const std::vector<std::string> words = {
        "cherry", "apple", "banana", "cherry", "apple", "cherry",
        "date", "banana", "elderberry", "banana", "fig", "apple"
    };

    // 词频统计：operator[] 不存在时默认构造 0，再自增 —— 一行完成
    std::unordered_map<std::string, int> freq;
    for (const auto& w : words) ++freq[w];

    // 拷贝到 vector 排序：map 的迭代器对可直接构造成 pair 序列
    std::vector<std::pair<std::string, int>> items(freq.begin(), freq.end());
    std::sort(items.begin(), items.end(),
              [](const auto& a, const auto& b) {
                  if (a.second != b.second) return a.second > b.second;  // 频次降序
                  return a.first < b.first;                              // 并列按词典序
              });

    constexpr int k = 3;  // Top-K
    std::cout << "=== Top-" << k << " ===\n";
    for (int i = 0; i < k && i < static_cast<int>(items.size()); ++i)
        std::cout << items[i].first << ": " << items[i].second << "\n";

    std::cout << "=== full frequency (desc) ===\n";
    for (const auto& [word, count] : items)
        std::cout << word << ": " << count << "\n";
    return 0;
}
