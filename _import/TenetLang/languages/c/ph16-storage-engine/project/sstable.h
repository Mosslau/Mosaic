/* sstable.h —— SSTable: 不可变有序文件（稀疏索引 + 内嵌 Bloom Filter）
 *
 * 文件布局（多字节字段显式大端）：
 *   [数据区]  entry*: [klen u32][type u8][vlen u32][key][value]   按 key 升序
 *   [索引区]  稀疏索引: 每 SST_IDX_EVERY 条索引一条: [klen u32][key][off u64]
 *   [bloom 区] bloom_bits 个位（按字节取整存放）
 *   [footer]  32 字节定长: index_off u64 | index_cnt u32 |
 *             bloom_off u64 | bloom_bits u32 | magic u32 "SST1" | reserved u32
 *
 * 查询路径: open 时载入索引与 bloom → get 先查 bloom（肯定不在则零数据区 IO）
 *          → 索引二分 → 块内顺扫至多 SST_IDX_EVERY 条。
 */
#ifndef SSTABLE_H
#define SSTABLE_H

#include <stddef.h>
#include <stdint.h>

#include "bloom.h"
#include "memtable.h"

#define SST_MAGIC 0x53535431u /* "SST1" */
#define SST_IDX_EVERY 4
#define SST_FTR_SIZE 32u

typedef struct {
    char path[256];
    char (*idx_key)[64];   /* 索引 key 表 */
    uint64_t *idx_off;     /* 对应数据区偏移 */
    uint32_t idx_cnt;
    bloom_t bloom;
    /* 诊断计数 */
    unsigned long bloom_skips; /* bloom 判"肯定不在"而省掉的数据区查询次数 */
    unsigned long disk_reads;  /* 真正读数据区的次数 */
} sst_t;

/* 把已升序的 MemTable 内容写成 SSTable; 返回 0 成功 */
int sst_write(const char *path, const memtable_t *m);

/* 打开: 校验 footer/magic, 载入索引与 bloom; 返回 0 成功 */
int sst_open(sst_t *s, const char *path);

/* 查询（三态）: 0 命中(*val 拷入 out) / 1 不存在 / 2 tombstone / -1 错误。
 * tombstone 必须与"不存在"区分: LSM 层从新到旧查到 tombstone 即停。 */
int sst_get(sst_t *s, const char *key, char *out, size_t cap);

void sst_close(sst_t *s);

#endif /* SSTABLE_H */
