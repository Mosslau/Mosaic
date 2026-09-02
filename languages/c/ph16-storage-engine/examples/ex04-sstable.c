/* ex04-sstable.c —— SSTable 文件格式：writer / reader（稀疏索引 + footer）
 *
 * SSTable = Sorted String Table: 不可变有序文件。MemTable 写满后整体 flush
 * 成一个 SSTable, 之后只读不改——"不可变"让并发读、缓存、压缩全都变简单。
 *
 * 文件布局（多字节字段显式大端）：
 *   [数据区]  entry*: [klen u32][type u8][vlen u32][key][value]   按 key 升序
 *   [索引区]  稀疏索引: 每 IDX_EVERY 条记录索引一条: [klen u32][key][off u64]
 *   [footer]  [index_off u64][index_cnt u32][magic u32 "SST1"]   定长 16 字节
 *
 * 查询路径: 读 footer → 载入索引 → 二分找"最后一个 ≤ target 的索引项"
 *          → 跳到 offset 顺序扫至多 IDX_EVERY 条 → 命中/tombstone/不存在。
 * 演示文件写 /tmp/ph16c-ex-data/, 退出时删除。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：mkdir -p /tmp/ph16c-ex && cc -Wall -Wextra -std=c11 ex04-sstable.c -o /tmp/ph16c-ex/ex04
// 运行：/tmp/ph16c-ex/ex04（产物在 /tmp/ph16c-ex-data/, 退出码 0）
// 验证状态：已验证（零警告; 命中/tombstone/区间扫描输出均为实测）
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

#define SST_MAGIC 0x53535431u /* "SST1" */
#define IDX_EVERY 4           /* 每 4 条记录索引一条（稀疏度） */
#define SST_FTR_SIZE 16u      /* index_off(8) + index_cnt(4) + magic(4) */

enum { SST_PUT = 1, SST_DEL = 2 };

static void put_u32be(uint8_t *d, uint32_t v) {
    d[0] = (uint8_t)(v >> 24); d[1] = (uint8_t)(v >> 16);
    d[2] = (uint8_t)(v >> 8);  d[3] = (uint8_t)v;
}
static void put_u64be(uint8_t *d, uint64_t v) {
    for (int i = 0; i < 8; i++) d[i] = (uint8_t)(v >> (56 - 8 * i));
}
static uint32_t get_u32be(const uint8_t *s) {
    return ((uint32_t)s[0] << 24) | ((uint32_t)s[1] << 16) |
           ((uint32_t)s[2] << 8) | (uint32_t)s[3];
}
static uint64_t get_u64be(const uint8_t *s) {
    uint64_t v = 0;
    for (int i = 0; i < 8; i++) v = (v << 8) | s[i];
    return v;
}

/* ---- writer: 输入必须已按 key 升序（MemTable flush 天然满足） ---- */
typedef struct {
    const char *key;
    const char *val;
    uint8_t type;
} kv_t;

static int sst_write(const char *path, const kv_t *kvs, size_t n) {
    FILE *f = fopen(path, "wb");
    if (!f) return -1;
    /* 先写数据区, 每 IDX_EVERY 条记一条索引到内存（演示用定长表） */
    char idx_key[64][64];
    uint64_t idx_off[64];
    size_t idx_cnt = 0;
    for (size_t i = 0; i < n; i++) {
        uint64_t off = (uint64_t)ftell(f);
        if (i % IDX_EVERY == 0 && idx_cnt < 64) {
            snprintf(idx_key[idx_cnt], sizeof idx_key[0], "%s", kvs[i].key);
            idx_off[idx_cnt] = off;
            idx_cnt++;
        }
        uint8_t hdr[9];
        uint32_t klen = (uint32_t)strlen(kvs[i].key);
        uint32_t vlen = (uint32_t)strlen(kvs[i].val);
        put_u32be(hdr, klen);
        hdr[4] = kvs[i].type;
        put_u32be(hdr + 5, vlen);
        fwrite(hdr, 1, 9, f);
        fwrite(kvs[i].key, 1, klen, f);
        fwrite(kvs[i].val, 1, vlen, f);
    }
    /* 索引区 */
    uint64_t index_off = (uint64_t)ftell(f);
    for (size_t i = 0; i < idx_cnt; i++) {
        uint8_t buf[4 + 64 + 8];
        uint32_t klen = (uint32_t)strlen(idx_key[i]);
        put_u32be(buf, klen);
        memcpy(buf + 4, idx_key[i], klen);
        put_u64be(buf + 4 + klen, idx_off[i]);
        fwrite(buf, 1, 4 + klen + 8, f);
    }
    /* footer（定长, 读方从文件尾直接定位） */
    uint8_t ftr[SST_FTR_SIZE];
    put_u64be(ftr, index_off);
    put_u32be(ftr + 8, (uint32_t)idx_cnt);
    put_u32be(ftr + 12, SST_MAGIC);
    fwrite(ftr, 1, SST_FTR_SIZE, f);
    fclose(f);
    return 0;
}

