// 来源：exercises/ 练习 3 —— concept 约束泛型函数（题目见 exercises/README.md，题解分离）
// 一句话说明：自定义 concept Numeric 约束泛型 sum，简写形式与 requires 子句
//             是等价写法；string 传入时编译期报 constraints not satisfied。
// 验证环境：Apple clang 17（g++ 兼容），C++20（涉及 concept）
// 编译：g++ -Wall -Wextra -std=c++20 sol-03-concept-constrained.cpp -o sol-03-concept-constrained
// 运行：./sol-03-concept-constrained
// 验证状态：已验证
#include <cassert>
#include <concepts>
#include <iostream>
#include <vector>

template<typename T>
concept Numeric = std::integral<T> || std::floating_point<T>;

// 简写形式：concept 名直接作为模板参数约束
template<Numeric T>
T sum(const std::vector<T>& v) {
    T acc{};
    for (const auto& x : v) acc += x;
    return acc;
}

// requires 子句等价写法
template<typename T>
  requires Numeric<T>
T sum_requires(const std::vector<T>& v) {
    T acc{};
    for (const auto& x : v) acc += x;
    return acc;
}

int main() {
    const std::vector<int> vi = {1, 2, 3};
    const std::vector<double> vd = {1.5, 2.5};
    assert(sum(vi) == 6);
    assert(sum(vd) == 4.0);
    assert(sum_requires(vi) == 6);
    assert(sum_requires(vd) == 4.0);
    // 若把 std::vector<std::string> 传给 sum：编译报错
    //   no matching function for call to 'sum'
    //   constraints not satisfied ... std::string 不满足 Numeric
    // 对比 enable_if 时代动辄数十行的模板实例化回溯，错误信息一行说清。
    std::cout << "concept 约束求和全部断言通过\n";
    return 0;
}
