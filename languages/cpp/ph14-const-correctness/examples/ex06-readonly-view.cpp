// ex06-readonly-view.cpp —— 只读视图设计：std::string_view 与 std::span（观察不拥有）
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：c++ -std=c++20 -Wall -Wextra ex06-readonly-view.cpp -o /tmp/ph14-ex06
// 运行：/tmp/ph14-ex06
#include <cstdio>
#include <span>
#include <string>
#include <string_view>
#include <vector>

// 只读接口：string_view 参数（SL.str.2）—— 接受 string/字面量/子串，零拷贝、零分配
std::size_t count_vowels(std::string_view text) {
    std::size_t n = 0;
    for (char c : text) {
        if (c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u') {
            ++n;
        }
    }
    return n;
}

// 只读接口：span<const T> 参数 —— 连续内存只读视图，覆盖数组/vector/裸指针+长度
double average(std::span<const double> values) {
    double s = 0.0;
    for (double v : values) {
        s += v;
    }
    return values.empty() ? 0.0 : s / static_cast<double>(values.size());
}

int main() {
    std::printf("[1] string_view 零拷贝：不同字符串形态统一进只读接口\n");
    std::string s = "hello";
    const char* lit = "world";
    std::printf("  count_vowels(std::string) = %zu\n", count_vowels(s));
    std::printf("  count_vowels(C 字面量)    = %zu\n", count_vowels(lit));
    std::printf("  count_vowels(string_view) = %zu\n", count_vowels(std::string_view("aeiou")));
    std::printf("  （string_view 内部只是 {指针, 长度}，三种形态都零拷贝）\n");

    std::printf("[2] string_view 是「观察」：底层数据变，视图看到变（不拥有数据）\n");
    std::string text = "abc";
    std::string_view view = text;   // 视图借用 text 的字符
    text[0] = 'X';                  // 改的是 text（唯一拥有者）
    std::printf("  view = %s（text 被改后视图跟着变）\n", std::string(view).c_str());

    std::printf("[3] span 覆盖 vector / C 数组 / 裸指针+长度\n");
    std::vector<double> vec{1.0, 2.0, 3.0};
    double arr[] = {4.0, 6.0};
    std::printf("  average(vector)     = %.1f\n", average(vec));
    std::printf("  average(C 数组)     = %.1f\n", average(arr));
    std::printf("  average(ptr+len)    = %.1f\n",
                average(std::span<const double>(arr, 2)));

    std::printf("[4] 接口即承诺：span<const T> 只读，span<T> 可写\n");
    std::printf("  只读接口用 span<const double>；需要修改才暴露 span<double>（见主文档）\n");
    return 0;
}
