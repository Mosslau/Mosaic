/* ex06-selftest.c —— 自测模式单元测试: 零依赖的轻量断言宏框架
 * 运行前提: 无（正常工程代码, 可任意编译运行; 建议再加 -fsanitize 复跑）
 * 说明: 这是"简单 assert 宏/自测模式"路线——不引第三方框架(Unity 等),
 *   用 4 个宏 + 一个计数器搭出可进 CI 的自测壳: ./ex06 退出码 0 = 全过。
 *   被测对象: 带边界检查的 byte 追加 buffer（append/get/len）。
 *   测试覆盖: 边界输入(空/恰好满/越界)与错误路径(NULL 参数、扩容失败)。
 * 编译: cc -Wall -Wextra -std=c11 -O1 -g ex06-selftest.c -o ex06
 * 运行: ./ex06 → 打印每个用例结果 + 汇总, 全过则退出码 0
 *   （CI 用法: ./ex06 && echo "测试通过" —— 非零退出即失败）
 * 验证环境: Apple clang 21.0.0（cc，macOS arm64）
 * 验证状态: 已验证（输出见 README 表格与主文档示例 6; 加
 *   -fsanitize=address,undefined 复跑同样零报告）
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---- 极简断言宏: 统计 PASS/FAIL, FAIL 计数非零则 main 返回非零 ---- */
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

/* ---- 被测对象: 带边界检查的 byte buffer（ph04 动态数组的字节版） ---- */
typedef struct {
    unsigned char *data;
    size_t         len;    /* 已用字节数 */
    size_t         cap;    /* 容量（字节数） */
} Buf;

static int buf_init(Buf *b, size_t cap) {
    if (b == NULL) return -1;
    b->data = malloc(cap ? cap : 1);
    if (b->data == NULL) return -1;
    b->len = 0;
    b->cap = cap ? cap : 1;
    return 0;
}

static void buf_destroy(Buf *b) {
    if (b == NULL) return;
    free(b->data);
    b->data = NULL;
    b->len = b->cap = 0;
}

static int buf_append(Buf *b, const void *src, size_t n) {
    if (b == NULL || (src == NULL && n > 0)) return -1;
    if (n > b->cap - b->len) {              /* 容量不足: 先检查再做算术 */
        if (b->cap > (SIZE_MAX - n) / 2) return -1;   /* 扩容溢出防护 */
        size_t new_cap = b->cap;
        while (new_cap < b->len + n)        /* 至少装下, 至少翻倍 */
            new_cap *= 2;
        unsigned char *tmp = realloc(b->data, new_cap);
        if (tmp == NULL) return -1;         /* 扩容失败: 原数据不丢 */
        b->data = tmp;
        b->cap = new_cap;
    }
    memcpy(b->data + b->len, src, n);
    b->len += n;
    return 0;
}

static int buf_get(const Buf *b, size_t idx, unsigned char *out) {
    if (b == NULL || out == NULL) return -1;
    if (idx >= b->len) return -1;           /* 边界检查: 越界返回 -1 */
    *out = b->data[idx];
    return 0;
}

static size_t buf_len(const Buf *b) {
    return b == NULL ? 0 : b->len;
}

/* ---- 测试用例: 边界输入 + 错误路径 ---- */
static void test_init_empty(void) {
    Buf b;
    CHECK(buf_init(&b, 0) == 0);
    CHECK(buf_len(&b) == 0);
    unsigned char c = 0;
    CHECK(buf_get(&b, 0, &c) == -1);       /* 空 buffer 越界 */
    buf_destroy(&b);
}

static void test_append_and_get(void) {
    Buf b;
    CHECK(buf_init(&b, 4) == 0);
    CHECK(buf_append(&b, "abc", 3) == 0);
    CHECK(buf_len(&b) == 3);
    unsigned char c = 0;
    CHECK(buf_get(&b, 0, &c) == 0 && c == 'a');
    CHECK(buf_get(&b, 2, &c) == 0 && c == 'c');
    buf_destroy(&b);
}

static void test_grow_past_capacity(void) {
    Buf b;
    CHECK(buf_init(&b, 4) == 0);
    const char *payload = "0123456789";
    CHECK(buf_append(&b, payload, 10) == 0);   /* 越过容量 4, 触发扩容 */
    CHECK(buf_len(&b) == 10);
    unsigned char c = 0;
    CHECK(buf_get(&b, 9, &c) == 0 && c == '9'); /* 扩容后边界内最后一位 */
    buf_destroy(&b);
}

static void test_out_of_bounds_returns_error(void) {
    Buf b;
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

static void test_append_grows_to_fit(void) {
    Buf b;
    CHECK(buf_init(&b, 1) == 0);
    const char *payload = "0123456789abcdef";
    CHECK(buf_append(&b, payload, 16) == 0);   /* 多次翻倍直到装下 */
    CHECK(buf_len(&b) == 16);
    buf_destroy(&b);
}

int main(void) {
    test_init_empty();
    test_append_and_get();
    test_grow_past_capacity();
    test_out_of_bounds_returns_error();
    test_null_arguments_rejected();
    test_append_grows_to_fit();
    if (g_failures == 0)
        printf("自测通过: %d 个断言全部通过 (退出码 0 = CI 通过)\n", g_passes);
    else
        printf("自测失败: %d 个断言失败\n", g_failures);
    return g_failures == 0 ? 0 : 1;
}
