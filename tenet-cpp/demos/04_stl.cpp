// 04 · STL 设计演示（容器 / 迭代器 / 算法解耦）
// 编译运行：make && ./demos/04_stl

#include <algorithm>
#include <iostream>
#include <map>
#include <string>
#include <vector>

int main() {
    std::cout << "== 同一算法作用于不同容器 ==\n";

    std::vector<int> v = {5, 2, 8, 1, 9};
    std::sort(v.begin(), v.end());
    std::cout << "vector 排序: ";
    for (int x : v) std::cout << x << " ";
    std::cout << "\n";

    // 算法只依赖迭代器接口，不认识容器
    std::map<std::string, int> scores = {{"alice", 90}, {"bob", 85}, {"carol", 92}};
    auto top = std::max_element(
        scores.begin(), scores.end(),
        [](const auto& a, const auto& b) { return a.second < b.second; });
    std::cout << "map 里最高分: " << top->first << " = " << top->second << "\n";

    std::cout << "\n== lambda 定制算法行为 ==\n";
    std::vector<int> nums = {1, 2, 3, 4, 5, 6};
    int evens = std::count_if(nums.begin(), nums.end(), [](int x) { return x % 2 == 0; });
    std::cout << "偶数个数: " << evens << "\n";

    std::cout << "\n== 组合而非继承：算法/容器/迭代器三解耦 ==\n";
}
