// examples/ex01-test-gtest.cpp —— Calculator 的 GoogleTest 真实版本
// ⚠️ 未在本环境验证：本机未安装 GoogleTest（brew 无 googletest）。本文件是
// 与 ex01-test-mini.cpp 一一对应的「真实框架版」，语法遵循 GoogleTest 官方文档。
//
// 安装与构建（两种方式，均未在本环境验证）：
//   # 方式一：Homebrew
//   brew install googletest
//   clang++ -std=c++20 -Wall -Wextra ex01-test-gtest.cpp \
//       -I/opt/homebrew/include -L/opt/homebrew/lib -lgtest -lgtest_main \
//       -o /tmp/ph16cpp-ex01-gtest && /tmp/ph16cpp-ex01-gtest
//   # 方式二：CMake FetchContent（推荐，见主文档 3.1；版本号以实际拉取为准）
//   FetchContent_Declare(googletest
//       URL https://github.com/google/googletest/archive/refs/tags/v1.15.2.tar.gz)
//   target_link_libraries(... GTest::gtest_main)
//
// 与 mini 框架的对照（同构点）：TEST ↔ MINI_TEST；EXPECT_EQ ↔ MINI_EXPECT_EQ；
// EXPECT_THROW ↔ try/catch + MINI_EXPECT_TRUE；gtest_main 提供的 main ↔ 手写 main + RUN_ALL_TESTS。
#include <gtest/gtest.h>

#include "ex01-calculator.h"

TEST(CalculatorTest, Add) {                  // TEST(测试套件名, 用例名)：自动注册
    EXPECT_EQ(Calculator::add(1, 2), 3);     // EXPECT_*：失败后继续执行（非致命断言）
    EXPECT_EQ(Calculator::add(-1, 1), 0);
    ASSERT_NE(Calculator::add(1, 1), 0);     // ASSERT_*：失败即中止当前用例（致命断言）
}

TEST(CalculatorTest, DivideNormal) {
    EXPECT_EQ(Calculator::divide(7, 2), 3);
}

TEST(CalculatorTest, DivideByZeroThrows) {
    EXPECT_THROW(Calculator::divide(1, 0), std::invalid_argument);  // 异常断言一条搞定
    EXPECT_NO_THROW(Calculator::divide(4, 2));
}
