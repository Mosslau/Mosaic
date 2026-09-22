// exercises/sol-01-bank-account-test.cpp —— 练习 1 参考实现：给核心类写测试（已验证）
// 被测类 BankAccount 内嵌于此（自包含，单文件可编译）；测试用内嵌最小断言助手，
// 与 examples/ex01-mini-test.h 同构（真实工程用 GoogleTest/Catch2）。
//
// 验证环境：Apple clang 21.0.0 + Homebrew clang 21.1.8
// 编译：c++ -std=c++20 -Wall -Wextra sol-01-bank-account-test.cpp -o /tmp/ph16cpp-sol01
// 运行：/tmp/ph16cpp-sol01
// 预期输出（退出码 0）：
//   [通过] 开户默认余额为 0
//   [通过] 存款累加余额
//   [通过] 取款扣减余额
//   [通过] 透支抛 invalid_argument 且余额不变
//   [通过] 负额存款抛 invalid_argument
//   5 个用例全部通过
#include <cstdio>
#include <stdexcept>

// ---- 被测类 ----
class BankAccount {
public:
    void deposit(int cents) {
        if (cents <= 0) {
            throw std::invalid_argument("deposit must be positive");
        }
        balance_ += cents;
    }

    void withdraw(int cents) {
        if (cents > balance_) {                    // 先校验，失败时状态不变（强保证）
            throw std::invalid_argument("overdraft");
        }
        balance_ -= cents;
    }

    int balance() const { return balance_; }       // Con.2：查询函数 const

private:
    int balance_{0};                               // ES.20：声明即初始化
};

// ---- 最小断言助手（与 examples/ex01-mini-test.h 同构的教学版） ----
namespace {
int g_failures = 0;

void check(bool ok, const char* case_name) {
    if (!ok) {
        ++g_failures;
        std::printf("[失败] %s\n", case_name);
    } else {
        std::printf("[通过] %s\n", case_name);
    }
}

template <typename Fn>
bool throws_invalid_argument(Fn&& fn) {
    try {
        fn();
    } catch (const std::invalid_argument&) {
        return true;
    }
    return false;
}
}  // namespace

int main() {
    {   // 用例 1：构造后状态
        const BankAccount acc;
        check(acc.balance() == 0, "开户默认余额为 0");
    }
    {   // 用例 2：正常路径
        BankAccount acc;
        acc.deposit(1000);
        acc.deposit(500);
        check(acc.balance() == 1500, "存款累加余额");
    }
    {   // 用例 3：正常路径
        BankAccount acc;
        acc.deposit(1000);
        acc.withdraw(300);
        check(acc.balance() == 700, "取款扣减余额");
    }
    {   // 用例 4：异常路径 + 失败后的状态不变性（测试异常不只是「抛没抛」）
        BankAccount acc;
        acc.deposit(100);
        const bool threw = throws_invalid_argument([&] { acc.withdraw(200); });
        check(threw && acc.balance() == 100, "透支抛 invalid_argument 且余额不变");
    }
    {   // 用例 5：边界/非法输入
        BankAccount acc;
        check(throws_invalid_argument([&] { acc.deposit(-1); }), "负额存款抛 invalid_argument");
    }

    std::printf(g_failures == 0 ? "5 个用例全部通过\n" : "%d 个用例失败\n", g_failures);
    return g_failures == 0 ? 0 : 1;
}
