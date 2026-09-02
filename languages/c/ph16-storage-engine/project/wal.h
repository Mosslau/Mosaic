/* wal.h —— WAL: 带 type 的 append-only 日志（承接 ph13 kvlog / ph14 kvdb）
 *
 * 记录格式（多字节字段显式大端）：
 *   [magic u32 "WAL1"][type u8][klen u32][vlen u32][key][value][crc32 u32]
 *   固定头 13 字节; crc32 覆盖 type..value; type: 1=PUT 2=DEL(tombstone)。
 *
 * 可靠性契约：
 *   - wal_append 返回只代表数据进了内核 Page Cache
 *   - wal_sync（fsync）返回后才算到达存储设备
 *   - 崩溃最多留下最后一条残记录; wal_replay 停在残尾并报告偏移,
 *     wal_repair（ftruncate）砍掉残尾后恢复可追加
 */
#ifndef WAL_H
#define WAL_H

#include <stdint.h>

#define WAL_MAGIC 0x57414C31u /* "WAL1" */
#define WAL_HDR_SIZE 13u
#define WAL_MAX_KV (256u * 1024u)

enum { WAL_PUT = 1, WAL_DEL = 2 };

/* 回放结果码 */
typedef enum {
    WAL_END_CLEAN = 0, /* 干净 EOF */
    WAL_END_TORN,      /* 残尾, torn_at 有效 */
    WAL_END_IOERR      /* 系统调用失败 */
} wal_end_t;

/* 打开（不存在则创建）追加用 fd; 失败返回 -1 */
int wal_open(const char *path);

/* 追加一条 PUT/DEL 记录; 返回 0 成功, -1 失败 */
int wal_append(int fd, uint8_t type, const char *key, const char *val);

/* fsync 刷盘; 返回 0 成功, -1 失败 */
int wal_sync(int fd);

/* 回放回调: 每条完整记录调用一次; 返回非 0 停止回放 */
typedef int (*wal_visit_fn)(uint8_t type, const char *key, const char *val,
                            void *ctx);

/* 顺序回放: *torn_at 输出残尾偏移（无残尾则 = 文件大小） */
wal_end_t wal_replay(const char *path, wal_visit_fn visit, void *ctx,
                     long *torn_at);

/* 修复: ftruncate 砍掉 torn_at 之后的残尾; 返回 0 成功, -1 失败 */
int wal_repair(const char *path, long torn_at);

#endif /* WAL_H */
