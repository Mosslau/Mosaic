// examples/ex01-test-catch2.cpp —— Calculator 的 Catch2 v3 真实版本
// ⚠️ 未在本环境验证：本机未安装 Catch2（brew 无 catch2）。语法遵循 Catch2 v3 官方文档。
//
// 安装与构建（未在本环境验证）：
//   brew install catch2
//   clang++ -std=c++20 -Wall -Wextra ex01-test-catch2.cpp \
//       -I/opt/homebrew/include -L/opt/homebrew/lib -lCatch2Main -lCatch2 \
//       -o /tmp/ph16cpp-ex01-catch2 && /tmp/ph16cpp-ex01-catch2
//
// Catch2 与 GoogleTest 的风格差异：TEST_CASE + SECTION 天然支持「一个场景多个分支」，
// REQUIRE（致命）/ CHECK（非致命）对应 ASSERT_*/EXPECT_*；BDD 风格（SCENARIO/GIVEN/WHEN/THEN）
// 是 Catch2 的招牌，这里演示 SECTION 即可看出与 GoogleTest fixture 的思路差异。
#include <catch2/catch_test_macros.hpp>

#include "ex01-calculator.h"

TEST_CASE("Calculator 加减除", "[calculator]") {   // [calculator] 是 tag，可按 tag 过滤运行
    SECTION("加法") {                               // SECTION：同一用例内的独立分支，各自从头执行
        REQUIRE(Calculator::add(1, 2) == 3);        // REQUIRE：失败即中止本 SECTION
        CHECK(Calculator::add(-1, 1) == 0);         // CHECK：失败后继续
    }
    SECTION("除法") {
        REQUIRE(Calculator::divide(7, 2) == 3);
        REQUIRE_THROWS_AS(Calculator::divide(1, 0), std::invalid_argument);
        REQUIRE_NOTHROW(Calculator::divide(4, 2));
    }
}
