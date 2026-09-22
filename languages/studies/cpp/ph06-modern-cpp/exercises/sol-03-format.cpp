// 来源：exercises/README.md 练习 3 —— 用 std::format 重写字符串拼接
// 参考实现（题解分离：题目见 README.md）
// 对应 roadmap 练习"用 std::format 重写字符串拼接"
// 验证环境：Apple clang 17（g++ 兼容），C++23（涉及 <format>/<print>）
// 编译：g++ -Wall -Wextra -std=c++23 sol-03-format.cpp -o sol-03
// 运行：./sol-03
// 验证状态：已验证
#include <format>
#include <iomanip>
#include <iostream>
#include <print>
#include <string>
#include <tuple>
#include <vector>

int main() {
    const std::vector<std::tuple<int, std::string, double>> rows = {
        {1, "alice", 88.5},
        {2, "bob", 92.0},
        {3, "carol", 79.25},
    };

    // 旧写法：iostream 拼接（fixed + setprecision(2) 保持精度一致，便于对比）
    std::cout << "--- iostream 拼接 ---\n";
    std::cout << std::fixed << std::setprecision(2);
    for (const auto& [id, name, score] : rows)
        std::cout << "id=" << id << " name=" << name << " score=" << score << "\n";

    // 新写法：std::format / std::println，格式串编译期校验
    std::cout << "--- std::format 重写 ---\n";
    for (const auto& [id, name, score] : rows)
        std::println("id={} name={:<8} score={:.2f}", id, name, score);

    // 编译期校验：std::format("{} {}", 42) 占位符多于实参、
    // std::format("{:d}", 3.14) 类型不匹配——两者都会在编译期报错，
    // 而 printf 的同款错误要到运行期才暴露（未定义行为）。
    return 0;
}
