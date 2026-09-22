// 来源：06-modern-cpp.md 第 6 章示例 3 —— std::optional 表示查找结果 / 配置项可选值
// 一句话说明：查找配置项可能不存在，用 optional 显式表达，拒绝 -1/空串哨兵值；
//             value_or 给出默认值，emplace 就地构造。
// 验证环境：Apple clang 17（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex03-optional-lookup.cpp -o ex03-optional-lookup
// 运行：./ex03-optional-lookup
// 验证状态：已验证
#include <iostream>
#include <optional>
#include <string>
#include <unordered_map>

// 查找配置项：可能不存在，用 optional 表达，拒绝 -1/空串哨兵值
std::optional<int> lookup(const std::unordered_map<std::string, int>& conf,
                          const std::string& key) {
    auto it = conf.find(key);
    if (it == conf.end()) return std::nullopt;   // 显式"无值"
    return it->second;
}

int main() {
    std::unordered_map<std::string, int> config = {
        {"port", 8080}, {"timeout_ms", 5000},
    };

    auto port = lookup(config, "port");
    if (port) std::cout << "port = " << *port << "\n";          // 8080

    auto retries = lookup(config, "retries");
    std::cout << "retries has_value = "
              << std::boolalpha << retries.has_value() << "\n"; // false
    std::cout << "retries value_or = "
              << retries.value_or(3) << "\n";

    std::optional<std::string> name;            // emplace 就地构造
    name.emplace("cache_node");
    std::cout << "name = " << *name << "\n";
    return 0;
}
