// 来源：project/ —— 配置管理模块头文件
// 一句话说明：Config 类以 std::unordered_map<std::string, Value> 存键值，
//             Value 是 std::variant<bool, int64, double, string> 的类型安全多态；
//             查询用 std::optional 表达缺失，参数用 std::string_view 做只读视图。
// 验证环境：Apple clang 17（g++ 兼容），C++23（涉及 <format>）
// 编译：g++ -Wall -Wextra -std=c++23 config.cpp main.cpp -o config_app
// 验证状态：已验证
#ifndef TENET_CONFIG_H
#define TENET_CONFIG_H

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <variant>

namespace tenet {

// 配置值类型：variant 表达"同一时刻恰好是之一"（类型安全的 union）
using Value = std::variant<bool, std::int64_t, double, std::string>;

// 配置管理模块：key=value 存储 + optional 表达缺失配置项
class Config {
public:
    // 从文件加载（key=value 格式，支持 # 注释、空行、首尾空白、坏行跳过）；
    // 返回成功解析的条目数，文件打不开时抛 std::runtime_error
    std::size_t load(std::string_view path);

    // 查询配置项：可能不存在，用 optional 显式表达（拒绝哨兵值）
    std::optional<Value> get(std::string_view key) const;

    // 类型化查询：key 不存在或类型不匹配均返回 nullopt
    std::optional<bool> get_bool(std::string_view key) const;
    std::optional<std::int64_t> get_int(std::string_view key) const;
    std::optional<double> get_double(std::string_view key) const;
    std::optional<std::string> get_string(std::string_view key) const;

    std::size_t size() const { return entries_.size(); }
    bool empty() const { return entries_.empty(); }

    // 配置清单：std::format 输出 "key = value"，逐行一行
    std::string dump() const;

private:
    std::size_t parse_lines(std::string_view text);
    std::unordered_map<std::string, Value> entries_;
};

}  // namespace tenet

#endif  // TENET_CONFIG_H
