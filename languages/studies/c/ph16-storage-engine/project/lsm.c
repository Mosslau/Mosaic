/* lsm.c —— LSM KV 引擎实现（接口与简化声明见 lsm.h） */
#include "lsm.h"
#include "wal.h"

#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>

/* ---- 打开辅助 ---- */

static int cmp_u64(const void *a, const void *b) {
    uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
    return (x > y) - (x < y);
}

/* mkdir -p: 逐级创建目录（已存在视为成功） */
static int mkdir_p(const char *path) {
    char tmp[320];
    snprintf(tmp, sizeof tmp, "%s", path);
    for (char *p = tmp + 1; *p; p++) {
        if (*p == '/') {
            *p = '\0';
            if (mkdir(tmp, 0755) != 0 && errno != EEXIST) return -1;
            *p = '/';
        }
    }
    if (mkdir(tmp, 0755) != 0 && errno != EEXIST) return -1;
    return 0;
}

/* 收集目录里全部 sst-*.dat 的编号, 升序返回 */
static int collect_sst_ids(const char *dir, uint64_t *ids, int cap) {
    DIR *d = opendir(dir);
    if (!d) return 0;
    int n = 0;
    struct dirent *de;
    while ((de = readdir(d)) != NULL && n < cap) {
        unsigned long long id;
        char tail[8];
        if (sscanf(de->d_name, "sst-%llu.dat%7s", &id, tail) == 1)
            ids[n++] = (uint64_t)id;
    }
    closedir(d);
    qsort(ids, (size_t)n, sizeof *ids, cmp_u64);
    return n;
}

/* WAL 回放回调: 把每条记录写回 MemTable */
static int replay_to_mt(uint8_t type, const char *key, const char *val, void *ctx) {
    memtable_t *m = ctx;
    if (type == WAL_PUT) return mt_put(m, key, val) == 0 ? 0 : 1;
    return mt_del(m, key) == 0 ? 0 : 1;
}

int lsm_open(lsm_t *e, const char *dir) {
    memset(e, 0, sizeof *e);
    snprintf(e->dir, sizeof e->dir, "%s", dir);
    if (mkdir_p(dir) != 0) return -1;
    mt_init(&e->mt);

    /* 1. 载入既有 SSTable（编号升序 = 从旧到新） */
    uint64_t ids[LSM_MAX_SST];
    int n = collect_sst_ids(dir, ids, LSM_MAX_SST);
    for (int i = 0; i < n; i++) {
        char p[320];
        snprintf(p, sizeof p, "%s/sst-%06llu.dat", dir,
                 (unsigned long long)ids[i]);
        if (sst_open(&e->ssts[e->sst_cnt], p) != 0) goto fail;
        e->sst_cnt++;
        if (ids[i] >= e->next_sst_id) e->next_sst_id = ids[i] + 1;
    }

    /* 2. replay WAL 重建 MemTable; 残尾修复后继续 */
    snprintf(e->wal_path, sizeof e->wal_path, "%s/wal.log", dir);
    long torn = 0;
    wal_end_t r = wal_replay(e->wal_path, replay_to_mt, &e->mt, &torn);
    if (r == WAL_END_TORN) wal_repair(e->wal_path, torn);

    /* 3. 打开 WAL 准备追加 */
    e->wal_fd = wal_open(e->wal_path);
    if (e->wal_fd < 0) goto fail;
    return 0;

fail:
    for (int i = 0; i < e->sst_cnt; i++) sst_close(&e->ssts[i]);
    mt_free(&e->mt);
    return -1;
}

int lsm_flush(lsm_t *e) {
    if (e->mt.len == 0 || e->sst_cnt >= LSM_MAX_SST) return 0;
    char p[320];
    snprintf(p, sizeof p, "%s/sst-%06llu.dat", e->dir,
             (unsigned long long)e->next_sst_id);
    /* 1. 落盘并打开新 SSTable; 失败删掉（可能半写的）文件, 内存态未动 → 可原样重试 */
    if (sst_write(p, &e->mt) != 0) { remove(p); return -1; }
    if (sst_open(&e->ssts[e->sst_cnt], p) != 0) { remove(p); return -1; }
    /* 2. SSTable 落盘后才清 WAL——顺序即崩溃安全; 至此提交内存态 */
    e->sst_cnt++;
    e->next_sst_id++;
    e->flushes++;
    close(e->wal_fd);
    /* 3. WAL 清空失败（wal_repair 出错）: WAL 内容原封未动, 回滚第 2 步提交并
     *    重开 WAL, 让引擎回到 flush 前的可写状态——否则 wal_fd 永久关闭,
     *    后续 put/del 全部落空而调用方无从知道。 */
    if (wal_repair(e->wal_path, 0) != 0) {
        sst_close(&e->ssts[e->sst_cnt - 1]);
        e->sst_cnt--;
        e->next_sst_id--;
        e->flushes--;
        e->wal_fd = wal_open(e->wal_path); /* 重开仍失败则 wal_fd=-1, 写入安全失败 */
        return -1;
    }
    e->wal_fd = wal_open(e->wal_path);
    if (e->wal_fd < 0) {
        /* WAL 已清空但重开失败: 数据都已落进第 1 步的新 SSTable, 不会丢;
         * memtable 未释放, wal_fd=-1 使后续写入安全失败（引擎退化为只读态） */
        return -1;
    }
    mt_free(&e->mt);
    return 0;
}

static int maybe_flush(lsm_t *e) {
    if (e->mt.bytes >= LSM_FLUSH_BYTES) return lsm_flush(e);
    return 0;
}

int lsm_put(lsm_t *e, const char *key, const char *val) {
    if (wal_append(e->wal_fd, WAL_PUT, key, val) != 0) return -1;
    if (wal_sync(e->wal_fd) != 0) return -1; /* 先持久化, 再写内存 */
    if (mt_put(&e->mt, key, val) != 0) return -1;
    return maybe_flush(e);
}

int lsm_del(lsm_t *e, const char *key) {
    if (wal_append(e->wal_fd, WAL_DEL, key, "") != 0) return -1;
    if (wal_sync(e->wal_fd) != 0) return -1;
    if (mt_del(&e->mt, key) != 0) return -1;
    return maybe_flush(e);
}

int lsm_get(lsm_t *e, const char *key, char *val_out, size_t cap) {
    /* 1. MemTable（最新数据）; tombstone 立即挡住所有旧层 */
    const char *v;
    int rc = mt_probe(&e->mt, key, &v);
    if (rc == 0) {
        snprintf(val_out, cap, "%s", v);
        return 0;
    }
    if (rc == 2) return 1;
    /* 2. SSTable 从新到旧; 每层先过 Bloom Filter;
     *    第一个"有该 key 记录"的层生效: PUT → 命中, tombstone → 不存在 */
    for (int i = e->sst_cnt - 1; i >= 0; i--) {
        rc = sst_get(&e->ssts[i], key, val_out, cap);
        if (rc == 0) return 0;
        if (rc == 2) return 1;
        /* rc == 1: 本层无此 key, 继续更旧的层 */
    }
    return 1;
}

void lsm_close(lsm_t *e) {
    if (e->wal_fd >= 0) {
        wal_sync(e->wal_fd);
        close(e->wal_fd);
        e->wal_fd = -1;
    }
    for (int i = 0; i < e->sst_cnt; i++) sst_close(&e->ssts[i]);
    mt_free(&e->mt);
}
