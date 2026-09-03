// examples/ex03-observer.cpp —— 观察者模式教学完整版：一对多状态通知 + 生命周期管理
// 教学点：subject 不依赖具体订阅者（面向接口/回调）；「忘了退订 → 悬挂指针」是 C++ 观察者
// 第一大坑，本示例给出 RAII 退订 Token 方案（析构自动退订）；通知期间列表可能被改，
// 用快照拷贝防迭代器失效；回调里的异常用 try/catch 隔离，防止一个订阅者打断全体。
//
// 验证环境：Apple clang 21.0.0（c++）/ Homebrew clang 21.1.8（clang++），macOS arm64，libc++
// 编译（在 examples/ 目录内执行）：clang++ -std=c++17 -Wall -Wextra ex03-observer.cpp -o /tmp/ph17cpp-ex03
// 运行：/tmp/ph17cpp-ex03
// 预期输出：见 main() 内注释（订阅→通知→退订→不再通知）
// 测试：main 自带断言式自检（check 计数，失败非零退出）
// 验证状态：已验证（Apple clang 21.0.0，-std=c++17 -Wall -Wextra 本机实测：编译零警告、运行通过）
#include <cstddef>
#include <exception>
#include <functional>
#include <iostream>
#include <string>
#include <utility>
#include <vector>

namespace {

// ============ subject：天气站。观察者 = 一个回调（类型擦除，无需继承） ============
class WeatherStation {
public:
    using ListenerId = std::size_t;
    using Listener = std::function<void(double celsius)>;

    // RAII 退订 Token：析构自动退订。「记得退订」从人肉纪律变成编译器保证
    class Subscription {
    public:
        Subscription() = default;  // 默认构造 = 空句柄（可移动赋值的目标）
        Subscription(WeatherStation* owner, ListenerId id) : owner_(owner), id_(id) {}

        ~Subscription() { reset(); }

        // 句柄按值传递会复制 → 禁拷贝，只允许移动（一次订阅对应唯一句柄）
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
        WeatherStation* owner_{nullptr};
        ListenerId id_{0};
    };

    // 订阅：返回句柄；句柄析构（或 reset()）即退订
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

    void set_temperature(double celsius) {
        temperature_ = celsius;
        notify();
    }

    double temperature() const { return temperature_; }

private:
    void notify() {
        // 快照拷贝：通知期间订阅者可能退订/新增（回调里改 listeners_ 会失效迭代器）
        const std::vector<Listener> snapshot = listeners_;
        for (const Listener& listener : snapshot) {
            if (!listener) {
                continue;
            }
            try {
                listener(temperature_);
            } catch (const std::exception& e) {
                // 一个订阅者抛异常不该打断其他订阅者——隔离后继续（E.17 的务实面）
                std::cout << "  订阅者回调异常被隔离: " << e.what() << '\n';
            }
        }
    }

    std::vector<Listener> listeners_;
    std::vector<ListenerId> ids_;  // 与 listeners_ 平行：id 换退订索引
    ListenerId next_id_{0};
    double temperature_{0.0};
};

// ---- 订阅者示例：纯数据收集（无继承、无接口）----
struct Display {
    std::string name;
    double last_reading{0.0};
    int notified_count{0};

    void on_change(double celsius) {
        last_reading = celsius;
        ++notified_count;
    }
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
    WeatherStation station;
    Display screen{"screen"};
    Display logger{"logger"};
    Display archive{"archive"};

    // 订阅：把成员函数包成 lambda（捕获 this 等价于经典「观察者接口」的注册）
    auto sub_screen = station.subscribe([&screen](double t) { screen.on_change(t); });
    auto sub_logger = station.subscribe([&logger](double t) { logger.on_change(t); });
    auto sub_archive = station.subscribe([&archive](double t) { archive.on_change(t); });

    station.set_temperature(21.5);
    std::cout << "  21.5 度：screen=" << screen.last_reading
              << " logger=" << logger.last_reading
              << " archive=" << archive.last_reading << '\n';
    check(screen.notified_count == 1 && logger.notified_count == 1 &&
              archive.notified_count == 1,
          "三个订阅者都收到首次通知");

    // ---- RAII 退订：直接丢弃句柄（作用域结束/移动赋值），无需记得调用 ----
    sub_logger = WeatherStation::Subscription{};  // 移动赋值空句柄 → logger 自动退订
    check(logger.notified_count == 1, "退订后 logger 不再收到通知");

    station.set_temperature(22.0);
    check(screen.last_reading == 22.0 && screen.notified_count == 2,
          "screen 收到第二次通知");
    check(logger.last_reading == 21.5 && logger.notified_count == 1,
          "logger 停在 21.5（已退订）");
    check(archive.notified_count == 2, "archive 仍订阅中");

    // ---- 回调异常隔离：抛异常的订阅者不影响他人 ----
    auto sub_throwing = station.subscribe([](double) {
        throw std::runtime_error("buggy listener");
    });
    station.set_temperature(23.0);  // 输出一行「订阅者回调异常被隔离」
    check(screen.notified_count == 3, "异常订阅者加入后 screen 仍收到通知");

    // ---- 移动语义：句柄可移动（进容器、随订阅者搬走）；reset 幂等 ----
    WeatherStation::Subscription moved = std::move(sub_throwing);  // 订阅权搬家
    sub_throwing.reset();  // 已是空句柄：reset 无副作用（幂等）
    moved.reset();         // 真正退订掉「抛异常」的订阅者
    check(true, "Token 可移动、reset 幂等（接口层面验证）");

    station.set_temperature(25.0);  // 抛异常订阅者已退订 → 不再打印「异常被隔离」
    check(screen.notified_count == 4, "全部订阅者退订路径正确，screen 收第 4 次");

    std::cout << (g_failures == 0 ? "全部通过，退出码 0" : "存在失败") << '\n';
    return g_failures == 0 ? 0 : 1;
}
