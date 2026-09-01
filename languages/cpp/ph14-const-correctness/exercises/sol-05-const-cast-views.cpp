// sol-05-const-cast-views.cpp —— 练习 5 参考实现：const_cast 气味识别 + 只读视图
// 练习 5 要求：识别"通过 const& 参数 const_cast 改写实参"的设计气味（反例），
//              用诚实的非 const 引用参数重构（正例对照）；再用 string_view / span
//              把只读接口改成观察不拥有的视图形态。
//
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致）：
//   [1] 气味识别：to_upper_sneaky(const std::string&) 内 const_cast 改写实参
//     s="hello" 调用后变 "HELLO"（const& 承诺被破坏——调用方以为只读）
//   [2] 正例重构：to_upper(std::string&) 接口诚实，零 cast
//     s="world" 调用后变 "WORLD"（接口明说可写）
//   [3] 只读视图：count_letters(std::string_view) 接受 string / C 字面量，零拷贝
//     count_letters(std::string) = 5
//     count_letters(C 字面量)    = 5
//   [4] span 只读视图：average(std::span<const double>) 覆盖 vector 与 C 数组
//     average(vector) = 3.0
//     average(C 数组) = 4.5
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-05-const-cast-views.cpp -o /tmp/ph14-sol-05
// 运行：    /tmp/ph14-sol-05
// 验证状态：已验证（两种编译器均零警告，输出一致）
#include <cctype>
#include <cstdio>
#include <span>
#include <string>
#include <string_view>
#include <vector>

// [反例：气味] const& 参数却用 const_cast 改写实参 —— 合法（对象非 const）但接口在撒谎
void to_upper_sneaky(const std::string& s) {
    for (char& c : const_cast<std::string&>(s)) {   // 气味：const 承诺被静默撕毁
        c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
    }
}

// [正例对照] 要修改就明说：非 const 引用参数，零 cast
void to_upper(std::string& s) {
    for (char& c : s) {
        c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
    }
}

// 只读视图：string_view 参数（SL.str.2）——接受 string/字面量，零拷贝零分配
std::size_t count_letters(std::string_view text) {
    std::size_t n = 0;
    for (char c : text) {
        if (std::isalpha(static_cast<unsigned char>(c))) {
            ++n;
        }
    }
    return n;
}

// 只读视图：span<const double> 参数——覆盖 vector / C 数组 / 裸指针+长度
double average(std::span<const double> values) {
    double s = 0.0;
    for (double v : values) {
        s += v;
    }
    return values.empty() ? 0.0 : s / static_cast<double>(values.size());
}

int main() {
    std::printf("[1] 气味识别：to_upper_sneaky(const std::string&) 内 const_cast 改写实参\n");
    std::string s1 = "hello";
    to_upper_sneaky(s1);
    std::printf("  s=\"hello\" 调用后变 \"%s\"（const& 承诺被破坏——调用方以为只读）\n",
                s1.c_str());

    std::printf("[2] 正例重构：to_upper(std::string&) 接口诚实，零 cast\n");
    std::string s2 = "world";
    to_upper(s2);
    std::printf("  s=\"world\" 调用后变 \"%s\"（接口明说可写）\n", s2.c_str());

    std::printf("[3] 只读视图：count_letters(std::string_view) 接受 string / C 字面量，零拷贝\n");
    const std::string txt = "hello";
    std::printf("  count_letters(std::string) = %zu\n", count_letters(txt));
    std::printf("  count_letters(C 字面量)    = %zu\n", count_letters("hello"));

    std::printf("[4] span 只读视图：average(std::span<const double>) 覆盖 vector 与 C 数组\n");
    const std::vector<double> vec{1.0, 2.0, 3.0, 6.0};
    const double arr[] = {3.0, 6.0};
    std::printf("  average(vector) = %.1f\n", average(vec));
    std::printf("  average(C 数组) = %.1f\n", average(arr));
    return 0;
}
