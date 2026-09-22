// tests/test_core.cpp —— ph10 工程模板：tests 测试目标
// 简单断言自测：全过退出码 0；任意失败打印并退出 1（真实项目用测试框架，ph16 深入）
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 构建/运行：make test（或 make && ./build/test_core）
// 验证状态：已验证（编译零警告 + 全部断言通过）
#include "core/stats_utils.h"

#include <cmath>
#include <cstdio>
#include <stdexcept>
#include <vector>

static int g_failed = 0;

static void check(bool cond, const char* msg) {
    if (!cond) {
        std::printf("FAIL: %s\n", msg);
        ++g_failed;
    }
}

static void check_close(double a, double b, const char* msg) {
    check(std::fabs(a - b) < 1e-9, msg);
}

// 传一个调用空容器的 lambda，验证四个函数对空输入都抛 std::invalid_argument
template <typename F>
static void check_throws_empty(const char* msg, F&& fn) {
    bool threw = false;
    try {
        fn();
    } catch (const std::invalid_argument&) {
        threw = true;
    }
    check(threw, msg);
}

int main() {
    check_close(stats::mean({1.0, 2.0, 3.0, 4.0}), 2.5, "mean 1..4");
    check_close(stats::median({1.0, 2.0, 3.0}), 2.0, "median odd");
    check_close(stats::median({1.0, 2.0, 3.0, 4.0}), 2.5, "median even");
    check_close(stats::stddev({2, 4, 4, 4, 5, 5, 7, 9}), 2.0, "stddev classic");
    {
        const auto [lo, hi] = stats::min_max({3.0, 1.0, 4.0, 1.0, 5.0});
        check_close(lo, 1.0, "min_max lo");
        check_close(hi, 5.0, "min_max hi");
    }
    check_throws_empty("mean throws", [] { (void)stats::mean({}); });
    check_throws_empty("median throws", [] { (void)stats::median({}); });
    check_throws_empty("stddev throws", [] { (void)stats::stddev({}); });
    check_throws_empty("min_max throws", [] { (void)stats::min_max({}); });

    if (g_failed == 0) std::printf("all tests pass\n");
    return g_failed == 0 ? 0 : 1;
}
