// project/engine.cpp —— 查询执行器 demo · 组装层实现（engine.h 的落地）
//
// 验证环境：Apple clang 21.0.0（c++）/ Homebrew clang 21.1.8（clang++），macOS arm64，libc++
// 构建/运行/测试：见同目录 Makefile（make / make run / make test）
// 验证状态：已验证（Apple clang 21.0.0，-std=c++17 -Wall -Wextra 本机实测：编译零警告、运行通过）
#include "engine.h"

#include <algorithm>
#include <exception>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>

namespace querydemo {

namespace {

// 值比较：两侧都可解析为数值（整串消费）→ 数值比较；否则字典序。
// 这是「demo 级」的语义选择，README 中有说明；真引擎由类型系统决定比较器。
double to_number(const std::string& text, bool& ok) {
    ok = false;
    try {
        std::size_t used = 0;
        const double value = std::stod(text, &used);
        ok = !text.empty() && used == text.size();
        return value;
    } catch (const std::exception&) {
        return 0.0;
    }
}

int compare_field(const std::string& a, const std::string& b) {
    bool a_num = false;
    bool b_num = false;
    const double a_value = to_number(a, a_num);
    const double b_value = to_number(b, b_num);
    if (a_num && b_num) {
        if (a_value < b_value) {
            return -1;
        }
        if (a_value > b_value) {
            return 1;
        }
        return 0;
    }
    if (a < b) {
        return -1;
    }
    if (a > b) {
        return 1;
    }
    return 0;
}

bool evaluate(const std::string& op, int cmp) {
    if (op == "=") {
        return cmp == 0;
    }
    if (op == "!=") {
        return cmp != 0;
    }
    if (op == ">") {
        return cmp > 0;
    }
    if (op == ">=") {
        return cmp >= 0;
    }
    if (op == "<") {
        return cmp < 0;
    }
    if (op == "<=") {
        return cmp <= 0;
    }
    return false;  // 未通过校验的操作符（engine 组装前已校验）
}

std::function<bool(const Row&)> make_predicate(const FilterSpec& spec) {
    return [spec](const Row& row) {
        const std::string* value = row.find(spec.column);
        if (value == nullptr) {
            return false;  // 缺列的行不匹配任何条件（明确语义，绝不静默通过）
        }
        return evaluate(spec.op, compare_field(*value, spec.value));
    };
}

bool contains(const std::vector<std::string>& items, const std::string& value) {
    return std::find(items.begin(), items.end(), value) != items.end();
}

}  // namespace

// ============ 注册（DI 落点） ============
void QueryEngine::add_table(std::shared_ptr<MemoryTable> table) {
    const std::string name = table->name();
    tables_[name] = std::move(table);  // 具体类型在此向上转型为 IStorage 视图
}

std::shared_ptr<IStorage> QueryEngine::find_storage(const std::string& table) const {
    const auto it = tables_.find(table);
    if (it == tables_.end()) {
        throw std::invalid_argument("未知表: " + table);
    }
    return it->second;
}

// ============ 组装（工厂职能：spec → 执行器树） ============
QueryEngine::Pipeline QueryEngine::build(const QuerySpec& spec) const {
    const std::shared_ptr<IStorage> storage = find_storage(spec.table);
    const std::vector<std::string> table_columns = storage->column_names();

    // 1) 校验：投影列与过滤列必须存在，操作符必须受支持（失败要可诊断）
    for (const std::string& column : spec.select_columns) {
        if (!contains(table_columns, column)) {
            throw std::invalid_argument("未知投影列: " + column + "（表 " +
                                        spec.table + "）");
        }
    }
    std::string filter_label;
    if (spec.filter) {
        if (!contains(table_columns, spec.filter->column)) {
            throw std::invalid_argument("未知过滤列: " + spec.filter->column +
                                        "（表 " + spec.table + "）");
        }
        const std::vector<std::string> allowed_ops{"=", "!=", ">", ">=", "<", "<="};
        if (!contains(allowed_ops, spec.filter->op)) {
            throw std::invalid_argument("不支持的比较操作符: " + spec.filter->op);
        }
        filter_label = spec.filter->column + " " + spec.filter->op + " " +
                       spec.filter->value;
    }

    // 2) 逐级包装：scan → filter → project → limit（每次包装持有上游所有权）
    std::unique_ptr<IExecutor> root =
        std::make_unique<TableScanExecutor>(*storage);
    if (spec.filter) {
        root = std::make_unique<FilterExecutor>(std::move(root),
                                                make_predicate(*spec.filter),
                                                filter_label);
    }
    if (!spec.select_columns.empty()) {
        root = std::make_unique<ProjectExecutor>(std::move(root),
                                                 spec.select_columns);
    }
    if (spec.limit > 0) {
        root = std::make_unique<LimitExecutor>(std::move(root), spec.limit);
    }

    Pipeline pipeline;
    pipeline.root = std::move(root);
    return pipeline;
}

// ============ 执行 ============
QueryStats QueryEngine::execute(const QuerySpec& spec, const Pipeline& pipeline,
                                std::ostream& out) const {
    QueryStats stats;
    const std::shared_ptr<IStorage> storage = find_storage(spec.table);
    stats.rows_in = storage->row_count();

    pipeline.root->open();
    while (auto row = pipeline.root->next()) {
        out << row->format() << '\n';
        ++stats.rows_out;
    }
    pipeline.root->close();

    if (listener_) {
        listener_(stats);  // 完成事件：订阅方拿到统计（观察者/事件驱动落点）
    }
    return stats;
}

void QueryEngine::set_listener(std::function<void(const QueryStats&)> listener) {
    listener_ = std::move(listener);
}

// ============ 便捷入口 ============
QueryStats run_query(QueryEngine& engine, const QuerySpec& spec, std::ostream& out) {
    const QueryEngine::Pipeline pipeline = engine.build(spec);
    out << "执行计划: " << pipeline.root->describe() << '\n';
    return engine.execute(spec, pipeline, out);
}

}  // namespace querydemo
