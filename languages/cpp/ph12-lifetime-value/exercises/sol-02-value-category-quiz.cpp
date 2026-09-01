// sol-02-value-category-quiz.cpp —— 练习 2 参考实现：值类别判定
// 练习 2 要求：用 decltype((expr)) 判别技巧写一个分类器，对给定的表达式清单
//   逐项报告 lvalue/prvalue/xvalue；先凭直觉预测，再运行核对，解释两个"坑"
//   （有名字的右值引用是 lvalue；字符串字面量是 lvalue）。
//
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致）：
//   x++                                -> prvalue
//   ++x                                -> lvalue
//   flag ? x : g_x                     -> lvalue
//   arr[0]                             -> lvalue
//   &arr[0]                            -> prvalue
//   lref_fn()                          -> lvalue
//   g_x                                -> lvalue
//   std::string("temp")                -> prvalue
//   static_cast<std::string&&>(s)      -> xvalue
//   std::move(s)                       -> xvalue
//   s                                  -> lvalue
//   "lit"                              -> lvalue
//   x == 42                            -> prvalue
//   预测要点：
//   - 自增：x++ 的表达式值是"旧值"的拷贝 → prvalue；++x 返回左值引用 → lvalue
//   - 条件表达式两侧都是 lvalue → 整体是 lvalue（glvalue）
//   - 下标表达式 arr[0] → lvalue；对它取地址 &arr[0] → prvalue（指针值）
//   - 返回引用的函数调用 → lvalue；返回非引用的函数调用 → prvalue
//   - std::move(s) / static_cast<T&&> → xvalue；有名字的 rref 是 lvalue；"lit" 是 lvalue
//   - 比较 x == 42 的结果是 bool 临时值 → prvalue
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-02-value-category-quiz.cpp -o /tmp/sol-02
// 运行：    /tmp/sol-02
// 验证状态：已验证（两种编译器均零警告，输出一致）
#include <cstdio>
#include <string>
#include <type_traits>
#include <utility>

int g_x = 7;                 // 文件作用域变量：演示取地址/函数返回引用
int& lref_fn() { return g_x; }   // 返回左值引用的函数 → 调用表达式是 lvalue

template <typename T>
const char* describe() {
    if constexpr (std::is_lvalue_reference_v<T>) {
        return "lvalue";
    } else if constexpr (std::is_rvalue_reference_v<T>) {
        return "xvalue";
    } else {
        return "prvalue";
    }
}

#define SHOW_CATEGORY(expr) \
    std::printf("%-34s -> %s\n", #expr, describe<decltype((expr))>())

int main() {
    int x = 42;
    int arr[3] = {1, 2, 3};
    const bool flag = true;
    std::string s = "hello";

    SHOW_CATEGORY(x++);                        // 后缀自增：旧值拷贝 → prvalue
    SHOW_CATEGORY(++x);                        // 前缀自增：返回左值引用 → lvalue
    SHOW_CATEGORY(flag ? x : g_x);             // 两侧 lvalue → 条件表达式是 lvalue
    SHOW_CATEGORY(arr[0]);                     // 下标 → lvalue
    SHOW_CATEGORY(&arr[0]);                    // 取地址 → prvalue（指针值）
    SHOW_CATEGORY(lref_fn());                  // 返回引用的函数调用 → lvalue
    SHOW_CATEGORY(g_x);                        // 全局变量名 → lvalue
    SHOW_CATEGORY(std::string("temp"));        // 直接构造临时 → prvalue
    SHOW_CATEGORY(static_cast<std::string&&>(s));  // 显式转换 → xvalue
    SHOW_CATEGORY(std::move(s));               // std::move 结果 → xvalue
    SHOW_CATEGORY(s);                          // 变量名 → lvalue
    SHOW_CATEGORY("lit");                      // 字符串字面量 → lvalue（const char[4]）
    SHOW_CATEGORY(x == 42);                    // 比较结果 bool 临时值 → prvalue
    return 0;
}
