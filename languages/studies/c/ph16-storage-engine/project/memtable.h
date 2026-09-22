/* memtable.h —— MemTable: 有序内存表（动态数组 + 二分定位）
 *
 * 所有写入先进 MemTable 并保序; 写满（字节数超阈值）后整体 flush 成 SSTable。
 * 删除写入 tombstone（type=DEL 的记录）, 真正清理由 flush/compaction 完成。
 */
#ifndef MEMTABLE_H
#define MEMTABLE_H

#include <stddef.h>
#include <stdint.h>

enum { MT_PUT = 1, MT_DEL = 2 };

typedef struct {
    char *key;
    char *val;    /* DEL 记录里为 NULL */
    uint8_t type;
} mt_entry_t;

typedef struct {
    mt_entry_t *e;
    size_t len;
    size_t cap;
    size_t bytes; /* key+val 字节合计, 用于 flush 阈值判断 */
} memtable_t;

void mt_init(memtable_t *m);
void mt_free(memtable_t *m);

/* 写入/覆盖; 返回 0 成功, -1 内存不足 */
int mt_put(memtable_t *m, const char *key, const char *val);

/* 删除: 对 key 打 tombstone——存在的 key 改标记, 不存在的 key 也补打
 * tombstone（幂等容忍: 删除不存在的 key 不算错误）; 返回 0 成功, -1 内存不足 */
int mt_del(memtable_t *m, const char *key);

/* 查询（三态）: 0 命中(*val 借用指针) / 1 不存在 / 2 tombstone。
 * tombstone 必须与普通"不存在"区分: LSM 层用它挡住更旧的 SSTable。 */
int mt_probe(const memtable_t *m, const char *key, const char **val);

#endif /* MEMTABLE_H */
