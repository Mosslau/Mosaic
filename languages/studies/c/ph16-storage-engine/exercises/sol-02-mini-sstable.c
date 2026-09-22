/* sol-02-mini-sstable.c —— 参考实现: Mini SSTable writer / reader
 *
 * 题目要点:
 *   - 布局: [entry: klen u32 / type u8 / vlen u32 / key / value]*（升序）
 *           [稀疏索引: 每 4 条 1 项 (key, offset)] [footer 16B: idx_off/idx_cnt/magic]
 *   - writer 输入必须已升序（MemTable flush 天然满足）; 文件写后只读
 *   - reader: footer → 索引 → 二分定位 → 块内顺扫至多 4 条; tombstone → 不存在
 * 自测断言: 命中、覆盖语义（后写的 SSTable 优先属 LSM 层职责, 本题不管）、
 *           tombstone、范围外 key、越界即停。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：mkdir -p /tmp/ph16c-sol && cc -Wall -Wextra -std=c11 sol-02-mini-sstable.c -o /tmp/ph16c-sol/sol02
// 运行：/tmp/ph16c-sol/sol02（演示文件在 /tmp/ph16c-sol-data/, 退出码 0）
// 验证状态：已验证（零警告; 全部断言 PASS）
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

#define SST_MAGIC 0x53535431u /* "SST1" */
#define IDX_EVERY 4
#define FTR 16u

enum { T_PUT = 1, T_DEL = 2 };

static int g_pass = 0, g_fail = 0;
#define CHECK(cond, name) do { \
    if (cond) { g_pass++; printf("PASS: %s\n", name); } \
    else { g_fail++; printf("FAIL: %s\n", name); } \
} while (0)

static void put32(uint8_t *d, uint32_t v) {
    d[0] = (uint8_t)(v >> 24); d[1] = (uint8_t)(v >> 16);
    d[2] = (uint8_t)(v >> 8); d[3] = (uint8_t)v;
}
static void put64(uint8_t *d, uint64_t v) {
    for (int i = 0; i < 8; i++) d[i] = (uint8_t)(v >> (56 - 8 * i));
}
static uint32_t get32(const uint8_t *s) {
    return ((uint32_t)s[0] << 24) | ((uint32_t)s[1] << 16) |
           ((uint32_t)s[2] << 8) | (uint32_t)s[3];
}
static uint64_t get64(const uint8_t *s) {
    uint64_t v = 0;
    for (int i = 0; i < 8; i++) v = (v << 8) | s[i];
    return v;
}

typedef struct { const char *key, *val; uint8_t type; } kv_t;

static int sst_write(const char *path, const kv_t *kvs, size_t n) {
    FILE *f = fopen(path, "wb");
    if (!f) return -1;
    char ik[128][32];
    uint64_t io[128];
    size_t ic = 0;
    for (size_t i = 0; i < n; i++) {
        if (i % IDX_EVERY == 0 && ic < 128) {
            snprintf(ik[ic], 32, "%s", kvs[i].key);
            io[ic] = (uint64_t)ftell(f);
            ic++;
        }
        uint8_t hdr[9];
        uint32_t klen = (uint32_t)strlen(kvs[i].key), vlen = (uint32_t)strlen(kvs[i].val);
        put32(hdr, klen); hdr[4] = kvs[i].type; put32(hdr + 5, vlen);
        fwrite(hdr, 1, 9, f);
        fwrite(kvs[i].key, 1, klen, f);
        fwrite(kvs[i].val, 1, vlen, f);
    }
    uint64_t idx_off = (uint64_t)ftell(f);
    for (size_t i = 0; i < ic; i++) {
        uint8_t buf[4 + 32 + 8];
        uint32_t klen = (uint32_t)strlen(ik[i]);
        put32(buf, klen);
        memcpy(buf + 4, ik[i], klen);
        put64(buf + 4 + klen, io[i]);
        fwrite(buf, 1, 4 + klen + 8, f);
    }
    uint8_t ftr[FTR];
    put64(ftr, idx_off);
    put32(ftr + 8, (uint32_t)ic);
    put32(ftr + 12, SST_MAGIC);
    fwrite(ftr, 1, FTR, f);
    fclose(f);
    return 0;
}

