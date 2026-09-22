// project/executor.h —— 查询执行器 demo · 执行层抽象
// 本层演示 roadmap 练习「IExecutor 接口抽象」：pull 模型执行器（open/next/close），
// 每个节点包装上游（组合），管道由 engine.h 的组合根按查询规格逐级拼装。
// 上层只依赖 IExecutor；节点实现见 executor.cpp。
//
// 验证环境：Apple clang 21.0.0（c++）/ Homebrew clang 21.1.8（clang++），macOS arm64，libc++
// 构建/运行/测试：见同目录 Makefile（make / make run / make test）
// 验证状态：已验证（Apple clang 21.0.0，-std=c++17 -Wall -Wextra 本机实测：编译零警告、运行通过）
#pragma once

#include <cstddef>
#include <functional>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "storage.h"

namespace querydemo {

// ============ 执行器抽象：拉取式（pull）迭代语义 ============
class IExecutor {
public:
    virtual ~IExecutor() = default;

    virtual void open() = 0;                 // 复位到第一行之前（可重复执行）
    virtual std::optional<Row> next() = 0;   // 拉下一行；耗尽返回空
    virtual void close() = 0;                // 收尾（demo 中多为空操作）
    virtual std::string describe() const = 0;  // 递归拼接整条执行计划
};

// ---- 节点 1：表扫描（叶子节点，唯一接触 IStorage 的地方） ----
class TableScanExecutor final : public IExecutor {
public:
    // 存储以 const IStorage& 注入（非拥有）：存储生命周期由组合根保证
    explicit TableScanExecutor(const IStorage& storage);

    void open() override;
    std::optional<Row> next() override;
    void close() override;
    std::string describe() const override;

private:
    const IStorage& storage_;
    std::size_t index_{0};
};

// ---- 节点 2：过滤（包装上游 + 谓词；谓词不满足就继续向上游拉） ----
class FilterExecutor final : public IExecutor {
public:
    using Predicate = std::function<bool(const Row&)>;

    // label：条件的人类可读描述（如 "age >= 18"），仅用于打印执行计划
    FilterExecutor(std::unique_ptr<IExecutor> upstream, Predicate predicate,
                   std::string label);

    void open() override;
    std::optional<Row> next() override;
    void close() override;
    std::string describe() const override;

private:
    std::unique_ptr<IExecutor> upstream_;  // 独占持有上游（管道生命周期沿此传递）
    Predicate predicate_;
    std::string label_;
};

// ---- 节点 3：投影（挑列，丢弃未选列） ----
class ProjectExecutor final : public IExecutor {
public:
    ProjectExecutor(std::unique_ptr<IExecutor> upstream,
                    std::vector<std::string> columns);

    void open() override;
    std::optional<Row> next() override;
    void close() override;
    std::string describe() const override;

private:
    std::unique_ptr<IExecutor> upstream_;
    std::vector<std::string> columns_;
};

// ---- 节点 4：限量（取够即停） ----
class LimitExecutor final : public IExecutor {
public:
    LimitExecutor(std::unique_ptr<IExecutor> upstream, std::size_t limit);

    void open() override;
    std::optional<Row> next() override;
    void close() override;
    std::string describe() const override;

private:
    std::unique_ptr<IExecutor> upstream_;
    std::size_t limit_;
    std::size_t remaining_{0};
};

}  // namespace querydemo
