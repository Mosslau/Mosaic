// examples/ex03-auto-range-for.cpp —— CTAD、range-for 与迭代器遍历对比
// 来源：languages/cpp/ph01-basic-syntax/01-basic-syntax.md 第 6 章示例 3
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex03-auto-range-for.cpp -o ex03
// 运行：./ex03
// 已验证：本环境编译零警告，两行均输出 1 2 3 4 5
#include <iostream>
#include <vector>

int main() {
    const auto nums = std::vector{1, 2, 3, 4, 5};  // C++17 CTAD：类模板参数推导

    // range-for 遍历：无需迭代器，const auto& 只读且零拷贝
    for (const auto& n : nums) {
        std::cout << n << ' ';
    }
    std::cout << '\n';

    // 迭代器写法：auto 避免写出 std::vector<int>::const_iterator 长类型名
    auto it = nums.begin();
    const auto end = nums.end();
    while (it != end) {
        std::cout << *it << ' ';
        ++it;
    }
    std::cout << '\n';
    return 0;
}
