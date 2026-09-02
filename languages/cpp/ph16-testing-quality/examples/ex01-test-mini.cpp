// examples/ex01-test-mini.cpp —— 用最小断言框架给 Calculator 写测试（已验证）
// 本机无 GoogleTest/Catch2（brew 未安装），本文件用同构的 mini 框架演示
// 「TEST 用例 + EXPECT 断言 + 汇总退出码」的核心模式；GoogleTest/Catch2 真实版本
// 见 ex01-test-gtest.cpp / ex01-test-catch2.cpp（未在本环境验证）。
//
// 验证环境：macOS arm64，Apple clang 21.0.0（c++）+ Homebrew clang 21.1.8（clang++）
// 编译：c++ -std=c++20 -Wall -Wextra ex01-test-mini.cpp -o /tmp/ph16cpp-ex01-mini
// 运行：/tmp/ph16cpp-ex01-mini        # 退出码 0 = 全过，1 = 有失败（CI 信号）
#include <stdexcept>

#include "ex01-calculator.h"
#include "ex01-mini-test.h"

MINI_TEST(CalculatorTest, Add) {                 // 对应 GoogleTest: TEST(CalculatorTest, Add)
    MINI_EXPECT_EQ(Calculator::add(1, 2), 3);    // 对应 EXPECT_EQ
    MINI_EXPECT_EQ(Calculator::add(-1, 1), 0);   // 边界：正负相消
}

MINI_TEST(CalculatorTest, DivideNormal) {
    MINI_EXPECT_EQ(Calculator::divide(7, 2), 3);  // 整数除法截断
}

MINI_TEST(CalculatorTest, DivideByZeroThrows) {   // 对应 GoogleTest: EXPECT_THROW
    bool threw = false;
    try {
        (void)Calculator::divide(1, 0);
    } catch (const std::invalid_argument&) {
        threw = true;
    }
    MINI_EXPECT_TRUE(threw);
}

int main() {
    return MINI_RUN_ALL_TESTS();
}
