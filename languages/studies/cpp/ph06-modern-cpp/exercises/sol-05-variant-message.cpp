// 来源：exercises/README.md 练习 5 —— 用 variant 表示多种状态
// 参考实现（题解分离：题目见 README.md）
// 对应 roadmap 练习"用 variant 表示多种状态"
// 验证环境：Apple clang 17（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-05-variant-message.cpp -o sol-05
// 运行：./sol-05
// 验证状态：已验证
#include <iostream>
#include <string>
#include <type_traits>
#include <variant>

struct Text { std::string content; };
struct Number { double value; };
struct Error { int code; std::string reason; };
using Message = std::variant<Text, Number, Error>;

std::string describe(const Message& m) {
    if (std::holds_alternative<Text>(m))
        return "text: " + std::get<Text>(m).content;
    if (std::holds_alternative<Number>(m))
        return "number: " + std::to_string(std::get<Number>(m).value);
    const auto& e = std::get<Error>(m);   // 分支不符时抛 std::bad_variant_access
    return "error " + std::to_string(e.code) + ": " + e.reason;
}

int main() {
    const Message msgs[] = {
        Text{"hello"}, Number{3.14}, Error{404, "not found"},
    };
    for (const auto& m : msgs) std::cout << describe(m) << "\n";

    // std::visit：对当前活跃分支统一处理（与 if constexpr 结合）
    std::visit([](const auto& m) {
        using T = std::decay_t<decltype(m)>;
        if constexpr (std::is_same_v<T, Text>)
            std::cout << "[visit] text: " << m.content << "\n";
        else if constexpr (std::is_same_v<T, Number>)
            std::cout << "[visit] number: " << m.value << "\n";
        else
            std::cout << "[visit] error: " << m.code << "\n";
    }, msgs[2]);

    std::cout << "index of Error = " << msgs[2].index() << "\n";  // 2
    return 0;
}
