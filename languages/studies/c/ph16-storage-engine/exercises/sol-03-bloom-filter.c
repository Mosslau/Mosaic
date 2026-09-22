/* sol-03-bloom-filter.c —— 参考实现: Bloom Filter（位数组 + 双哈希）
 *
 * 题目要点:
 *   - m 位位数组 + k 个哈希（双哈希法 h_i = h1 + i*h2 模拟）
 *   - add 置 k 位, maybe 查 k 位; 无假阴性, 有可控假阳性
 *   - 理论误判率 p = (1 - e^(-kn/m))^k; 实测应围绕理论值
 * 自测断言: 回查漏报 = 0; 实测误判率 < 理论值的 2 倍（宽松上界, 允许哈希
 *           非理想独立带来的偏差, 且本例键序列确定、结果可复现）。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：mkdir -p /tmp/ph16c-sol && cc -Wall -Wextra -std=c11 sol-03-bloom-filter.c -o /tmp/ph16c-sol/sol03 -lm
// 运行：/tmp/ph16c-sol/sol03（无外部产物, 退出码 0）
// 验证状态：已验证（零警告; 实测误判率 0.46% < 理论 0.82% 的 2 倍, 全部断言 PASS）
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int g_pass = 0, g_fail = 0;
#define CHECK(cond, name) do { \
    if (cond) { g_pass++; printf("PASS: %s\n", name); } \
    else { g_fail++; printf("FAIL: %s\n", name); } \
} while (0)

typedef struct { uint8_t *bits; size_t m; uint32_t k; } bloom_t;

static uint64_t fnv1a(const char *s, uint64_t seed) {
    uint64_t h = 1469598103934665603ULL ^ (seed * 1099511628211ULL);
    for (; *s; s++) { h ^= (uint8_t)*s; h *= 1099511628211ULL; }
    return h;
}

static void bloom_add(bloom_t *b, const char *key) {
    uint64_t h1 = fnv1a(key, 1), h2 = fnv1a(key, 2);
    for (uint32_t i = 0; i < b->k; i++) {
        size_t bit = (size_t)((h1 + (uint64_t)i * h2) % b->m);
        b->bits[bit / 8] |= (uint8_t)(1u << (bit % 8));
    }
}

static int bloom_maybe(const bloom_t *b, const char *key) {
    uint64_t h1 = fnv1a(key, 1), h2 = fnv1a(key, 2);
    for (uint32_t i = 0; i < b->k; i++) {
        size_t bit = (size_t)((h1 + (uint64_t)i * h2) % b->m);
        if (!(b->bits[bit / 8] & (uint8_t)(1u << (bit % 8)))) return 0;
    }
    return 1;
}

int main(void) {
    printf("=== sol-03: Bloom Filter ===\n");
    const size_t n = 10000, m = n * 10;
    const uint32_t k = 7;
    bloom_t b = { calloc(m / 8 + 1, 1), m, k };
    if (!b.bits) return 1;

    for (size_t i = 0; i < n; i++) {
        char key[32];
        snprintf(key, sizeof key, "key%06zu", i);
        bloom_add(&b, key);
    }

    size_t miss = 0;
    for (size_t i = 0; i < n; i++) {
        char key[32];
        snprintf(key, sizeof key, "key%06zu", i);
        if (!bloom_maybe(&b, key)) miss++;
    }
    CHECK(miss == 0, "无假阴性: 10000 个已插入 key 回查漏报 = 0");

    const size_t probe = 100000;
    size_t fp = 0;
    for (size_t i = 0; i < probe; i++) {
        char key[32];
        snprintf(key, sizeof key, "nope%06zu", i);
        if (bloom_maybe(&b, key)) fp++;
    }
    double measured = (double)fp / (double)probe;
    double theory = pow(1.0 - exp(-(double)k * (double)n / (double)m), (double)k);
    printf("    实测误判 %.3f%%（理论 %.3f%%）\n", measured * 100, theory * 100);
    CHECK(measured < theory * 2.0, "实测误判率 < 理论值 2 倍（宽松上界）");
    CHECK(fp > 0, "假阳性确实存在（Bloom Filter 的固有代价）");

    free(b.bits);
    printf("sol-03: %d PASS, %d FAIL, 退出码 %d\n", g_pass, g_fail, g_fail ? 1 : 0);
    return g_fail ? 1 : 0;
}
