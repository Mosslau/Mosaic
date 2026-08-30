// 来源：05-templates.md 第 6 章示例 1 —— 函数模板 max/min + concept 约束
// 一句话说明：函数模板由调用实参自动推导类型；std::integral 约束 my_min
//             只接受整数，非法实参（如 double）在编译期被拒绝。
// 验证环境：Apple clang 17（g++ 兼容），C++20（涉及 concept，不能降级 C++17）
// 编译：g++ -Wall -Wextra -std=c++20 ex01-func-template.cpp -o ex01-func-template
// 运行：./ex01-func-template
// 验证状态：已验证
#include <concepts>
#include <iostream>
#include <string>

template<typename T>
T my_max(T a, T b) { return a > b ? a : b; }

template<std::integral T>
T my_min(T a, T b) { return a < b ? a : b; }

int main() {
    std::cout << "max(3, 7) = " << my_max(3, 7) << "\n";
    std::cout << "max(abc, xyz) = "
              << my_max(std::string("abc"), std::string("xyz")) << "\n";
    std::cout << "min(3, 7) = " << my_min(3, 7) << "\n";
    // my_min(3.14, 2.71); // 编译错误：double 不满足 std::integral
    return 0;
}
