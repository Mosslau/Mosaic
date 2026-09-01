// ex01-value-categories.cpp —— 值类别判别：lvalue / prvalue / xvalue
// 主题：值类别是表达式的属性（不是对象的属性）；用 decltype((expr)) 在编译期
//       判别表达式类别——lvalue → T&，xvalue → T&&，prvalue → T（无引用）。
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra ex01-value-categories.cpp -o /tmp/ex01
// 运行：    /tmp/ex01
// 验证状态：已验证（两种编译器均零警告，输出一致，见文件底部注释）
#include <cstdio>
#include <string>
#include <type_traits>
#include <utility>

// decltype((expr)) 是未求值上下文，不会真的执行 expr：
//   lvalue  → T&（左值引用）
//   xvalue  → T&&（右值引用）
//   prvalue → T（裸类型，无引用）
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

// 宏：打印表达式原文 + 类别（decltype((expr)) 不实际求值）
#define SHOW_CATEGORY(expr) \
    std::printf("%-34s -> %s\n", #expr, describe<decltype((expr))>())

int main() {
    std::printf("== 表达式值类别实测（decltype((expr)) 判别）==\n\n");

    int x = 42;
    std::string s = "hello";
    std::string& lref = s;               // 左值引用
    std::string&& rref = std::move(s);   // 右值引用

    SHOW_CATEGORY(x);                     // 变量名 → lvalue
    SHOW_CATEGORY(42);                    // 字面量 → prvalue
    SHOW_CATEGORY(s);                     // 变量名 → lvalue
    SHOW_CATEGORY(s + "!");               // 函数调用返回非引用 → prvalue
    SHOW_CATEGORY(std::move(s));          // std::move 的结果 → xvalue
    SHOW_CATEGORY(lref);                  // 左值引用的表达式 → lvalue
    SHOW_CATEGORY(rref);                  // 坑：有名字的右值引用是 lvalue！
    SHOW_CATEGORY("literal");             // 坑：字符串字面量是 lvalue（const char[N]）
    SHOW_CATEGORY(static_cast<std::string&&>(s));   // 显式转换 → xvalue
    SHOW_CATEGORY(std::string{"temp"});   // 直接构造的临时 → prvalue
    SHOW_CATEGORY(&x);                    // 取地址结果 → prvalue（指针值）
    return 0;
}
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致）：
//   == 表达式值类别实测（decltype((expr)) 判别）==
//
//   x                                  -> lvalue
//   42                                 -> prvalue
//   s                                  -> lvalue
//   s + "!"                            -> prvalue
//   std::move(s)                       -> xvalue
//   lref                               -> lvalue
//   rref                               -> lvalue
//   "literal"                          -> lvalue
//   static_cast<std::string&&>(s)      -> xvalue
//   std::string{"temp"}                -> prvalue
//   &x                                 -> prvalue
