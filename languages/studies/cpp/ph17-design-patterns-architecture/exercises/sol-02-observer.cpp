// exercises/sol-02-observer.cpp —— 练习 2 参考实现：用观察者实现状态变化通知
// 思路：DeviceMonitor 持开关与温度；set_* 只在「值真的变化」时才通知全体订阅者；
// 订阅回调经 RAII 句柄管理（析构自动退订）；通知期间订阅表可能被回调改动，
// 用快照拷贝防迭代器失效（回调内退订自己不会破坏遍历）。
//
// 验证环境：Apple clang 21.0.0（c++）/ Homebrew clang 21.1.8（clang++），macOS arm64，libc++
// 编译（在 exercises/ 目录内执行）：clang++ -std=c++17 -Wall -Wextra sol-02-observer.cpp -o /tmp/ph17cpp-sol02// 运行：/tmp/ph17cpp-sol02
// 测试：main 自带断言式自检（check 计数，失败非零退出）
// 预期输出：每个订阅者的通知计数 + 断言行 + 全部通过，退出码 0
// 验证状态：已验证（Apple clang 21.0.0，-std=c++17 -Wall -Wextra 本机实测：编译零警告、运行通过）
#include <cstddef>
#include <exception>
#include <functional>
#include <iostream>
#include <string>
#include <utility>
#include <vector>

namespace {

struct DeviceState {
    bool powered{false};
    int temperature_c{20};  // 演示初始 20 度
};

// ============ Subject：设备监视器 ============
class DeviceMonitor {
public:
    using ListenerId = std::size_t;
    using Listener = std::function<void(const DeviceState&)>;

    // RAII 订阅句柄：析构自动退订（防「忘了退订 → 悬挂」）
    class Subscription {
    public:
        Subscription() = default;
        Subscription(DeviceMonitor* owner, ListenerId id) : owner_(owner), id_(id) {}
        ~Subscription() { reset(); }

        Subscription(const Subscription&) = delete;
        Subscription& operator=(const Subscription&) = delete;
        Subscription(Subscription&& other) noexcept
            : owner_(other.owner_), id_(other.id_) {
            other.owner_ = nullptr;
        }
        Subscription& operator=(Subscription&& other) noexcept {
            if (this != &other) {
                reset();
                owner_ = other.owner_;
                id_ = other.id_;
                other.owner_ = nullptr;
            }
            return *this;
        }

        void reset() {
            if (owner_ != nullptr) {
                owner_->unsubscribe(id_);
                owner_ = nullptr;
            }
        }

    private:
        DeviceMonitor* owner_{nullptr};
        ListenerId id_{0};
    };

    Subscription subscribe(Listener listener) {
        listeners_.push_back(std::move(listener));
        ids_.push_back(next_id_);
        return Subscription(this, next_id_++);
    }

    void unsubscribe(ListenerId id) {
        for (std::size_t i = 0; i < ids_.size(); ++i) {
            if (ids_[i] == id) {
                ids_.erase(ids_.begin() + static_cast<std::ptrdiff_t>(i));
                listeners_.erase(listeners_.begin() + static_cast<std::ptrdiff_t>(i));
                return;
            }
        }
    }

    // ---- 修改接口：值没变就不通知（变化检测是语义核心） ----
    void set_power(bool powered) {
        if (state_.powered == powered) {
            return;  // 无变化：不产生通知
        }
        state_.powered = powered;
        notify();
    }

    void set_temperature(int celsius) {
        if (state_.temperature_c == celsius) {
            return;
        }
        state_.temperature_c = celsius;
        notify();
    }

    const DeviceState& state() const { return state_; }

private:
    void notify() {
        const DeviceState snapshot = state_;  // 值快照：通知期间状态再变也不影响本轮语义
        const std::vector<Listener> listeners_snapshot = listeners_;
        for (const Listener& listener : listeners_snapshot) {
            if (!listener) {
                continue;
            }
            try {
                listener(snapshot);
            } catch (const std::exception& e) {
                std::cout << "  订阅者回调异常被隔离: " << e.what() << '\n';
            }
        }
    }

    std::vector<Listener> listeners_;
    std::vector<ListenerId> ids_;  // 与 listeners_ 平行：id ↔ 索引
    ListenerId next_id_{0};
    DeviceState state_;
};

// 订阅者示例：纯数据收集对象（无继承）
struct Monitor {
    std::string name;
    int notified{0};
    DeviceState last;
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
    DeviceMonitor device;
    Monitor console{"console"};
    Monitor alarm{"alarm"};
    Monitor audit{"audit"};

    // 三个订阅者
    auto sub_console =
        device.subscribe([&console](const DeviceState& s) { console.last = s; ++console.notified; });
    auto sub_alarm =
        device.subscribe([&alarm](const DeviceState& s) { alarm.last = s; ++alarm.notified; });
    auto sub_audit =
        device.subscribe([&audit](const DeviceState& s) { audit.last = s; ++audit.notified; });

    // ---- 初始 20 度，开电源 → 通知一次 ----
    device.set_power(true);
    check(console.notified == 1 && alarm.notified == 1 && audit.notified == 1,
          "开电源: 三个订阅者各收 1 次通知");

    // ---- 重复赋值同值 → 不通知（变化检测） ----
    device.set_power(true);
    device.set_temperature(20);  // 温度没变
    check(console.notified == 1 && alarm.notified == 1 && audit.notified == 1,
          "重复赋值同值不产生通知");

    // ---- 温度变化 → 再通知一次 ----
    device.set_temperature(35);
    check(console.notified == 2, "温度变化: 订阅者收到第 2 次通知");
    check(console.last.temperature_c == 35, "通知载荷携带最新状态");

    // ---- alarm 在收到第 2 次通知后销毁句柄（模拟「告警器退役」） ----
    sub_alarm = DeviceMonitor::Subscription{};  // 移动赋值空句柄 → 自动退订
    device.set_power(false);
    check(alarm.notified == 2, "alarm 退订后不再增长（停在 2）");
    check(console.notified == 3 && audit.notified == 3, "console/audit 继续收到");

    // ---- 回调里退订自己（快照拷贝保证遍历安全） ----
    DeviceMonitor once_only;
    Monitor m{"once"};
    DeviceMonitor::Subscription sub_self;  // 先声明空句柄，再订阅（lambda 捕获它）
    sub_self = once_only.subscribe([&sub_self, &m](const DeviceState& s) {
        ++m.notified;
        (void)s;
        sub_self.reset();  // 通知期间销毁自己的句柄：合法，快照遍历不受影响
    });
    once_only.set_temperature(1);   // 第 1 次通知
    once_only.set_temperature(2);   // 已退订：不再通知
    once_only.set_temperature(3);
    check(m.notified == 1, "回调内自退订生效: 只收到 1 次通知");

    std::cout << (g_failures == 0 ? "全部通过，退出码 0" : "存在失败") << '\n';
    return g_failures == 0 ? 0 : 1;
}
