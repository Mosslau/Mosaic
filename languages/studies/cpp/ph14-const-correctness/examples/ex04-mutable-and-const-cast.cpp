// ex04-mutable-and-const-cast.cpp —— mutable 的正确用途，与 const_cast 的设计气味（正反例对照）
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：c++ -std=c++20 -Wall -Wextra ex04-mutable-and-const-cast.cpp -o /tmp/ph14-ex04
// 运行：/tmp/ph14-ex04
// 危险路径（故意出错，ES.50 反例）：-DPH14_CONST_UB 单独编译运行——
//   修改"真正 const"对象是未定义行为。实测（macOS arm64）：O0 下写入只读段，
//   Bus error: 10（SIGBUS，退出码 138）；O2 下编译器常量折叠、不崩溃但打印 42。
//   勿在未理解 UB 风险的情况下裸跑。
//   c++ -std=c++20 -Wall -Wextra -DPH14_CONST_UB ex04-mutable-and-const-cast.cpp -o /tmp/ph14-ex04-ub
//   /tmp/ph14-ex04-ub
#include <cstdio>
#include <string>

#ifndef PH14_CONST_UB
// ---------------- 正常演示路径 ----------------

// [正例] mutable 缓存：const 成员函数里做"物理可变、逻辑不变"的缓存。
// is_prime 的语义是"查询"，不改变对象逻辑状态；last_n_/last_result_ 只是缓存位。
class PrimeChecker {
public:
    bool is_prime(int n) const {
        if (last_n_ == n) {                       // 命中缓存：不再重算
            std::printf("  is_prime(%d) 命中缓存（mutable 缓存位已就绪）\n", n);
            return last_result_;
        }
        std::printf("  is_prime(%d) 首次计算（写 mutable 缓存位）\n", n);
        last_n_ = n;                              // const 成员函数中允许改 mutable 成员
        last_result_ = compute_prime(n);
        return last_result_;
    }

private:
    static bool compute_prime(int n) {
        if (n < 2) {
            return false;
        }
        for (int d = 2; d * d <= n; ++d) {
            if (n % d == 0) {
                return false;
            }
        }
        return true;
    }

    mutable int last_n_{0};          // mutable：只属于"实现缓存"，不属于逻辑状态
    mutable bool last_result_{false};
};

// [反例 1：设计气味] 通过 const& 参数 const_cast 修改 —— 合法（对象本身非 const）
// 但破坏接口承诺：调用方看到的是 const&，以为只读，实际被改。
void sneaky(const int& v) {
    const_cast<int&>(v) = 999;       // 气味：const 承诺被静默撕毁
}

// [正例对照] 需要修改就明说：非 const 引用参数，零 cast、接口诚实。
void update(int& v) {
    v = 300;
}

int main() {
    std::printf("[1] mutable 缓存（正例）：const 成员函数中缓存计算结果\n");
    const PrimeChecker checker;
    std::printf("  checker.is_prime(17) = %s\n", checker.is_prime(17) ? "true" : "false");
    std::printf("  checker.is_prime(17) = %s（再次查询命中缓存）\n",
                checker.is_prime(17) ? "true" : "false");
    std::printf("  checker.is_prime(18) = %s（新输入，重新计算）\n",
                checker.is_prime(18) ? "true" : "false");

    std::printf("[2] const_cast 气味（反例）：const& 参数被偷偷改写\n");
    int x = 1;
    sneaky(x);                                    // 合法编译，但 x 被改了
    std::printf("  sneaky(x) 之后 x = %d（调用方以为只读，实际被改——接口承诺被破坏）\n", x);

    std::printf("[3] 正例对照：用非 const 引用参数表达「要修改」\n");
    int y = 1;
    update(y);
    std::printf("  update(y) 之后 y = %d（接口明说可写，无需任何 cast）\n", y);

    std::printf("[4] 危险路径提醒：修改真正 const 对象是 UB（ES.50）\n");
    std::printf("  用 -DPH14_CONST_UB 编译单独运行，实测结果见文件头注释/README\n");
    return 0;
}

#else  // PH14_CONST_UB
// ---------------- 危险路径（故意出错） ----------------
int main() {
    static const int k = 42;       // 静态存储期 const：通常落在只读段
    const_cast<int&>(k) = 43;      // UB：修改 const 对象（ES.50 反例）
    std::printf("k = %d（UB：编译器可假设 k 恒为 42，实测值取决于优化与平台）\n", k);
    return 0;
}
#endif
