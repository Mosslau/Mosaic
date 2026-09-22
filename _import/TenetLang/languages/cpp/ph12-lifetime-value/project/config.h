// config.h —— 值语义配置对象（ph12 project）
// 设计要点：
//   - Rule of Zero（C.20）：成员全是 std::string/std::vector<Entry>，不手写任何
//     特殊成员函数——拷贝=深拷贝（值语义）、移动=廉价转移，编译器生成的就是对的
//   - 不可变 + 按值变换：Config 构造后不再原地修改（没有 set 方法），"修改"通过
//     with()/merged_with() 返回新 Config——原对象不变，借用（string_view）因此稳定
//   - 借用式接口：find() 返回 std::string_view，只借用不拷贝；前提是借用者寿命
//     不超过 Config 本身（本类不可变，借用期内存储稳定）
//   - 所有权通过类型体现：Config 拥有数据（值语义），string_view/const& 只借用
#pragma once
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace cfg {

// 一条配置项：键值对。值语义：拷贝即独立副本
struct Entry {
    std::string key;
    std::string value;
};

// 值语义配置对象：可拷贝、可移动、可放进容器、可按值返回
class Config {
public:
    Config() = default;

    // 借用式查询：返回内部存储的 string_view，不拷贝；Config 存活期间有效
    std::string_view find(std::string_view key) const;

    // 值语义"设置"：返回添加/覆盖 key 后的新 Config，*this 不变
    Config with(std::string_view key, std::string value) const;

    // 值语义"合并"：other 覆盖同名条目、保留独有条目，返回新 Config
    Config merged_with(const Config& other) const;

    // 借用式访问：只读底层条目
    const std::vector<Entry>& entries() const { return entries_; }

    std::size_t size() const { return entries_.size(); }

private:
    friend Config parse(std::string_view text);   // 只有 parse 能直接构造
    explicit Config(std::vector<Entry> entries) : entries_(std::move(entries)) {}

    std::vector<Entry> entries_;   // 构造后不可变（无公开修改入口）→ 借用稳定
};

// 从 key=value 文本解析（# 开头为注释、空行跳过、缺 '=' 抛异常）。
// 按值返回：prvalue + C++17 保证省略，直接构造到调用方，零拷贝
Config parse(std::string_view text);

}  // namespace cfg
