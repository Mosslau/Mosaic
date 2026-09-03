// project/executor.cpp —— 查询执行器 demo · 执行层实现（executor.h 的落地）
//
// 验证环境：Apple clang 21.0.0（c++）/ Homebrew clang 21.1.8（clang++），macOS arm64，libc++
// 构建/运行/测试：见同目录 Makefile（make / make run / make test）
// 验证状态：已验证（Apple clang 21.0.0，-std=c++17 -Wall -Wextra 本机实测：编译零警告、运行通过）
#include "executor.h"

#include <utility>

namespace querydemo {

// ============ TableScanExecutor ============
TableScanExecutor::TableScanExecutor(const IStorage& storage) : storage_(storage) {}

void TableScanExecutor::open() { index_ = 0; }

std::optional<Row> TableScanExecutor::next() {
    // row_at 越界返回空 → 结束语义
    return storage_.row_at(index_++);
}

void TableScanExecutor::close() {}

std::string TableScanExecutor::describe() const {
    return "scan(" + storage_.name() + ")";
}

// ============ FilterExecutor ============
FilterExecutor::FilterExecutor(std::unique_ptr<IExecutor> upstream, Predicate predicate,
                               std::string label)
    : upstream_(std::move(upstream)), predicate_(std::move(predicate)),
      label_(std::move(label)) {}

void FilterExecutor::open() { upstream_->open(); }

std::optional<Row> FilterExecutor::next() {
    // 循环拉取：谓词不通过的行直接丢弃，直到命中或上游耗尽
    while (auto row = upstream_->next()) {
        if (predicate_(*row)) {
            return row;
        }
    }
    return std::nullopt;
}

void FilterExecutor::close() { upstream_->close(); }

std::string FilterExecutor::describe() const {
    return upstream_->describe() + " -> filter(" + label_ + ")";
}

// ============ ProjectExecutor ============
ProjectExecutor::ProjectExecutor(std::unique_ptr<IExecutor> upstream,
                                 std::vector<std::string> columns)
    : upstream_(std::move(upstream)), columns_(std::move(columns)) {}

void ProjectExecutor::open() { upstream_->open(); }

std::optional<Row> ProjectExecutor::next() {
    auto row = upstream_->next();
    if (!row) {
        return std::nullopt;
    }
    // 投影：只保留被选列（缺列的行该字段自然缺席——查询结果只含选列）
    Row projected;
    for (const std::string& column : columns_) {
        const std::string* value = row->find(column);
        if (value != nullptr) {
            projected.fields[column] = *value;
        }
    }
    return projected;
}

void ProjectExecutor::close() { upstream_->close(); }

std::string ProjectExecutor::describe() const {
    std::string cols;
    for (const std::string& column : columns_) {
        if (!cols.empty()) {
            cols += ", ";
        }
        cols += column;
    }
    return upstream_->describe() + " -> project(" + cols + ")";
}

// ============ LimitExecutor ============
LimitExecutor::LimitExecutor(std::unique_ptr<IExecutor> upstream, std::size_t limit)
    : upstream_(std::move(upstream)), limit_(limit) {}

void LimitExecutor::open() {
    upstream_->open();
    remaining_ = limit_;
}

std::optional<Row> LimitExecutor::next() {
    if (remaining_ == 0) {
        return std::nullopt;  // 已取够：提前结束（真引擎里可下推为上游的 early stop）
    }
    auto row = upstream_->next();
    if (!row) {
        return std::nullopt;
    }
    --remaining_;
    return row;
}

void LimitExecutor::close() { upstream_->close(); }

std::string LimitExecutor::describe() const {
    return upstream_->describe() + " -> limit(" + std::to_string(limit_) + ")";
}

}  // namespace querydemo
