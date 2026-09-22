// 来源：06-modern-cpp.md 第 6 章示例 5 —— std::format 类型安全格式化输出（C++20，替代 printf / iostream 拼接）
// 一句话说明：std::format 格式串编译期校验、类型安全；特化 std::formatter 让自定义
//             类型接入 {}；std::println（C++23）直接打印到 stdout。
// 验证环境：Apple clang 17（g++ 兼容），C++23（涉及 <format>/<print>，不能降级 C++17）
// 编译：g++ -Wall -Wextra -std=c++23 ex05-format.cpp -o ex05-format
// 运行：./ex05-format
// 验证状态：已验证
#include <format>
#include <iostream>
#include <print>
#include <string>

struct Sensor {
    std::string name;
    double value;
};

// 自定义类型接入 std::format：特化 std::formatter
template<>
struct std::formatter<Sensor> {
    constexpr auto parse(std::format_parse_context& ctx) { return ctx.begin(); }
    auto format(const Sensor& s, std::format_context& ctx) const {
        return std::format_to(ctx.out(), "{} = {:.2f}", s.name, s.value);
    }
};

int main() {
    int id = 7;
    double val = 3.1415926;
    std::string unit = "V";
    std::string msg = std::format("sensor {}: value = {:.2f} {}", id, val, unit);
    std::println("{}", msg);                    // C++23：直接打印到 stdout
    std::cout << std::format("sensor {}: value = {:.2f} {}\n", id, val, unit);
    std::println("report: {}", Sensor{"temp", 36.5});  // 自定义类型
    return 0;
}
