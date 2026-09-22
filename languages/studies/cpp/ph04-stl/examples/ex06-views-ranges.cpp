// 来源：04-stl.md 第 6 章示例 6 —— string_view / span / ranges 组合（C++20）
// 一句话说明：三个零开销抽象的组合演示——string_view 收字符串、span 收连续内存、
//             ranges 管道式过滤变换；本示例需要 C++20，编译命令与示例 1~5 不同。
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++20
// 编译：g++ -Wall -Wextra -std=c++20 ex06-views-ranges.cpp -o ex06-views-ranges
// 运行：./ex06-views-ranges
// 验证状态：已验证
#include <algorithm>
#include <iostream>
#include <ranges>
#include <span>
#include <string>
#include <string_view>
#include <vector>

void print_sv(std::string_view sv) {
    std::cout << "string_view: \"" << sv << "\" size=" << sv.size() << "\n";
}

int sum(std::span<const int> data) {
    int s = 0;
    for (int x : data) s += x;
    return s;
}

int main() {
    print_sv("C-string literal");  // const char* 隐式转换
    std::string s = "std::string";
    print_sv(s);                   // std::string → string_view
    print_sv(s.substr(0, 3));      // 临时 string 的安全视图

    int arr[] = {1, 2, 3, 4, 5};
    std::vector<int> v = {10, 20, 30};
    std::cout << "sum(arr)=" << sum(arr) << "\n";
    std::cout << "sum(v)=" << sum(v) << "\n";

    // ranges 管道式组合：过滤偶数 → 平方
    std::vector<int> nums = {1, 2, 3, 4, 5, 6, 7, 8};
    auto view = nums
              | std::views::filter([](int x) { return x % 2 == 0; })
              | std::views::transform([](int x) { return x * x; });
    std::cout << "even squares:";
    for (int x : view) std::cout << " " << x;
    std::cout << "\n";

    std::ranges::sort(nums);  // 直接传容器，无需 begin/end
    std::cout << "sorted:";
    for (int x : nums) std::cout << " " << x;
    std::cout << "\n";

    return 0;
}
