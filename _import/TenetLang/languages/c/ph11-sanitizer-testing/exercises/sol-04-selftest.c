/* sol-04-selftest.c —— 参考实现: 自测模式单元测试（断言宏 + 边界/错误路径）
 * 练习要点: 给 check_len / is_leap 写自测, 故意留一个 off-by-one 让测试
 *   失败、定位、修复——测试的价值在于能抓住回归。
 * 实测: 全部用例通过时输出 11 个 [PASS] + "自测通过: 11 个断言全部通过",
 *   退出码 0（Apple clang 21.0.0 实测）。
 * 反证: 把 is_leap 的 `y % 400 == 0` 改成 `y % 400 != 0` 后重编译,
 *   5 个闰年相关用例应 [FAIL]（实测 5 个, 退出码 1）——"故意引入 bug"验证法。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 -O1 -g sol-04-selftest.c -o sol04
// 运行：./sol04（11 个断言全过, 退出码 0; CI 用法: ./sol04 && echo OK）
// 验证状态：已验证（-Wall -Wextra 零警告; 加 -fsanitize=address,undefined 运行零报告）
#include <stddef.h>
#include <stdio.h>

/* ---- 极简断言宏（与 examples/ex06-selftest.c 同一思路） ---- */
static int g_passes = 0;
static int g_failures = 0;
#define CHECK(cond) do {                                                   \
    if (cond) {                                                            \
        g_passes++;                                                        \
        printf("[PASS] %s\n", #cond);                                      \
    } else {                                                               \
        g_failures++;                                                      \
        printf("[FAIL] %s  (%s:%d)\n", #cond, __FILE__, __LINE__);         \
    }                                                                      \
} while (0)

/* ---- 被测函数 1: 闰年判断（4 个分支, 覆盖边界年份） ---- */
static int is_leap(int y) {
    if (y % 400 == 0) return 1;      /* 分支 1: 400 的倍数 */
    if (y % 100 == 0) return 0;      /* 分支 2: 100 的倍数非 400 */
    return y % 4 == 0;               /* 分支 3/4: 4 的倍数与否 */
}

/* ---- 被测函数 2: record 长度校验（衔接 ph12 的边界逻辑） ---- */
static int check_len(size_t len, size_t max) {
    if (len > max) return -1;        /* 错误路径: 超长 */
    return 0;
}

/* ---- 测试用例: 边界输入 + 错误路径 ---- */
static void test_is_leap(void) {
    CHECK(is_leap(2000) == 1);       /* %400 分支 */
    CHECK(is_leap(1900) == 0);       /* %100 分支 */
    CHECK(is_leap(2024) == 1);       /* %4 分支 */
    CHECK(is_leap(2023) == 0);       /* 非闰年分支 */
}

static void test_check_len(void) {
    CHECK(check_len(4, 16) == 0);    /* 正常长度 */
    CHECK(check_len(16, 16) == 0);   /* 等于上限: 边界内 */
    CHECK(check_len(17, 16) == -1);  /* 超上限: 错误路径 */
    CHECK(check_len(0, 16) == 0);    /* 空 record */
}

static void test_error_paths(void) {
    /* 极端长度: SIZE_MAX 一定超限(若 max 是普通上限) */
    CHECK(check_len((size_t)-1, 16) == -1);
    CHECK(is_leap(1600) == 1);       /* %400 分支的另一边界 */
    CHECK(is_leap(1700) == 0);       /* %100 分支的另一边界 */
}

int main(void) {
    test_is_leap();
    test_check_len();
    test_error_paths();
    if (g_failures == 0)
        printf("自测通过: %d 个断言全部通过 (退出码 0 = CI 通过)\n", g_passes);
    else
        printf("自测失败: %d 个断言失败\n", g_failures);
    return g_failures == 0 ? 0 : 1;
}
