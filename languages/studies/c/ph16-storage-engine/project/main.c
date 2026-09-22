/* main.c —— lsmkv 命令行与自测套件
 *
 * 用法:
 *   lsmkv put <dir> <key> <val>   写入
 *   lsmkv get <dir> <key>         查询
 *   lsmkv del <dir> <key>         删除（tombstone）
 *   lsmkv flush <dir>             手动 flush
 *   lsmkv stats <dir>             诊断统计
 *   lsmkv test                    自测套件（退出码即结果, 数据在 /tmp/ph16c-proj-data）
 */
#include "lsm.h"
#include "wal.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int g_pass = 0, g_fail = 0;
#define CHECK(cond, name) do { \
    if (cond) { g_pass++; printf("PASS: %s\n", name); } \
    else { g_fail++; printf("FAIL: %s\n", name); } \
} while (0)

static unsigned long total_bloom_skips(const lsm_t *e) {
    unsigned long s = 0;
    for (int i = 0; i < e->sst_cnt; i++) s += e->ssts[i].bloom_skips;
    return s;
}

static int run_test(void) {
    printf("=== ph16 project: lsmkv 自测套件 ===\n");
    const char *dir = "/tmp/ph16c-proj-data/test";
    /* 清场 */
    char cmd[384];
    snprintf(cmd, sizeof cmd, "rm -rf %s", dir);
    if (system(cmd) != 0) return 1;

    char val[1024];
    lsm_t e;

    /* 场景 1: 基本 put/get（MemTable 命中） */
    CHECK(lsm_open(&e, dir) == 0, "open 成功");
    CHECK(lsm_put(&e, "name", "tenet") == 0, "put(name,tenet)");
    CHECK(lsm_get(&e, "name", val, sizeof val) == 0 && strcmp(val, "tenet") == 0,
          "get(name) = tenet");
    CHECK(lsm_get(&e, "nope", val, sizeof val) == 1, "get(nope) 不存在");

    /* 场景 2: 覆盖与删除 */
    CHECK(lsm_put(&e, "name", "lsmkv") == 0, "put(name,lsmkv) 覆盖");
    CHECK(lsm_get(&e, "name", val, sizeof val) == 0 && strcmp(val, "lsmkv") == 0,
          "覆盖后 get(name) = lsmkv");
    CHECK(lsm_del(&e, "name") == 0, "del(name)");
    CHECK(lsm_get(&e, "name", val, sizeof val) == 1, "删除后 get(name) 不存在");

    /* 场景 3: 关闭重开 → WAL replay 恢复 */
    CHECK(lsm_put(&e, "city", "hangzhou") == 0, "put(city,hangzhou)");
    lsm_close(&e);
    CHECK(lsm_open(&e, dir) == 0, "重开成功（WAL replay）");
    CHECK(lsm_get(&e, "city", val, sizeof val) == 0 && strcmp(val, "hangzhou") == 0,
          "重开后 get(city) = hangzhou（WAL 恢复）");
    CHECK(lsm_get(&e, "name", val, sizeof val) == 1, "重开后 name 仍是删除态（tombstone 也重放了）");

    /* 场景 4: 写满 4 KiB 触发自动 flush → SSTable 落盘 */
    char k[32], v[900];
    memset(v, 'x', sizeof v - 1);
    v[sizeof v - 1] = '\0';
    for (int i = 0; i < 10; i++) {
        snprintf(k, sizeof k, "bulk%02d", i);
        if (lsm_put(&e, k, v) != 0) { g_fail++; break; }
    }
    CHECK(e.flushes >= 1, "写满 4 KiB 自动 flush（flushes >= 1）");
    CHECK(e.sst_cnt >= 1, "SSTable 已生成");
    CHECK(access("/tmp/ph16c-proj-data/test/sst-000001.dat", F_OK) == 0,
          "sst-000001.dat 存在于磁盘");

    /* 场景 5: flush 后数据仍可读（SSTable 路径） */
    CHECK(lsm_get(&e, "bulk00", val, sizeof val) == 0 && strlen(val) == 899,
          "flush 后 get(bulk00) 从 SSTable 命中");
    CHECK(lsm_get(&e, "city", val, sizeof val) == 0, "flush 后旧数据 city 仍可读");

    /* 场景 6: 新数据覆盖 SSTable 里的旧值（新层赢） */
    CHECK(lsm_put(&e, "bulk00", "updated") == 0, "put(bulk00,updated) 覆盖 SSTable 里的值");
    CHECK(lsm_get(&e, "bulk00", val, sizeof val) == 0 && strcmp(val, "updated") == 0,
          "get(bulk00) = updated（MemTable 新值赢过 SSTable 旧值）");

    /* 场景 7: 删除住在 SSTable 里的 key（tombstone 遮挡） */
    CHECK(lsm_del(&e, "bulk01") == 0, "del(bulk01)（住在 SSTable）");
    CHECK(lsm_get(&e, "bulk01", val, sizeof val) == 1, "get(bulk01) 不存在（MemTable tombstone 遮挡）");

    /* 场景 8: 再 flush → tombstone 落到新 SSTable, 仍遮挡最旧的值 */
    CHECK(lsm_flush(&e) == 0, "手动 flush 成功");
    CHECK(lsm_get(&e, "bulk01", val, sizeof val) == 1, "二次 flush 后 bulk01 仍不存在（SSTable tombstone 遮挡）");
    CHECK(lsm_get(&e, "bulk00", val, sizeof val) == 0 && strcmp(val, "updated") == 0,
          "二次 flush 后 bulk00 = updated（新 SSTable 赢旧 SSTable）");

    /* 场景 9: Bloom Filter 省掉不存在 key 的数据区查询 */
    unsigned long before = total_bloom_skips(&e);
    for (int i = 0; i < 100; i++) {
        snprintf(k, sizeof k, "ghost%03d", i);
        lsm_get(&e, k, val, sizeof val);
    }
    CHECK(total_bloom_skips(&e) > before, "100 个不存在的 key 触发 bloom 拦截（bloom_skips 增长）");

    /* 场景 10: flush 后重开 → 纯 SSTable 恢复（WAL 已清空） */
    lsm_close(&e);
    CHECK(lsm_open(&e, dir) == 0, "flush 后重开成功");
    CHECK(lsm_get(&e, "bulk00", val, sizeof val) == 0 && strcmp(val, "updated") == 0,
          "重开后 bulk00 = updated（纯 SSTable 路径）");
    CHECK(lsm_get(&e, "bulk01", val, sizeof val) == 1, "重开后 bulk01 仍不存在");
    lsm_close(&e);

    printf("lsmkv: %d PASS, %d FAIL, 退出码 %d\n", g_pass, g_fail, g_fail ? 1 : 0);
    return g_fail ? 1 : 0;
}

