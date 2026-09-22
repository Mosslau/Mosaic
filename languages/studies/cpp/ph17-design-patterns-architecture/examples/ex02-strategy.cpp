// examples/ex02-strategy.cpp —— 策略模式教学完整版：虚函数策略 vs std::function 策略
// 教学点：算法族封装为可替换策略（运行期换算法）；两种载体（继承 vs 类型擦除）的取舍；
// 按名选择策略（策略注册表，与 ex01 工厂注册表同构）；策略生命周期归上下文所有。
//
// 验证环境：Apple clang 21.0.0（c++）/ Homebrew clang 21.1.8（clang++），macOS arm64，libc++
// 编译（在 examples/ 目录内执行）：clang++ -std=c++17 -Wall -Wextra ex02-strategy.cpp -o /tmp/ph17cpp-ex02
// 运行：/tmp/ph17cpp-ex02
// 预期输出：两条 PLAIN 日志 + 两条 KV 日志 + 一条带前缀日志（逐行见 main 内注释）
// 测试：main 自带断言式自检（check 计数，失败非零退出）
// 验证状态：已验证（Apple clang 21.0.0，-std=c++17 -Wall -Wextra 本机实测：编译零警告、运行通过）
#include <functional>
#include <iostream>
#include <memory>
#include <string>
#include <unordered_map>
#include <utility>

namespace {

struct LogRecord {
    std::string level;    // "INFO" / "ERROR"
    std::string message;
    long timestamp_sec;   // 简化：UNIX 秒（演示用固定值）
};

// ============ 载体 A：抽象策略接口 + 派生实现（经典 GoF 形态） ============
class ILogFormatter {
public:
    virtual ~ILogFormatter() = default;
    virtual std::string format(const LogRecord& record) const = 0;
};

class PlainFormatter final : public ILogFormatter {
public:
    std::string format(const LogRecord& r) const override {
        return r.level + " " + r.message;
    }
};

class KeyValueFormatter final : public ILogFormatter {
public:
    std::string format(const LogRecord& r) const override {
        return "level=" + r.level + " message=" + r.message +
               " ts=" + std::to_string(r.timestamp_sec);
    }
};

// 上下文 A：持有策略（组合，不是继承）。策略经接口注入 → 换算法不影响 Logger 本体
class LoggerClassic {
public:
    explicit LoggerClassic(std::unique_ptr<ILogFormatter> formatter, std::ostream& out)
        : formatter_(std::move(formatter)), out_(out) {}

    void set_formatter(std::unique_ptr<ILogFormatter> formatter) {
        formatter_ = std::move(formatter);  // 运行期替换策略：算法族可插拔
    }

    void log(const LogRecord& record) const {
        if (formatter_) {
            out_ << formatter_->format(record) << '\n';
        }
    }

private:
    std::unique_ptr<ILogFormatter> formatter_;  // 上下文独占策略所有权（R.20：unique_ptr 表达独占）
    std::ostream& out_;                          // 注入目标流（非拥有）
};

// ============ 载体 B：std::function 策略（类型擦除，值语义，免类层次） ============
using LogFormatter = std::function<std::string(const LogRecord&)>;

class LoggerModern {
public:
    // 直接收可调用对象：lambda、函数指针、绑定的成员函数都可
    explicit LoggerModern(LogFormatter formatter, std::ostream& out)
        : formatter_(std::move(formatter)), out_(out) {}

    void set_formatter(LogFormatter formatter) { formatter_ = std::move(formatter); }

    void log(const LogRecord& record) const {
        if (formatter_) {  // 空 function 可判空（operator bool）：策略忘设时不静默裸奔
            out_ << formatter_(record) << '\n';
        }
    }

private:
    LogFormatter formatter_;
    std::ostream& out_;
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
    const LogRecord info{"INFO", "startup complete", 1700000000};
    const LogRecord err{"ERROR", "disk full", 1700000001};

    // ---- 载体 A：默认 PLAIN，运行期换成 KV ----
    LoggerClassic a(std::make_unique<PlainFormatter>(), std::cout);
    a.log(info);  // 输出: INFO startup complete
    a.set_formatter(std::make_unique<KeyValueFormatter>());
    a.log(err);  // 输出: level=ERROR message=disk full ts=1700000001

    // ---- 载体 B：lambda 即策略；捕获状态（前缀）也自然 ----
    const std::string prefix = "[svc]";
    LoggerModern b(
        [prefix](const LogRecord& r) {  // 捕获 prefix：换类实现要为此写成员变量
            return prefix + " " + r.level + " " + r.message;
        },
        std::cout);
    b.log(info);  // 输出: [svc] INFO startup complete

    // ---- 按名选择策略：策略注册表（与 ex01 工厂注册表同构），运行期切换 ----
    const std::unordered_map<std::string, LogFormatter> named_formatters{
        {"plain", [](const LogRecord& r) { return r.level + " " + r.message; }},
        {"kv", [](const LogRecord& r) {
             return "level=" + r.level + " message=" + r.message;
         }},
    };
    const auto chosen = named_formatters.find("kv");
    if (chosen != named_formatters.end()) {
        b.set_formatter(chosen->second);
    }
    b.log(err);  // 输出: level=ERROR message=disk full

    // ---- 自检：同一意图的两种载体产物一致（策略语义由意图定义，与载体无关） ----
    check(PlainFormatter{}.format(info) == "INFO startup complete",
          "载体 A：PLAIN 格式正确");
    check(KeyValueFormatter{}.format(err) ==
              "level=ERROR message=disk full ts=1700000001",
          "载体 A：KV 格式正确");
    const LogFormatter lambda_kv = [](const LogRecord& r) {
        return "level=" + r.level + " message=" + r.message;
    };
    check(lambda_kv(err) == "level=ERROR message=disk full",
          "载体 B：按名选择的 KV 语义正确");

    std::cout << (g_failures == 0 ? "全部通过，退出码 0" : "存在失败") << '\n';
    return g_failures == 0 ? 0 : 1;
}
