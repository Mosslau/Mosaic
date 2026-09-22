// project/storage.h —— 查询执行器 demo · 存储层抽象
// 本文件属于分层 demo 的「接口 + 实现」最底层：
//   Row（行数据）→ IStorage（存储契约）→ MemoryTable（内存表实现）
// 上层（executor.h / engine.h）只依赖 IStorage，不依赖 MemoryTable 的实现细节。
//
// 验证环境：Apple clang 21.0.0（c++）/ Homebrew clang 21.1.8（clang++），macOS arm64，libc++
// 构建/运行/测试：见同目录 Makefile（make / make run / make test）
// 验证状态：已验证（Apple clang 21.0.0，-std=c++17 -Wall -Wextra 本机实测：编译零警告、运行通过）
#pragma once

#include <cstddef>
#include <initializer_list>
#include <map>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace querydemo {

// ============ 行：列名 → 字符串值（demo 用字符串统一承载，真引擎用类型化列） ============
struct Row {
    std::map<std::string, std::string> fields;

    // 稳定打印：字段按键排序，k=v 以 ", " 连接
    std::string format() const;

    // 取列值；缺列返回空串
    const std::string* find(const std::string& column) const;
};

// 便捷构造：make_row({{"id","1"},{"name","alice"}}) —— 声明见 storage.cpp
Row make_row(
    std::initializer_list<std::pair<const std::string, std::string>> fields);

// ============ 存储抽象：执行器与引擎对存储的全部依赖都在这里 ============
class IStorage {
public:
    virtual ~IStorage() = default;

    virtual std::string name() const = 0;                     // 表名（工厂注册表键）
    virtual std::size_t row_count() const = 0;                // 当前行数
    virtual std::optional<Row> row_at(std::size_t index) const = 0;  // 越界返回空
    virtual std::vector<std::string> column_names() const = 0;      // 排序后的列名
};

// ============ 实现：内存表（demo 唯一实现；文件存储/索引实现留作扩展方向） ============
class MemoryTable final : public IStorage {
public:
    MemoryTable(std::string name, std::vector<Row> rows);

    std::string name() const override;
    std::size_t row_count() const override;
    std::optional<Row> row_at(std::size_t index) const override;
    std::vector<std::string> column_names() const override;

private:
    std::string name_;
    std::vector<Row> rows_;
    std::vector<std::string> columns_;  // 构造时按行键并集排序缓存
};

}  // namespace querydemo
