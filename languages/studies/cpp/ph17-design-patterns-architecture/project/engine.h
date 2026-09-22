// project/engine.h —— 查询执行器 demo · 组装层（组合根）
// 本层演示「分层架构的组装职责」：表注册（DI 组装点）、查询规格校验、
// 管道拼装（工厂职能：把 spec 变成可执行执行器树）、执行入口、完成事件。
// 依赖方向：engine → executor → storage（上层依赖下层接口，互不反向）。
//
// 验证环境：Apple clang 21.0.0（c++）/ Homebrew clang 21.1.8（clang++），macOS arm64，libc++
// 构建/运行/测试：见同目录 Makefile（make / make run / make test）
// 验证状态：已验证（Apple clang 21.0.0，-std=c++17 -Wall -Wextra 本机实测：编译零警告、运行通过）
#pragma once

#include <cstddef>
#include <functional>
#include <iosfwd>
#include <memory>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

#include "executor.h"
#include "storage.h"

namespace querydemo {

// 过滤条件：列 + 操作符（= != > >= < <=）+ 值
struct FilterSpec {
    std::string column;
    std::string op;
    std::string value;
};

// 查询规格：谁来组装层说「想要什么」，不说「怎么做」
struct QuerySpec {
    std::string table;
    std::vector<std::string> select_columns;  // 空 = 全列
    std::optional<FilterSpec> filter;         // 空 = 不过滤
    std::size_t limit{0};                     // 0 = 不限
};

struct QueryStats {
    std::size_t rows_in{0};   // 扫描输入行数（= 表行数，demo 语义）
    std::size_t rows_out{0};  // 最终输出行数
};

// ============ QueryEngine：组合根 ============
// 职责边界（分层 demo 的组装层）：
//   ① 注册表管理（把建好的表登记进来，内部统一以 IStorage 接口访问——DI 落点）
//   ② 查询规格校验（列存在、操作符合法——失败抛可诊断异常）
//   ③ 管道组装（工厂职能：spec → 执行器树，见 ex01 的注册表/工厂思想）
//   ④ 执行入口 + 完成事件（事件驱动设计的最小形态）
class QueryEngine {
public:
    // DI：注册表。调用方先建好 MemoryTable（具体实现），引擎只保留 IStorage 视图
    void add_table(std::shared_ptr<MemoryTable> table);

    struct Pipeline {
        std::unique_ptr<IExecutor> root;
    };

    Pipeline build(const QuerySpec& spec) const;  // 组装（工厂职能）

    QueryStats execute(const QuerySpec& spec, const Pipeline& pipeline,
                       std::ostream& out) const;  // 执行并把结果行写入 out

    // 每次执行完成触发一次（订阅方如 UI/日志/测试探针）
    void set_listener(std::function<void(const QueryStats&)> listener);

private:
    std::shared_ptr<IStorage> find_storage(const std::string& table) const;

    std::unordered_map<std::string, std::shared_ptr<IStorage>> tables_;
    std::function<void(const QueryStats&)> listener_;
};

// 便捷入口：build + execute 一步到位（打印执行计划 + 结果行）
QueryStats run_query(QueryEngine& engine, const QuerySpec& spec, std::ostream& out);

}  // namespace querydemo
