/* lsm.h —— LSM KV 引擎: WAL + MemTable + SSTable(+Bloom) 串联
 *
 * 写入路径: put/del → 先追加 WAL（崩溃恢复保险）→ 写 MemTable →
 *          MemTable 字节数超阈值 → flush 成新 SSTable + 清空 WAL
 * 查询路径: get → MemTable → SSTable 从新到旧（每个先过 Bloom Filter）
 * 恢复路径: open 时 replay WAL 重建 MemTable, 载入全部既有 SSTable
 *
 * 教学版简化（README 已声明）：单线程、无 compaction（SSTable 只增不并）、
 * key/value 为不含 NUL 的文本、单条 ≤ 4 KiB。
 */
#ifndef LSM_H
#define LSM_H

#include "memtable.h"
#include "sstable.h"

#define LSM_MAX_SST 64
#define LSM_FLUSH_BYTES 4096 /* MemTable 超过 4 KiB 即 flush */

typedef struct {
    char dir[256];
    char wal_path[320];
    int wal_fd;
    memtable_t mt;
    sst_t ssts[LSM_MAX_SST]; /* 按编号升序 = 从旧到新 */
    int sst_cnt;
    unsigned long next_sst_id;
    /* 诊断 */
    unsigned long flushes;
} lsm_t;

/* 打开/创建目录下的引擎: 载入 SSTable + replay WAL; 返回 0 成功 */
int lsm_open(lsm_t *e, const char *dir);

int lsm_put(lsm_t *e, const char *key, const char *val);
int lsm_del(lsm_t *e, const char *key);
/* 0 命中(*val 借用内部缓冲, 下次 get 前有效) / 1 不存在 / -1 错误 */
int lsm_get(lsm_t *e, const char *key, char *val_out, size_t cap);

/* 强制把 MemTable flush 成 SSTable（写满自动触发, 也可手动调用） */
int lsm_flush(lsm_t *e);

void lsm_close(lsm_t *e);

#endif /* LSM_H */
