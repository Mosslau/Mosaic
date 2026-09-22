// 来源：exercises/ 练习 5 —— 简单 TMP 模板元编程（题目见 exercises/README.md，题解分离）
// 一句话说明：编译期计算 —— Factorial/Fibonacci 递归实例化 + typelist
//             Length/Contains 基本变换，全部 static_assert 验证（零运行时代码）。
// 验证环境：Apple clang 17（g++ 兼容），C++17（折叠表达式）
// 编译：g++ -Wall -Wextra -std=c++17 sol-05-simple-tmp.cpp -o sol-05-simple-tmp
// 运行：./sol-05-simple-tmp
// 验证状态：已验证
#include <cstddef>
#include <iostream>
#include <type_traits>

// 编译期阶乘：递归实例化 + 全特化终止
template<int N> struct Factorial { static constexpr int value = N * Factorial<N - 1>::value; };
template<>      struct Factorial<0> { static constexpr int value = 1; };

// 编译期斐波那契：双递归 + 两个全特化终止
template<int N> struct Fibonacci { static constexpr int value = Fibonacci<N - 1>::value + Fibonacci<N - 2>::value; };
template<>      struct Fibonacci<0> { static constexpr int value = 0; };
template<>      struct Fibonacci<1> { static constexpr int value = 1; };

// typelist：把一组类型打包为一个类型，元编程的「容器」
template<typename... Ts> struct TypeList {};

// Length：列表长度（偏特化 + sizeof...）
template<typename List> struct Length;
template<typename... Ts>
struct Length<TypeList<Ts...>> { static constexpr std::size_t value = sizeof...(Ts); };

// Contains：类型是否在列表中（C++17 折叠表达式，C++17 前要写递归偏特化）
template<typename T, typename List> struct Contains;
template<typename T, typename... Ts>
struct Contains<T, TypeList<Ts...>>
    : std::bool_constant<(std::is_same_v<T, Ts> || ...)> {};

using MyTypes = TypeList<int, double, char>;

static_assert(Factorial<0>::value == 1);
static_assert(Factorial<5>::value == 120);
static_assert(Factorial<10>::value == 3628800);
static_assert(Fibonacci<0>::value == 0);
static_assert(Fibonacci<1>::value == 1);
static_assert(Fibonacci<10>::value == 55);
static_assert(Length<MyTypes>::value == 3);
static_assert(Contains<double, MyTypes>::value);
static_assert(!Contains<float, MyTypes>::value);

int main() {
    // 全部验证已在编译期完成，main 只做运行期确认
    std::cout << "Factorial<5>=" << Factorial<5>::value
              << " Fibonacci<10>=" << Fibonacci<10>::value
              << " Length=" << Length<MyTypes>::value << "\n";
    return 0;
}
