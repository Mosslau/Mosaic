// exercises/sol-04-iexecutor.cpp —— 练习 4 参考实现：为查询执行器抽象 IExecutor 接口
// 思路：pull 模型（拉取式）执行器接口 open/next/close + describe；节点只包上游（组合，
// unique_ptr 独占所有权沿管道传递）；Filter 是「拉直到谓词满足或上游耗尽」，Limit 数到即止；
// 执行器换谓词/上限即换管道——同一 ScanExecutor 可复用于不同查询。
//
// 验证环境：Apple clang 21.0.0（c++）/ Homebrew clang 21.1.8（clang++），macOS arm64，libc++
// 编译（在 exercises/ 目录内执行）：clang++ -std=c++17 -Wall -Wextra sol-04-iexecutor.cpp -o /tmp/ph17cpp-sol04// 运行：/tmp/ph17cpp-sol04
// 测试：main 自带断言式自检（check 计数，失败非零退出）
// 预期输出：两条管道的执行计划 + 结果行 + 断言行 + 全部通过，退出码 0
// 验证状态：已验证（Apple clang 21.0.0，-std=c++17 -Wall -Wextra 本机实测：编译零警告、运行通过）
#include <functional>
#include <iostream>
#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace {

struct Row {
    int id;
    std::string name;
    int score;
};

// ============ IExecutor：执行器抽象（pull 模型） ============
class IExecutor {
public:
    virtual ~IExecutor() = default;

    virtual void open() = 0;                          // 复位到「第一行之前」
    virtual std::optional<Row> next() = 0;            // 拉下一行；耗尽返回 std::nullopt
    virtual void close() = 0;                         // 释放/收尾
    virtual std::string describe() const = 0;         // 打印整条执行计划
};

// ---- 节点 1：扫描源（数据源非拥有引用注入） ----
class ScanExecutor final : public IExecutor {
public:
    explicit ScanExecutor(const std::vector<Row>& rows) : rows_(rows) {}

    void open() override { index_ = 0; }

    std::optional<Row> next() override {
        if (index_ >= rows_.size()) {
            return std::nullopt;  // 耗尽：结束语义
        }
        return rows_[index_++];
    }

    void close() override {}

    std::string describe() const override { return "scan(source)"; }

private:
    const std::vector<Row>& rows_;  // 非拥有：数据源由组合处保证存活
    std::size_t index_{0};
};

// ---- 节点 2：过滤（包装上游 + 谓词） ----
class FilterExecutor final : public IExecutor {
public:
    using Predicate = std::function<bool(const Row&)>;

    FilterExecutor(std::unique_ptr<IExecutor> upstream, Predicate predicate)
        : upstream_(std::move(upstream)), predicate_(std::move(predicate)) {}

    void open() override { upstream_->open(); }

    std::optional<Row> next() override {
        // 循环拉取：不满足谓词的行直接跳过，继续向上游要下一行
        while (auto row = upstream_->next()) {
            if (predicate_(*row)) {
                return row;
            }
        }
        return std::nullopt;
    }

    void close() override { upstream_->close(); }

    std::string describe() const override {
        return upstream_->describe() + " -> filter(谓词)";
    }

private:
    std::unique_ptr<IExecutor> upstream_;  // 独占持有上游：管道生命周期自动传递
    Predicate predicate_;
};

// ---- 节点 3：限量（包装上游 + 行数上限） ----
class LimitExecutor final : public IExecutor {
public:
    LimitExecutor(std::unique_ptr<IExecutor> upstream, std::size_t limit)
        : upstream_(std::move(upstream)), limit_(limit) {}

    void open() override {
        upstream_->open();
        remaining_ = limit_;
    }

    std::optional<Row> next() override {
        if (remaining_ == 0) {
            return std::nullopt;  // 已取够：直接结束
        }
        auto row = upstream_->next();
        if (!row) {
            return std::nullopt;
        }
        --remaining_;
        return row;
    }

    void close() override { upstream_->close(); }

    std::string describe() const override {
        return upstream_->describe() + " -> limit(" + std::to_string(limit_) + ")";
    }

private:
    std::unique_ptr<IExecutor> upstream_;
    std::size_t limit_;
    std::size_t remaining_{0};
};

// ---- 自检小助手 ----
int g_failures = 0;
void check(bool condition, const char* what) {
    std::cout << (condition ? "[通过] " : "[失败] ") << what << '\n';
    if (!condition) {
        ++g_failures;
    }
}

// 跑完一条管道，返回取出的行
std::vector<Row> drain(IExecutor& executor) {
    executor.open();
    std::vector<Row> out;
    while (auto row = executor.next()) {
        out.push_back(*row);
    }
    executor.close();
    return out;
}

}  // namespace

int main() {
    // 数据源（组合处保证其存活期覆盖全部管道使用）
    const std::vector<Row> rows{
        {1, "alice", 88}, {2, "bob", 45}, {3, "carol", 92},
        {4, "dave", 59},  {5, "erin", 73},
    };

    // ---- 管道 1：score >= 60，取前 2 ----
    auto pipeline = std::make_unique<LimitExecutor>(
        std::make_unique<FilterExecutor>(
            std::make_unique<ScanExecutor>(rows),
            [](const Row& r) { return r.score >= 60; }),
        2);
    std::cout << "计划: " << pipeline->describe() << '\n';

    const auto first_page = drain(*pipeline);
    check(first_page.size() == 2, "管道 1 取出 2 行");
    check(first_page[0].name == "alice" && first_page[1].name == "carol",
          "管道 1 行序与内容正确（alice, carol）");

    // ---- 管道 2：换谓词与上限——同一个 ScanExecutor 理念复用，结果随之变化 ----
    auto strict = std::make_unique<LimitExecutor>(
        std::make_unique<FilterExecutor>(
            std::make_unique<ScanExecutor>(rows),
            [](const Row& r) { return r.score >= 90; }),
        5);
    std::cout << "计划: " << strict->describe() << '\n';

    const auto honors = drain(*strict);
    check(honors.size() == 1 && honors[0].name == "carol",
          "管道 2（score >= 90）：只取到 carol");

    // ---- 复位语义：open() 让同一管道对象可再次执行（结果一致） ----
    auto& pipeline_obj = *pipeline;
    const auto second_page = drain(pipeline_obj);
    check(second_page.size() == 2 && second_page[0].name == "alice",
          "open() 复位后同一管道可再次执行，结果一致");

    std::cout << (g_failures == 0 ? "全部通过，退出码 0" : "存在失败") << '\n';
    return g_failures == 0 ? 0 : 1;
}
