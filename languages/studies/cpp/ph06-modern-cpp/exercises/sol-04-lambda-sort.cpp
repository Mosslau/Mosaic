// 来源：exercises/README.md 练习 4 —— 用 lambda 定义排序规则
// 参考实现（题解分离：题目见 README.md）
// 对应 roadmap 练习"用 lambda 定义排序规则"
// 验证环境：Apple clang 17（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-04-lambda-sort.cpp -o sol-04
// 运行：./sol-04
// 验证状态：已验证
#include <algorithm>
#include <iostream>
#include <string>
#include <vector>

struct Task {
    int priority;
    std::string name;
};

int main(int argc, char** argv) {
    std::vector<Task> tasks = {
        {1, "low"}, {5, "urgent"}, {3, "normal"}, {4, "high"},
    };

    // lambda 定义排序规则：priority 降序
    std::sort(tasks.begin(), tasks.end(),
              [](const Task& a, const Task& b) { return a.priority > b.priority; });
    for (const auto& t : tasks) std::cout << t.priority << " " << t.name << "\n";

    // 阈值来自运行期参数，保证"按值捕获"是必要的（否则编译器会警告捕获多余）
    const int min_priority = argc > 1 ? std::stoi(argv[1]) : 3;
    auto filtered = [min_priority](const Task& t) { return t.priority >= min_priority; };
    std::cout << "priority >= " << min_priority << "：\n";
    for (const auto& t : tasks)
        if (filtered(t)) std::cout << "  " << t.priority << " " << t.name << "\n";

    // 按引用捕获：修改外部计数变量 kept；min_priority 按值捕获
    int kept = 0;
    auto count_if = [&kept, min_priority](const Task& t) {
        if (t.priority >= min_priority) ++kept;
    };
    for (const auto& t : tasks) count_if(t);
    std::cout << "按引用捕获计数 = " << kept << "\n";
    return 0;
}
