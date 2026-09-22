// exercises/sol-03-vector-stats.cpp —— 练习 3 参考实现：vector 一次遍历求最值与平均
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-03-vector-stats.cpp -o sol03
// 运行：./sol03
// 已验证：本环境编译零警告，输出 人数 6 / 平均 81.33 / 最高 99 / 最低 63
#include <iomanip>
#include <iostream>
#include <vector>

int main() {
    const std::vector<double> scores = {78, 92, 85, 63, 99, 71};

    double sum = 0.0;
    double max = scores.front();
    double min = scores.front();
    for (const auto& s : scores) {  // const auto&：只读遍历，零拷贝
        sum += s;
        if (s > max) max = s;
        if (s < min) min = s;
    }

    std::cout << "人数: " << scores.size() << '\n';
    std::cout << std::fixed << std::setprecision(2);  // 只对平均值保留两位小数
    std::cout << "平均: " << sum / static_cast<double>(scores.size()) << '\n';
    std::cout.unsetf(std::ios::floatfield);  // 恢复默认格式，避免最值也带小数
    std::cout << "最高: " << max << ", 最低: " << min << '\n';
    return 0;
}
