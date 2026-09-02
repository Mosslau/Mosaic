/* ex05-bloom-filter.c —— Bloom Filter：位数组 + k 个哈希（双哈希法）
 *
 * Bloom Filter 回答一个问题："这个 key 肯定不在 / 可能在集合里"。
 * SSTable 前面挂一个 Bloom Filter, 点查不存在的 key 时不用读数据块——
 * 用一点内存换掉大量无效磁盘 IO（主文档 3.5）。
 *
 * 实现要点：
 *   - m 位位数组, k 个哈希函数; 插入置 k 位, 查询查 k 位
 *   - 双哈希法: h_i(x) = h1(x) + i*h2(x), 两个真哈希模拟 k 个（Kirsch-Mitzenmacher）
 *   - 理论误判率 p = (1 - e^(-kn/m))^k; 本例实测对比理论值
 *   - 只能插不能删（删一个位会误伤其他 key）——LSM 里随 SSTable 重建, 无需删
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：mkdir -p /tmp/ph16c-ex && cc -Wall -Wextra -std=c11 ex05-bloom-filter.c -o /tmp/ph16c-ex/ex05
// 运行：/tmp/ph16c-ex/ex05（无外部产物, 退出码 0）
// 验证状态：已验证（零警告; 误判率为实测, 键序列确定故每次运行结果相同, 见 README）
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    uint8_t *bits;   /* 位数组: m 位, 按字节存放 */
    size_t m;        /* 位数 */
    uint32_t k;      /* 哈希函数个数 */
} bloom_t;

/* FNV-1a 64 位: 简单快速的字符串哈希（教学够用, 非加密级） */
static uint64_t fnv1a(const char *s, uint64_t seed) {
    uint64_t h = 1469598103934665603ULL ^ (seed * 1099511628211ULL);
    for (; *s; s++) {
        h ^= (uint8_t)*s;
        h *= 1099511628211ULL;
    }
    return h;
}

static void bloom_add(bloom_t *b, const char *key) {
    uint64_t h1 = fnv1a(key, 1);
    uint64_t h2 = fnv1a(key, 2);
    for (uint32_t i = 0; i < b->k; i++) {
        uint64_t h = h1 + (uint64_t)i * h2; /* 双哈希模拟第 i 个哈希 */
        size_t bit = (size_t)(h % b->m);
        b->bits[bit / 8] |= (uint8_t)(1u << (bit % 8));
    }
}

static int bloom_maybe(const bloom_t *b, const char *key) {
    uint64_t h1 = fnv1a(key, 1);
    uint64_t h2 = fnv1a(key, 2);
    for (uint32_t i = 0; i < b->k; i++) {
        uint64_t h = h1 + (uint64_t)i * h2;
        size_t bit = (size_t)(h % b->m);
        if (!(b->bits[bit / 8] & (uint8_t)(1u << (bit % 8)))) return 0;
    }
    return 1;
}

int main(void) {
    const size_t n = 10000;          /* 插入 1 万个 key */
    const uint32_t k = 7;            /* 7 个哈希 */
    const size_t m = n * 10;         /* 每 key 10 位 → 理论误判约 0.8% */
    bloom_t b;
    b.m = m;
    b.k = k;
    b.bits = calloc(m / 8 + 1, 1);
    if (!b.bits) return 1;

    printf("=== Bloom Filter ===\n");
    printf("配置: %zu 位（每 key %zu 位）, k=%u 个哈希, 插入 n=%zu 个 key\n",
           m, m / n, k, n);

    for (size_t i = 0; i < n; i++) {
        char key[32];
        snprintf(key, sizeof key, "key%06zu", i);
        bloom_add(&b, key);
    }

    /* 1. 已插入的 key 全部命中（Bloom Filter 无假阴性） */
    size_t miss = 0;
    for (size_t i = 0; i < n; i++) {
        char key[32];
        snprintf(key, sizeof key, "key%06zu", i);
        if (!bloom_maybe(&b, key)) miss++;
    }
    printf("[1] 已插入 %zu 个 key 回查: 漏报 %zu 个（必为 0, 无假阴性）\n", n, miss);

    /* 2. 未插入的 key 测误判（假阳性） */
    const size_t probe = 100000;
    size_t fp = 0;
    for (size_t i = 0; i < probe; i++) {
        char key[32];
        snprintf(key, sizeof key, "nope%06zu", i);
        if (bloom_maybe(&b, key)) fp++;
    }
    double measured = (double)fp / (double)probe * 100.0;
    double theory = pow(1.0 - exp(-(double)k * (double)n / (double)m), (double)k) * 100.0;
    printf("[2] 未插入 %zu 个 key 探测: 误判 %zu 次 = %.2f%%（理论 %.2f%%）\n",
           probe, fp, measured, theory);

    /* 3. 不同 k 的对比（m/n 不变） */
    printf("[3] k 对误判率的影响（同 m, 同 n, 理论值）:\n");
    for (uint32_t kk = 1; kk <= 10; kk += 3) {
        double t = pow(1.0 - exp(-(double)kk * (double)n / (double)m), (double)kk) * 100.0;
        printf("    k=%2u → 理论误判 %.2f%%\n", kk, t);
    }

    free(b.bits);
    return 0;
}