static int usage(const char *prog) {
    fprintf(stderr,
            "用法:\n"
            "  %s put <dir> <key> <val>\n"
            "  %s get <dir> <key>\n"
            "  %s del <dir> <key>\n"
            "  %s flush <dir>\n"
            "  %s stats <dir>\n"
            "  %s test\n", prog, prog, prog, prog, prog, prog);
    return 2;
}

int main(int argc, char **argv) {
    if (argc >= 2 && strcmp(argv[1], "test") == 0) return run_test();
    if (argc < 3) return usage(argv[0]);

    lsm_t e;
    if (lsm_open(&e, argv[2]) != 0) {
        fprintf(stderr, "lsmkv: 打开目录 %s 失败\n", argv[2]);
        return 1;
    }
    int rc = 0;
    if (strcmp(argv[1], "put") == 0 && argc == 5) {
        rc = lsm_put(&e, argv[3], argv[4]) == 0 ? 0 : 1;
        if (rc == 0) printf("OK\n");
    } else if (strcmp(argv[1], "get") == 0 && argc == 4) {
        char val[1024];
        rc = lsm_get(&e, argv[3], val, sizeof val);
        if (rc == 0) printf("%s\n", val);
        else if (rc == 1) { printf("(not found)\n"); rc = 1; }
    } else if (strcmp(argv[1], "del") == 0 && argc == 4) {
        rc = lsm_del(&e, argv[3]) == 0 ? 0 : 1;
        if (rc == 0) printf("OK\n");
    } else if (strcmp(argv[1], "flush") == 0 && argc == 3) {
        rc = lsm_flush(&e) == 0 ? 0 : 1;
        if (rc == 0) printf("OK (flushes=%lu)\n", e.flushes);
    } else if (strcmp(argv[1], "stats") == 0 && argc == 3) {
        printf("memtable: %zu 条 / %zu 字节\n", e.mt.len, e.mt.bytes);
        printf("sstable: %d 个, flush %lu 次, bloom 拦截 %lu 次\n",
               e.sst_cnt, e.flushes, total_bloom_skips(&e));
    } else {
        lsm_close(&e);
        return usage(argv[0]);
    }
    lsm_close(&e);
    return rc;
}
