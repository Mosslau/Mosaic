// 来源：05-templates.md 第 6 章示例 4 —— 自定义 concept + requires 约束
// 一句话说明：自定义 concept Printable 与标准 concept std::integral、
//             std::ranges::range 组合约束；非法实参（如 double 传给 gcd）编译报错。
// 验证环境：Apple clang 17（g++ 兼容），C++20（涉及 concept / std::ranges）
// 编译：g++ -Wall -Wextra -std=c++20 ex04-concept-requires.cpp -o ex04-concept-requires
// 运行：./ex04-concept-requires
// 验证状态：已验证
#include <concepts>
#include <iostream>
#include <ranges>
#include <vector>

template<typename T>
concept Printable = requires(T v) { std::cout << v; };

template<std::integral T>
T gcd(T a, T b) {
    while (b != 0) { T t = b; b = a % b; a = t; }
    return a;
}

template<typename T>
  requires std::ranges::range<T> && Printable<std::ranges::range_value_t<T>>
void print_all(const T& c) {
    for (const auto& v : c) std::cout << v << " ";
    std::cout << "\n";
}

int main() {
    std::cout << "gcd(48,18)=" << gcd(48, 18) << "\n";
    std::vector<int> v = {1, 2, 3, 4, 5};
    print_all(v);
    // gcd(3.14, 2.71); // 一行错误：double 不满足 std::integral
    return 0;
}
