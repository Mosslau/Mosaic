// examples/ex01-mini-test.h —— 最小断言框架（约 60 行）：演示 GoogleTest 的同构模式
// （TEST 注册 + EXPECT_* 断言 + RUN_ALL_TESTS 汇总），供本机无 GoogleTest/Catch2 环境
// 下练习「给核心类写测试」。注意：它只覆盖单断言计数，不含 fixture/参数化/死亡测试等
// GoogleTest 完整能力——真实工程请用 GoogleTest 或 Catch2（见 ex01-test-gtest.cpp）。
#ifndef EX01_MINI_TEST_H
#define EX01_MINI_TEST_H

#include <cstdio>
#include <functional>
#include <string>
#include <vector>

namespace mini {

struct TestCase {
    std::string suite;   // 对应 GoogleTest 的 TestSuite 名
    std::string name;    // 对应 TEST 的第二个参数
    std::function<void()> fn;
};

// 内联变量（C++17）：每个 TU 共享同一份注册表
inline std::vector<TestCase>& registry() {
    static std::vector<TestCase> tests;
    return tests;
}

inline int& failure_count() {
    static int failures = 0;
    return failures;
}

// 注册器：全局对象的构造函数在 main 之前完成注册（与 GoogleTest 同原理）
struct Registrar {
    Registrar(std::string suite, std::string name, std::function<void()> fn) {
        registry().push_back({std::move(suite), std::move(name), std::move(fn)});
    }
};

inline void report_failure(const char* file, int line, const std::string& expr) {
    ++failure_count();
    std::printf("  [失败] %s:%d: %s\n", file, line, expr.c_str());
}

inline int run_all_tests() {
    int failed_cases = 0;
    for (const auto& tc : registry()) {
        const int before = failure_count();
        std::printf("[运行] %s.%s\n", tc.suite.c_str(), tc.name.c_str());
        tc.fn();
        if (failure_count() == before) {
            std::printf("[通过] %s.%s\n", tc.suite.c_str(), tc.name.c_str());
        } else {
            ++failed_cases;
        }
    }
    std::printf("[汇总] %zu 个用例，%d 个失败\n", registry().size(), failed_cases);
    return failed_cases == 0 ? 0 : 1;   // 退出码即 CI 信号：0 全过，1 有失败
}

}  // namespace mini

// MINI_TEST(Suite, Name) —— 对应 GoogleTest 的 TEST(Suite, Name)
#define MINI_TEST(suite, name)                                                 \
    static void mini_test_##suite##_##name();                                  \
    static ::mini::Registrar mini_reg_##suite##_##name{#suite, #name,          \
                                                       mini_test_##suite##_##name}; \
    static void mini_test_##suite##_##name()

#define MINI_EXPECT_TRUE(cond)                                                 \
    do {                                                                       \
        if (!(cond)) {                                                         \
            ::mini::report_failure(__FILE__, __LINE__, "EXPECT_TRUE(" #cond ")"); \
        }                                                                      \
    } while (0)

#define MINI_EXPECT_EQ(a, b)                                                   \
    do {                                                                       \
        if (!((a) == (b))) {                                                   \
            ::mini::report_failure(__FILE__, __LINE__,                         \
                                   "EXPECT_EQ(" #a ", " #b ")");              \
        }                                                                      \
    } while (0)

#define MINI_RUN_ALL_TESTS() ::mini::run_all_tests()

#endif  // EX01_MINI_TEST_H
