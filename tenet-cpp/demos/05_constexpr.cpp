// 05 · constexpr 与编译期计算演示
// 编译运行：make && ./demos/05_constexpr

#include <array>
#include <iostream>

// constexpr 函数：编译期可求值，也可运行时求值
constexpr int fib(int n) {
    return n < 2 ? n : fib(n - 1) + fib(n - 2);
}

// static_assert：编译期断言，条件不满足直接编译失败
static_assert(fib(10) == 55, "fib(10) 必须在编译期算出 55");

// 编译期生成查找表：fib 前 12 项
constexpr std::array<int, 12> FIB_TABLE = [] {
    std::array<int, 12> t{};
    for (int i = 0; i < 12; ++i) t[i] = fib(i);
    return t;
}();

int main() {
    std::cout << "== 编译期求值 ==" << std::endl;
    std::cout << "fib(10) = " << fib(10) << "（static_assert 已证明它是编译期常量）\n";
    std::cout << "fib(20) = " << fib(20) << "（运行时求值，同一函数）\n";

    std::cout << "\n== 编译期生成的查找表（运行时零计算）==\n";
    for (int i = 0; i < 12; ++i) {
        std::cout << "fib(" << i << ") = " << FIB_TABLE[i] << "\n";
    }
}
