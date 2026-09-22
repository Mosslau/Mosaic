// exercises/sol-02-tidy-clean.cpp —— 练习 2 参考实现（代码侧）：在 sol-02.clang-tidy
// 的 'bugprone-*,modernize-*,performance-*' 配置下零告警（已验证）。
//
// 验证环境：clang-tidy 21.1.8（/opt/homebrew/opt/llvm/bin/clang-tidy）
// 检查：clang-tidy sol-02-tidy-clean.cpp --config-file=sol-02.clang-tidy -- -std=c++20
//       （WarningsAsErrors='*'，有告警即非零退出；实测零告警、退出码 0）
// 编译：c++ -std=c++20 -Wall -Wextra sol-02-tidy-clean.cpp -o /tmp/ph16cpp-sol02
// 运行：/tmp/ph16cpp-sol02  →  输出：total=9.42
#include <cstdio>
#include <string>
#include <vector>

namespace sol02 {

class Formatter {
public:
    virtual ~Formatter() = default;                  // C.35：多态基类虚析构
    virtual std::string render(double value) const = 0;
};

class MoneyFormatter final : public Formatter {
public:
    explicit MoneyFormatter(std::string currency) : currency_(std::move(currency)) {}
    std::string render(double value) const override {  // C.128：重写必标 override
        return currency_ + " " + std::to_string(value);
    }

private:
    std::string currency_;
};

double total_price(const std::vector<double>& prices) {
    double total = 0.0;
    for (const double price : prices) {              // 范围 for 按 const 引用语义取值
        total += price;
    }
    return total;
}

}  // namespace sol02

int main() {
    const sol02::MoneyFormatter fmt{"CNY"};
    const std::vector<double> prices{3.14, 2.72, 3.56};
    const double total = sol02::total_price(prices);
    const char* env = nullptr;                       // ES.47：nullptr 而非 NULL
    std::printf("total=%.2f%s\n", total, env == nullptr ? "" : env);
    return 0;
}
