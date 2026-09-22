// 来源：exercises/ 练习 1 —— 泛型 Max（题目见 exercises/README.md，题解分离）
// 一句话说明：单 T 版本处理同类型比较；双参类型版本用 std::common_type_t
//             让混合类型（int/double）返回公共类型 double。
// 验证环境：Apple clang 17（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-01-generic-max.cpp -o sol-01-generic-max
// 运行：./sol-01-generic-max
// 验证状态：已验证
#include <cassert>
#include <iostream>
#include <string>
#include <type_traits>

// 单 T 版本：两个实参类型必须一致，否则推导冲突
template<typename T>
const T& my_max(const T& a, const T& b) {
    return a > b ? a : b;
}

// 双参类型版本：返回 common type，my_max(3, 4.5) 编译通过
template<typename T, typename U>
std::common_type_t<T, U> my_max(const T& a, const U& b) {
    using R = std::common_type_t<T, U>;
    return a > b ? static_cast<R>(a) : static_cast<R>(b);
}

int main() {
    assert(my_max(3, 7) == 7);                          // 单 T 版本：T=int
    assert(my_max(3.14, 2.71) == 3.14);                 // 单 T 版本：T=double
    assert(my_max(std::string("abc"), std::string("xyz")) == "xyz");
    // 混合类型：单 T 版本推导冲突（T 同时是 int 和 double），
    // 重载决议选出双参版本，common_type<int, double> = double
    assert(my_max(3, 4.5) == 4.5);
    std::cout << "泛型 Max 全部断言通过\n";
    return 0;
}
