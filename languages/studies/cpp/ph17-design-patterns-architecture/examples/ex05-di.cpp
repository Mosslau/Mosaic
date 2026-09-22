// examples/ex05-di.cpp —— 依赖注入与组合根教学完整版（手写 DI，无框架）
// 教学点：OrderService 只依赖抽象接口（IOrderStore / IPaymentGateway），自己不 new 任何
// 具体实现；具体对象在「组合根」（main 组装处）一次性组装好再注入；换实现/换 mock 不改
// 业务代码——roadmap 验收「能通过接口 mock 依赖」在此兑现（ph16 可测试性伏笔的落地）。
//
// 生命周期教学：store 被两个 service 共享 → shared_ptr 表达共享所有权；
// 只被一个消费者独占的依赖应优先 unique_ptr（R.21：能 unique 不 shared）。
//
// 验证环境：Apple clang 21.0.0（c++）/ Homebrew clang 21.1.8（clang++），macOS arm64，libc++
// 编译（在 examples/ 目录内执行）：clang++ -std=c++17 -Wall -Wextra ex05-di.cpp -o /tmp/ph17cpp-ex05
// 运行：/tmp/ph17cpp-ex05
// 预期输出：见 main() 内注释（下单成功/失败、共享存储计数）
// 测试：main 自带断言式自检（check 计数，失败非零退出）
// 验证状态：已验证（Apple clang 21.0.0，-std=c++17 -Wall -Wextra 本机实测：编译零警告、运行通过）
#include <iostream>
#include <memory>
#include <string>
#include <utility>
#include <vector>

namespace {

struct Order {
    std::string id;
    int amount_cents;
};

// ============ 抽象接口层：业务依赖只指向这里（依赖方向指向稳定抽象） ============
class IOrderStore {
public:
    virtual ~IOrderStore() = default;
    virtual void save(const Order& order) = 0;
    virtual std::size_t count() const = 0;
};

class IPaymentGateway {
public:
    virtual ~IPaymentGateway() = default;
    virtual bool charge(int amount_cents) = 0;  // 返回扣款是否成功（演示语义）
};

// ============ 具体实现层：可替换、可 mock ============
class MemoryOrderStore final : public IOrderStore {
public:
    void save(const Order& order) override { orders_.push_back(order); }
    std::size_t count() const override { return orders_.size(); }

private:
    std::vector<Order> orders_;
};

// 演示用假网关：succeed 参数让「成功/失败」两个场景共用这一个实现
class StubPaymentGateway final : public IPaymentGateway {
public:
    explicit StubPaymentGateway(bool succeed) : succeed_(succeed) {}

    bool charge(int amount_cents) override {
        (void)amount_cents;  // 演示实现不真正扣款
        return succeed_;
    }

private:
    bool succeed_;
};

// ============ 业务层：只知道接口，构造注入依赖 ============
class OrderService {
public:
    OrderService(std::shared_ptr<IOrderStore> store, std::shared_ptr<IPaymentGateway> gateway)
        : store_(std::move(store)), gateway_(std::move(gateway)) {}

    // 业务规则：扣款成功才落库（强保证思路——失败不留脏数据）
    bool place(const Order& order) {
        if (!gateway_->charge(order.amount_cents)) {
            return false;
        }
        store_->save(order);
        return true;
    }

private:
    std::shared_ptr<IOrderStore> store_;
    std::shared_ptr<IPaymentGateway> gateway_;
};

// 第二个消费者：报表服务只读 store（共享所有权的理由）
class OrderReporter {
public:
    explicit OrderReporter(std::shared_ptr<IOrderStore> store) : store_(std::move(store)) {}
    std::size_t total_orders() const { return store_->count(); }

private:
    std::shared_ptr<IOrderStore> store_;
};

// ---- 自检小助手 ----
int g_failures = 0;
void check(bool condition, const char* what) {
    std::cout << (condition ? "[通过] " : "[失败] ") << what << '\n';
    if (!condition) {
        ++g_failures;
    }
}

}  // namespace

int main() {
    // ============ 组合根：全程序唯一知道「具体实现是谁」的地方 ============
    // 注意：组合根把「组装」集中在这里，业务层保持对具体类型零知识。
    // store 用 shared_ptr：要被 OrderService 与 OrderReporter 两个消费者共享。
    auto store = std::make_shared<MemoryOrderStore>();
    auto ok_gateway = std::make_shared<StubPaymentGateway>(true);
    auto fail_gateway = std::make_shared<StubPaymentGateway>(false);

    OrderService checkout(store, ok_gateway);
    OrderReporter reporter(store);  // 共享同一个 store 实例

    // ---- 成功路径 ----
    const bool placed = checkout.place(Order{"o-001", 5000});
    std::cout << "  下单 o-001: " << (placed ? "成功" : "失败") << '\n';
    check(placed, "扣款成功 → 订单落库");
    check(reporter.total_orders() == 1, "共享 store：报表服务看到 1 单");

    // ---- 失败路径：换一个 mock（succeed=false），业务代码零改动 ----
    OrderService checkout_with_failing_gateway(store, fail_gateway);
    const bool failed = checkout_with_failing_gateway.place(Order{"o-002", 9999});
    std::cout << "  下单 o-002: " << (failed ? "成功" : "失败（扣款被拒）") << '\n';
    check(!failed, "扣款失败 → 订单不落库（业务规则正确）");
    check(reporter.total_orders() == 1, "失败订单未污染存储");

    // ---- 与「服务自己 new 依赖」的反模式对比 ----
    // 反模式：OrderService 内部 new MemoryOrderStore() + 全局支付网关单例 ——
    //   ① 换实现要改业务代码；② 测试无法注入假网关；③ 全局单例隐藏依赖图。
    // 本示例的构造注入让三条都不成立：依赖全部从参数进来，可见、可换、可 mock。

    std::cout << (g_failures == 0 ? "全部通过，退出码 0" : "存在失败") << '\n';
    return g_failures == 0 ? 0 : 1;
}
