// project/storage.cpp —— 查询执行器 demo · 存储层实现（storage.h 的落地）
//
// 验证环境：Apple clang 21.0.0（c++）/ Homebrew clang 21.1.8（clang++），macOS arm64，libc++
// 构建/运行/测试：见同目录 Makefile（make / make run / make test）
// 验证状态：已验证（Apple clang 21.0.0，-std=c++17 -Wall -Wextra 本机实测：编译零警告、运行通过）
#include "storage.h"

#include <algorithm>
#include <set>

namespace querydemo {

std::string Row::format() const {
    std::string out;
    bool first = true;
    for (const auto& [key, value] : fields) {  // C++17 结构化绑定
        if (!first) {
            out += ", ";
        }
        first = false;
        out += key;
        out += "=";
        out += value;
    }
    return out;
}

const std::string* Row::find(const std::string& column) const {
    const auto it = fields.find(column);
    if (it == fields.end()) {
        return nullptr;
    }
    return &it->second;
}

Row make_row(
    std::initializer_list<std::pair<const std::string, std::string>> fields) {
    Row row;
    row.fields.insert(fields.begin(), fields.end());
    return row;
}

MemoryTable::MemoryTable(std::string name, std::vector<Row> rows)
    : name_(std::move(name)), rows_(std::move(rows)) {
    // 列 = 全部行的键并集（排序，保证 column_names 稳定）
    std::set<std::string> keys;
    for (const Row& row : rows_) {
        for (const auto& [key, value] : row.fields) {
            (void)value;
            keys.insert(key);
        }
    }
    columns_.assign(keys.begin(), keys.end());
}

std::string MemoryTable::name() const { return name_; }

std::size_t MemoryTable::row_count() const { return rows_.size(); }

std::optional<Row> MemoryTable::row_at(std::size_t index) const {
    if (index >= rows_.size()) {
        return std::nullopt;
    }
    return rows_[index];
}

std::vector<std::string> MemoryTable::column_names() const { return columns_; }

}  // namespace querydemo
