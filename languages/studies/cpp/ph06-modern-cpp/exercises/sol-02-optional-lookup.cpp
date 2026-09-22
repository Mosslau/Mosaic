// 来源：exercises/README.md 练习 2 —— 用 optional 表示查找结果
// 参考实现（题解分离：题目见 README.md）
// 对应 roadmap 练习"用 optional 表示查找结果"
// 验证环境：Apple clang 17（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-02-optional-lookup.cpp -o sol-02
// 运行：./sol-02
// 验证状态：已验证
#include <iostream>
#include <map>
#include <optional>
#include <string>

// 查找成绩：可能不存在，用 optional 显式表达
std::optional<int> find_score(const std::map<std::string, int>& scores,
                              const std::string& name) {
    auto it = scores.find(name);
    if (it == scores.end()) return std::nullopt;   // 显式"无值"
    return it->second;
}

int main() {
    const std::map<std::string, int> scores = {
        {"alice", 88}, {"bob", 92},
    };

    auto a = find_score(scores, "alice");
    if (a) std::cout << "alice 成绩 = " << *a << "\n";           // 88

    auto z = find_score(scores, "zed");
    std::cout << "zed has_value = " << std::boolalpha << z.has_value() << "\n"; // false
    std::cout << "zed value_or = " << z.value_or(60) << "\n";    // 默认值 60

    // 为什么不用哨兵值：若返回 -1 表示"不存在"，那成绩真的能是 -1 吗？
    // optional<int> 把"存在 int"与"不存在"分成两个显式状态，调用方不会被哨兵值误导，
    // 也不会出现"把 -1 当真成绩用"的隐患。
    return 0;
}
