// sol-03-query-plan-tree.cpp —— 练习 3 参考实现：查询计划树 demo
// 对应主文档 3.3/3.11 与 roadmap §21 练习「查询计划树 demo」。
// 教学点：查询计划是一棵「运算符树」，本练习用树结构 + 递归做三件事：
// ① 后序遍历自底向上估算每棵子树的输出行数（filter=输入/10，join=子估算乘积，scan=行数）；
// ② 先序遍历打印计划；③ 递归统计节点数/叶子数/最大深度。子节点用 unique_ptr 持有（RAII）。
// 边界：join/filter 的子树个数不合法时 estimate 抛 std::logic_error（显式校验）。
// 复杂度：单次 estimate/统计 O(节点数)；与树深无关的递归深度受树的形状约束。
// 验证环境：Apple clang 21.0.0（/usr/bin/clang++），macOS arm64 + libc++
// 编译/运行：clang++ -std=c++20 -Wall -Wextra sol-03-query-plan-tree.cpp -o /tmp/ph21-sol03 && /tmp/ph21-sol03
// 验证状态：已验证（编译零警告、断言全绿、退出码 0）
#include <algorithm>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

void require(bool cond, const char* what) {
    if (!cond) {
        std::cerr << "FAIL: " << what << '\n';
        std::exit(1);
    }
}

enum class op_kind { scan, filter, join };

const char* kind_name(op_kind k) {
    switch (k) {
        case op_kind::scan: return "scan";
        case op_kind::filter: return "filter";
        case op_kind::join: return "join";
    }
    return "?";
}

class plan_node {
public:
    plan_node(op_kind kind, std::string name, double rows)
        : kind_{kind}, name_{std::move(name)}, rows_{rows} {}

    void add_child(std::unique_ptr<plan_node> child) {
        children_.push_back(std::move(child));
    }

    // 后序遍历：先算孩子再算自己 —— 行数估算自底向上流动
    double estimate_rows() const {
        if (kind_ == op_kind::scan) {
            return rows_;                              // 叶子：scan 直接给源行数
        }
        if (kind_ == op_kind::filter) {
            if (children_.size() != 1) {
                throw std::logic_error("filter must have exactly 1 child");
            }
            return children_[0]->estimate_rows() / 10.0;   // 教学规则：过滤掉 90%
        }
        // join：无 child 或单 child 都不构成合法连接
        if (children_.size() < 2) {
            throw std::logic_error("join must have at least 2 children");
        }
        double product = 1.0;
        for (const auto& child : children_) {
            product *= child->estimate_rows();         // 教学规则：嵌套循环连接的最坏行数
        }
        return product;
    }

    std::size_t node_count() const {
        std::size_t total = 1;
        for (const auto& child : children_) {
            total += child->node_count();
        }
        return total;
    }

    std::size_t leaf_count() const {
        if (children_.empty()) {
            return 1;
        }
        std::size_t total = 0;
        for (const auto& child : children_) {
            total += child->leaf_count();
        }
        return total;
    }

    std::size_t max_depth() const {
        std::size_t best = 0;
        for (const auto& child : children_) {
            best = std::max(best, child->max_depth());
        }
        return best + 1;
    }

    void print(int depth = 0) const {                  // 先序遍历：打印缩进计划
        for (int i = 0; i < depth; ++i) {
            std::cout << "  ";
        }
        std::cout << kind_name(kind_) << ' ' << name_ << " (rows~" << estimate_rows() << ")\n";
        for (const auto& child : children_) {
            child->print(depth + 1);
        }
    }

private:
    op_kind kind_;
    std::string name_;
    double rows_;                                      // 仅 scan 语义使用：源行数
    std::vector<std::unique_ptr<plan_node>> children_; // unique_ptr 持有：析构自动整树回收
};

std::unique_ptr<plan_node> make_scan(const std::string& name, double rows) {
    return std::make_unique<plan_node>(op_kind::scan, name, rows);
}

std::unique_ptr<plan_node> make_filter(const std::string& name,
                                       std::unique_ptr<plan_node> child) {
    auto node = std::make_unique<plan_node>(op_kind::filter, name, 0.0);
    node->add_child(std::move(child));
    return node;
}

std::unique_ptr<plan_node> make_join(const std::string& name,
                                     std::unique_ptr<plan_node> a,
                                     std::unique_ptr<plan_node> b) {
    auto node = std::make_unique<plan_node>(op_kind::join, name, 0.0);
    node->add_child(std::move(a));
    node->add_child(std::move(b));
    return node;
}

void demo_plan() {
    // 计划：join( filter(scan users 1000) , scan orders 5000 )
    // 期望：filter 估 100 → join 估 100 × 5000 = 500000
    auto plan = make_join("j_users_orders",
                          make_filter("f_active", make_scan("scan_users", 1000.0)),
                          make_scan("scan_orders", 5000.0));
    std::cout << "--- plan tree ---\n";
    plan->print();
    require(plan->estimate_rows() == 500000.0, "join estimate = 100 * 5000");
    require(plan->node_count() == 4, "4 nodes in this plan");
    require(plan->leaf_count() == 2, "2 leaves (scan users, scan orders)");
    require(plan->max_depth() == 3, "deepest path join->filter->scan has depth 3");
}

void demo_boundaries() {
    // 非法树必须显式抛错而非静默算错：filter 必须 1 子、join 必须 ≥2 子
    auto bad_filter = std::make_unique<plan_node>(op_kind::filter, "empty_filter", 0.0);
    bool threw = false;
    try {
        (void)bad_filter->estimate_rows();
    } catch (const std::logic_error&) {
        threw = true;
    }
    require(threw, "filter with 0 children throws logic_error");

    auto bad_join = std::make_unique<plan_node>(op_kind::join, "lonely_join", 0.0);
    threw = false;
    try {
        (void)bad_join->estimate_rows();
    } catch (const std::logic_error&) {
        threw = true;
    }
    require(threw, "join with <2 children throws logic_error");
    std::cout << "  boundary: invalid subtree shapes rejected\n";
}

}  // namespace

int main() {
    demo_plan();
    demo_boundaries();
    std::cout << "sol-03-query-plan-tree OK\n";
    return 0;
}
