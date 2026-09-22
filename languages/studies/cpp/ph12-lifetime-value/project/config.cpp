// config.cpp —— 值语义配置对象实现（ph12 project）
#include "config.h"

#include <stdexcept>

namespace cfg {

namespace {

// 去掉字符串首尾的空白（空格 / 制表符），返回子串视图
std::string_view trim(std::string_view s) {
    while (!s.empty() && (s.front() == ' ' || s.front() == '\t')) {
        s.remove_prefix(1);
    }
    while (!s.empty() && (s.back() == ' ' || s.back() == '\t')) {
        s.remove_suffix(1);
    }
    return s;
}

}  // namespace

std::string_view Config::find(std::string_view key) const {
    for (const auto& e : entries_) {
        if (e.key == key) {
            return e.value;          // 借用：指向本 Config 内部存储
        }
    }
    return {};                       // 未找到：空视图（sv.empty() 判断）
}

Config Config::with(std::string_view key, std::string value) const {
    std::vector<Entry> next = entries_;    // 拷贝：值语义的"分叉"起点
    for (auto& e : next) {
        if (e.key == key) {
            e.value = std::move(value);    // 覆盖已有键
            return Config(std::move(next));
        }
    }
    next.push_back(Entry{std::string(key), std::move(value)});   // 新增键
    return Config(std::move(next));
}

Config Config::merged_with(const Config& other) const {
    std::vector<Entry> next = entries_;
    for (const auto& oe : other.entries_) {
        bool replaced = false;
        for (auto& e : next) {
            if (e.key == oe.key) {
                e.value = oe.value;        // other 覆盖同名条目
                replaced = true;
                break;
            }
        }
        if (!replaced) {
            next.push_back(oe);            // other 独有的条目并入
        }
    }
    return Config(std::move(next));
}

Config parse(std::string_view text) {
    std::vector<Entry> entries;
    std::size_t pos = 0;
    while (pos < text.size()) {
        // 按行切分（兼容 \r\n 与 \n）
        const std::size_t nl = text.find('\n', pos);
        const std::size_t end = (nl == std::string_view::npos) ? text.size() : nl;
        std::string_view line = text.substr(pos, end - pos);
        pos = (nl == std::string_view::npos) ? text.size() : nl + 1;
        if (!line.empty() && line.back() == '\r') {
            line.remove_suffix(1);
        }
        if (line.empty() || line.front() == '#') {
            continue;                      // 空行与注释行跳过
        }
        const std::size_t eq = line.find('=');
        if (eq == std::string_view::npos) {
            throw std::runtime_error("malformed line (missing '='): " + std::string(line));
        }
        entries.push_back(Entry{std::string(trim(line.substr(0, eq))),
                                std::string(trim(line.substr(eq + 1)))});
    }
    return Config(std::move(entries));     // prvalue：C++17 保证省略
}

}  // namespace cfg
