// 来源：05-templates.md 第 6 章示例 3 —— constexpr + if constexpr 编译期计算
// 一句话说明：constexpr 函数在编译期求值（static_assert 验证）；if constexpr
//             作为编译期递归的终止条件，sum_to<100> 在编译期算出 5050。
// 验证环境：Apple clang 17（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex03-constexpr-if.cpp -o ex03-constexpr-if
// 运行：./ex03-constexpr-if
// 验证状态：已验证
#include <iostream>

constexpr unsigned long long factorial(unsigned int n) {
    unsigned long long r = 1;
    for (unsigned int i = 2; i <= n; ++i) r *= i;
    return r;
}

template<unsigned int N>
constexpr unsigned long long sum_to() {
    if constexpr (N == 0) return 0;          // 被丢弃的分支不实例化
    else return N + sum_to<N - 1>();         // 编译期递归
}

int main() {
    constexpr auto f5 = factorial(5);
    static_assert(f5 == 120, "5! must be 120");
    std::cout << "5!=" << f5 << " 10!=" << factorial(10) << "\n";
    constexpr auto s100 = sum_to<100>();
    std::cout << "sum_to<100>=" << s100 << "\n"; // 5050
    return 0;
}
