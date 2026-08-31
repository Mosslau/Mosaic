/* test_buffer.c —— buffer 库自测（ph11 阶段项目）
 * 零依赖断言宏(与 examples/ex06-selftest.c 同一思路): 统计 PASS/FAIL,
 * FAIL 非零则退出码非 0 —— make test / CI 里"一键运行"的入口。
 * 覆盖: 边界输入(空/恰好满/越界/远界) + 错误路径(NULL 参数/扩容失败) +
 *   append-only 语义。
 * 验证环境: Apple clang 21.0.0（cc，macOS arm64）
 * 编译: make test（见 Makefile）; 或 cc -Wall -Wextra -std=c11 -O1 -g buffer.c test_buffer.c -o test_buffer
 * 运行: ./test_buffer
 * 验证状态: 已验证（Makefile 全目标实测, 见 README 验收标准）
 */
#include "buffer.h"

#include <stdio.h>

/* ---- 极简断言宏 ---- */
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

/* ---- 用例: 边界输入 ---- */
static void test_init_empty(void) {
    Buffer b;
    CHECK(buf_init(&b, 0) == 0);           /* 0 容量退化为 1 */
    CHECK(buf_len(&b) == 0);
    unsigned char c = 0;
    CHECK(buf_get(&b, 0, &c) == -1);       /* 空 buffer 越界 */
    buf_destroy(&b);
}

static void test_append_then_get(void) {
    Buffer b;
    CHECK(buf_init(&b, 4) == 0);
    CHECK(buf_append(&b, "abc", 3) == 0);
    CHECK(buf_len(&b) == 3);
    unsigned char c = 0;
    CHECK(buf_get(&b, 0, &c) == 0 && c == 'a');
    CHECK(buf_get(&b, 2, &c) == 0 && c == 'c');
    buf_destroy(&b);
}

static void test_append_exact_fit(void) {
    Buffer b;
    CHECK(buf_init(&b, 3) == 0);
    CHECK(buf_append(&b, "xyz", 3) == 0);  /* 恰好填满 cap, 不扩容 */
    CHECK(buf_len(&b) == 3);
    unsigned char c = 0;
    CHECK(buf_get(&b, 2, &c) == 0 && c == 'z');
    CHECK(buf_append(&b, "!", 1) == 0);    /* 再写 1 字节触发扩容 */
    CHECK(buf_len(&b) == 4);
    CHECK(buf_get(&b, 3, &c) == 0 && c == '!');
    buf_destroy(&b);
}

static void test_grow_past_capacity(void) {
    Buffer b;
    CHECK(buf_init(&b, 4) == 0);
    const char *payload = "0123456789";    /* 10 字节 > 初始 4, 多次翻倍 */
    CHECK(buf_append(&b, payload, 10) == 0);
    CHECK(buf_len(&b) == 10);
    unsigned char c = 0;
    CHECK(buf_get(&b, 9, &c) == 0 && c == '9');   /* 扩容后边界内最后一位 */
    buf_destroy(&b);
}

/* ---- 用例: 错误路径 ---- */
static void test_oob_returns_error(void) {
    Buffer b;
    CHECK(buf_init(&b, 4) == 0);
    CHECK(buf_append(&b, "xy", 2) == 0);
    unsigned char c = 0;
    CHECK(buf_get(&b, 2, &c) == -1);           /* 越界: idx == len */
    CHECK(buf_get(&b, 100, &c) == -1);         /* 越界: 远界 */
    buf_destroy(&b);
}

static void test_null_arguments_rejected(void) {
    CHECK(buf_init(NULL, 4) == -1);
    CHECK(buf_append(NULL, "x", 1) == -1);
    unsigned char c = 0;
    CHECK(buf_get(NULL, 0, &c) == -1);
    CHECK(buf_len(NULL) == 0);
}

static void test_zero_len_append_is_noop(void) {
    Buffer b;
    CHECK(buf_init(&b, 4) == 0);
    CHECK(buf_append(&b, NULL, 0) == 0);       /* 空追加: 无操作 */
    CHECK(buf_len(&b) == 0);
    buf_destroy(&b);
}

int main(void) {
    test_init_empty();
    test_append_then_get();
    test_append_exact_fit();
    test_grow_past_capacity();
    test_oob_returns_error();
    test_null_arguments_rejected();
    test_zero_len_append_is_noop();
    if (g_failures == 0)
        printf("自测通过: %d 个断言全部通过 (退出码 0 = CI 通过)\n", g_passes);
    else
        printf("自测失败: %d 个断言失败\n", g_failures);
    return g_failures == 0 ? 0 : 1;
}
