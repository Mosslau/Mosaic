// 来源：06-modern-cpp.md 第 6 章示例 2 —— 用 lambda 定义排序规则与回调（std::sort + capture）
// 一句话说明：lambda 就地定义降序排序规则；按值捕获外部阈值做过滤；
//             std::function 类型擦除包装回调。
// 验证环境：Apple clang 17（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex02-lambda-sort.cpp -o ex02-lambda-sort
// 运行：./ex02-lambda-sort
// 验证状态：已验证
#include <algorithm>
#include <functional>
#include <iostream>
#include <string>
#include <vector>

struct Sensor {
    std::string name;
    double value;
};

int main() {
    std::vector<Sensor> sensors = {{"temp", 36.5}, {"hum", 60.2}, {"co2", 810.0}};

    // lambda 定义排序规则：按 value 降序
    std::sort(sensors.begin(), sensors.end(),
              [](const Sensor& a, const Sensor& b) { return a.value > b.value; });
    for (const auto& s : sensors) std::cout << s.name << " = " << s.value << "\n";

    // capture 外部阈值过滤
    double threshold = 50.0;
    auto above = [threshold](const Sensor& s) { return s.value > threshold; };
    std::cout << "value > " << threshold << "：\n";
    for (const auto& s : sensors)
        if (above(s)) std::cout << "  " << s.name << "\n";

    // std::function 包装回调
    std::function<void(const Sensor&)> report = [](const Sensor& s) {
        std::cout << "report: " << s.name << " = " << s.value << "\n";
    };
    for (const auto& s : sensors) report(s);
    return 0;
}