/* 0 命中 / 1 不存在(含 tombstone) / -1 错误; 顺带输出实际扫过的数据条数 */
static int sst_get(const char *path, const char *target, char *out, size_t cap,
                   int *scanned) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    *scanned = 0;
    fseek(f, -(long)FTR, SEEK_END);
    uint8_t ftr[FTR];
    if (fread(ftr, 1, FTR, f) != FTR || get32(ftr + 12) != SST_MAGIC) {
        fclose(f); return -1;
    }
    uint64_t idx_off = get64(ftr);
    uint32_t ic = get32(ftr + 8);
    fseek(f, (long)idx_off, SEEK_SET);
    char ik[128][32];
    uint64_t io[128];
    for (uint32_t i = 0; i < ic && i < 128; i++) {
        uint8_t lb[4];
        if (fread(lb, 1, 4, f) != 4) { fclose(f); return -1; }
        uint32_t klen = get32(lb);
        if (klen >= 32 || fread(ik[i], 1, klen, f) != klen) { fclose(f); return -1; }
        ik[i][klen] = '\0';
        uint8_t ob[8];
        if (fread(ob, 1, 8, f) != 8) { fclose(f); return -1; }
        io[i] = get64(ob);
    }
    long lo = -1;
    uint32_t hi = ic;
    while ((uint32_t)(lo + 1) < hi) { /* 最后一个 key <= target 的索引项 */
        uint32_t mid = (uint32_t)(lo + 1) + (hi - (uint32_t)(lo + 1)) / 2;
        if (strcmp(ik[mid], target) <= 0) lo = (long)mid; else hi = mid;
    }
    if (lo < 0) { fclose(f); return 1; }
    fseek(f, (long)io[lo], SEEK_SET);
    for (int i = 0; i < IDX_EVERY; i++) {
        uint8_t hdr[9];
        if (fread(hdr, 1, 9, f) != 9) break;
        uint32_t klen = get32(hdr), vlen = get32(hdr + 5);
        uint8_t type = hdr[4];
        char key[32];
        if (klen >= 32 || fread(key, 1, klen, f) != klen) break;
        key[klen] = '\0';
        (*scanned)++;
        int cmp = strcmp(key, target);
        if (cmp == 0) {
            if (type == T_DEL) { fclose(f); return 1; }
            uint32_t take = vlen < cap - 1 ? vlen : (uint32_t)cap - 1;
            if (fread(out, 1, take, f) != take) { fclose(f); return -1; }
            out[take] = '\0';
            fclose(f);
            return 0;
        }
        if (cmp > 0) break;
        fseek(f, (long)vlen, SEEK_CUR);
    }
    fclose(f);
    return 1;
}

int main(void) {
    printf("=== sol-02: Mini SSTable writer / reader ===\n");
    mkdir("/tmp/ph16c-sol-data", 0755);
    const char *path = "/tmp/ph16c-sol-data/sol02.sst";
    const kv_t kvs[] = {
        {"a01", "v1", T_PUT}, {"a02", "v2", T_PUT}, {"a03", "v3", T_PUT},
        {"a04", "",   T_DEL}, /* tombstone */
        {"a05", "v5", T_PUT}, {"a06", "v6", T_PUT}, {"a07", "v7", T_PUT},
        {"a08", "v8", T_PUT}, {"a09", "v9", T_PUT},
    };
    CHECK(sst_write(path, kvs, sizeof kvs / sizeof kvs[0]) == 0, "写入 9 条成功");

    char val[32];
    int scanned = 0;
    CHECK(sst_get(path, "a05", val, sizeof val, &scanned) == 0 && strcmp(val, "v5") == 0,
          "get(a05) = v5");
    printf("    （块内顺扫 %d 条命中）\n", scanned);
    CHECK(sst_get(path, "a04", val, sizeof val, &scanned) == 1, "get(a04) tombstone → 不存在");
    CHECK(sst_get(path, "a00", val, sizeof val, &scanned) == 1, "get(a00) 小于所有 key → 不存在");
    CHECK(sst_get(path, "zzz", val, sizeof val, &scanned) == 1, "get(zzz) 大于所有 key → 不存在");
    CHECK(sst_get(path, "a01", val, sizeof val, &scanned) == 0 && scanned == 1,
          "get(a01) 索引直达, 只扫 1 条");

    remove(path);
    printf("sol-02: %d PASS, %d FAIL, 退出码 %d\n", g_pass, g_fail, g_fail ? 1 : 0);
    return g_fail ? 1 : 0;
}
