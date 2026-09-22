// config.hpp —— 只读配置接口（ph14 project，header-only）
// 设计要点（ph14 const 正确性）：
//  1. 接口全部 const（Con.2）：get/contains/size/keys 都是 const 成员函数；
//  2. 查询返回 std::string_view（观察不拥有，SL.str.2）——视图指向对象自有的 text_；
//  3. 查询统计 lookups_ 是 mutable 物理状态（逻辑 const：统计不影响配置语义）；
//  4. 无任何 public 修改方法——「改配置」只能构造新对象（不可变快照模型）；
//  5. Rule of 0（C.20）：成员都是值类型，拷贝/移动交给编译器（拷贝即只读快照）。
#ifndef PH14_CONFIG_HPP
#define PH14_CONFIG_HPP

#include <cstddef>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

class Config {
public:
    // 构造即解析：拥有原始文本（值语义），条目视图指向 text_（无拷贝）
    explicit Config(std::string text) : text_(std::move(text)) { parse(); }

    // 查询：不存在返回 nullopt（optional 表达"可能没有"，属 ph06）
    std::optional<std::string_view> get(std::string_view key) const {
        lookups_ += 1;                       // mutable 计数：物理状态
        for (const auto& [k, v] : entries_) {
            if (k == key) {
                return v;
            }
        }
        return std::nullopt;
    }

    bool contains(std::string_view key) const {
        lookups_ += 1;
        for (const auto& [k, v] : entries_) {
            (void)v;
            if (k == key) {
                return true;
            }
            // 快速路径：命中后提前返回；全表线性扫描（教学简化，未做哈希索引）
        }
        return false;
    }

    std::size_t size() const { return entries_.size(); }

    // 只读枚举：返回 key 列表（拷贝视图，演示用）
    std::vector<std::string_view> keys() const {
        std::vector<std::string_view> ks;
        ks.reserve(entries_.size());
        for (const auto& [k, v] : entries_) {
            (void)v;
            ks.push_back(k);
        }
        return ks;
    }

    // 查询统计（mutable 物理状态）：const 接口也能看"被查了多少次"
    std::size_t lookup_count() const { return lookups_; }

private:
    void parse() {
        std::size_t pos = 0;
        while (pos < text_.size()) {
            std::size_t eol = text_.find('\n', pos);
            if (eol == std::string::npos) {
                eol = text_.size();
            }
            std::string_view line(text_.data() + pos, eol - pos);
            pos = eol + 1;
            while (!line.empty() && (line.front() == ' ' || line.front() == '\t' ||
                                     line.front() == '\r')) {
                line.remove_prefix(1);       // 去行首空白
            }
            if (line.empty() || line.front() == '#') {
                continue;                    // 空行 / 注释
            }
            std::size_t eq = line.find('=');
            if (eq == std::string_view::npos) {
                continue;                    // 非法行跳过（教学简化）
            }
            std::string_view k = line.substr(0, eq);
            std::string_view v = line.substr(eq + 1);
            while (!k.empty() && k.back() == ' ') {
                k.remove_suffix(1);          // 去 key 尾部空白
            }
            while (!v.empty() && v.front() == ' ') {
                v.remove_prefix(1);          // 去 value 头部空白
            }
            entries_.emplace_back(k, v);     // 视图指向 text_（零拷贝）
        }
    }

    std::string text_;                                                      // 逻辑状态：拥有数据
    std::vector<std::pair<std::string_view, std::string_view>> entries_;    // 视图（指向 text_）
    mutable std::size_t lookups_{0};                                        // 物理状态：查询统计
};

#endif  // PH14_CONFIG_HPP