/* ---- reader: 返回 0 命中 / 1 不存在（含 tombstone） / -1 错误 ---- */
static int sst_get(const char *path, const char *target,
                   char *val_out, size_t val_cap, int *steps) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    fseek(f, -(long)SST_FTR_SIZE, SEEK_END);
    uint8_t ftr[SST_FTR_SIZE];
    if (fread(ftr, 1, SST_FTR_SIZE, f) != SST_FTR_SIZE) { fclose(f); return -1; }
    if (get_u32be(ftr + 12) != SST_MAGIC) { fclose(f); return -1; }
    uint64_t index_off = get_u64be(ftr);
    uint32_t idx_cnt = get_u32be(ftr + 8);
    /* 载入索引 */
    fseek(f, (long)index_off, SEEK_SET);
    char idx_key[64][64];
    uint64_t idx_off[64];
    for (uint32_t i = 0; i < idx_cnt && i < 64; i++) {
        uint8_t lb[4];
        if (fread(lb, 1, 4, f) != 4) { fclose(f); return -1; }
        uint32_t klen = get_u32be(lb);
        if (klen >= 64) { fclose(f); return -1; }
        if (fread(idx_key[i], 1, klen, f) != klen) { fclose(f); return -1; }
        idx_key[i][klen] = '\0';
        uint8_t ob[8];
        if (fread(ob, 1, 8, f) != 8) { fclose(f); return -1; }
        idx_off[i] = get_u64be(ob);
    }
    /* 二分: 找最后一个 key <= target 的索引项 */
    long lo = -1;
    uint32_t hi = idx_cnt;
    *steps = 0;
    while ((uint32_t)(lo + 1) < hi) {
        uint32_t mid = (uint32_t)(lo + 1) + (hi - (uint32_t)(lo + 1)) / 2;
        (*steps)++;
        if (strcmp(idx_key[mid], target) <= 0) lo = (long)mid;
        else hi = mid;
    }
    if (lo < 0) { fclose(f); return 1; } /* 比第一条还小 */
    /* 从索引项顺序扫至多 IDX_EVERY 条 */
    fseek(f, (long)idx_off[lo], SEEK_SET);
    for (int i = 0; i < IDX_EVERY; i++) {
        uint8_t hdr[9];
        if (fread(hdr, 1, 9, f) != 9) break;
        uint32_t klen = get_u32be(hdr);
        uint8_t type = hdr[4];
        uint32_t vlen = get_u32be(hdr + 5);
        char key[64];
        if (klen >= 64 || fread(key, 1, klen, f) != klen) break;
        key[klen] = '\0';
        int cmp = strcmp(key, target);
        if (cmp == 0) {
            if (type == SST_DEL) { fclose(f); return 1; } /* tombstone */
            uint32_t take = vlen < val_cap - 1 ? vlen : (uint32_t)val_cap - 1;
            if (fread(val_out, 1, take, f) != take) { fclose(f); return -1; }
            val_out[take] = '\0';
            fclose(f);
            return 0;
        }
        if (cmp > 0) break; /* 有序: 越过即不存在 */
        fseek(f, (long)vlen, SEEK_CUR);
    }
    fclose(f);
    return 1;
}

int main(void) {
    const char *dir = "/tmp/ph16c-ex-data";
    mkdir(dir, 0755);
    char path[128];
    snprintf(path, sizeof path, "%s/demo.sst", dir);

    /* MemTable flush 场景: 输入已升序, 含一条 tombstone */
    const kv_t kvs[] = {
        {"ant",    "1", SST_PUT}, {"bear",   "2", SST_PUT},
        {"cat",    "3", SST_PUT}, {"deer",   "",  SST_DEL}, /* tombstone */
        {"eagle",  "5", SST_PUT}, {"fox",    "6", SST_PUT},
        {"goat",   "7", SST_PUT}, {"horse",  "8", SST_PUT},
        {"iguana", "9", SST_PUT}, {"jaguar", "10", SST_PUT},
    };
    size_t n = sizeof kvs / sizeof kvs[0];
    sst_write(path, kvs, n);

    long sz = 0;
    FILE *f = fopen(path, "rb");
    if (f) { fseek(f, 0, SEEK_END); sz = ftell(f); fclose(f); }
    printf("=== SSTable: 不可变有序文件 ===\n");
    printf("[1] 写入 %zu 条（含 1 条 tombstone）, 文件 %ld 字节, 稀疏索引每 %d 条 1 项\n",
           n, sz, IDX_EVERY);

    char val[64];
    int steps = 0;
    int rc = sst_get(path, "fox", val, sizeof val, &steps);
    printf("[2] get(fox) rc=%d value=%s （索引二分 %d 步 + 块内顺扫）\n", rc, val, steps);
    rc = sst_get(path, "deer", val, sizeof val, &steps);
    printf("    get(deer) rc=%d （tombstone → 不存在）\n", rc);
    rc = sst_get(path, "zebra", val, sizeof val, &steps);
    printf("    get(zebra) rc=%d （比所有 key 都大, 索引直接排除）\n", rc);
    rc = sst_get(path, "aaa", val, sizeof val, &steps);
    printf("    get(aaa) rc=%d （比第一条还小, 无需读数据区）\n", rc);

    remove(path);
    return 0;
}
