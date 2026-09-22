/* kvl.h —— kvlog: 可靠 append-only log 的格式与接口
 *
 * 记录格式（多字节字段显式大端, 衔接 ph12 的线上格式纪律）：
 *   [magic: u32 = "KVL1"][len: u32][crc32: u32][payload: len 字节]
 *   头部 12 字节; crc32 覆盖 payload; len 上限 1 MiB。
 *
 * 可靠性契约：
 *   - 追加：fd 以 O_APPEND 打开, 每次 write 原子落到文件末尾
 *   - 持久化：kvl_append 返回只代表数据进了内核 Page Cache;
 *     kvl_sync（fsync）返回后才算到达存储设备（macOS 真落盘见 README）
 *   - 恢复：崩溃最多留下最后一条残记录; kvl_replay 在残记录处停下并报告
 *     偏移, kvl_repair（ftruncate）砍掉残尾后文件恢复可追加状态
 */
#ifndef KVL_H
#define KVL_H

#include <stdint.h>
#include <sys/types.h>

#define KVL_MAGIC 0x4B564C31u /* "KVL1" */
#define KVL_HDR_SIZE 12u
#define KVL_MAX_PAYLOAD (1024u * 1024u)

/* 回放结果码：最后一条记录的状态 */
typedef enum {
    KVL_END_CLEAN = 0, /* 干净 EOF，无残尾 */
    KVL_END_TORN,      /* 残尾（截断/损坏）已跳过，torn_at 有效 */
    KVL_END_IOERR      /* 系统调用失败 */
} kvl_end_t;

/* 打开（不存在则创建）用于追加的 fd；失败返回 -1 */
int kvl_open_append(const char *path);

/* 追加一条记录；返回 0 成功，-1 失败（errno 保留） */
int kvl_append(int fd, const void *payload, uint32_t len);

/* fsync 刷盘；返回 0 成功，-1 失败 */
int kvl_sync(int fd);

/* 回放回调：对每条完整记录调用一次；返回非 0 停止回放 */
typedef int (*kvl_visit_fn)(const uint8_t *payload, uint32_t len, void *ctx);

/* 顺序回放文件：
 *   *count 输出完整记录数；*torn_at 输出残尾偏移（无残尾则 = 文件大小）。
 *   返回 KVL_END_* 结果码。visit 可为 NULL（只统计不访问）。 */
kvl_end_t kvl_replay(const char *path, kvl_visit_fn visit, void *ctx,
                     int *count, off_t *torn_at);

/* 修复：ftruncate 砍掉 torn_at 之后的残尾；返回 0 成功，-1 失败 */
int kvl_repair(const char *path, off_t torn_at);

/* CRC-32（IEEE 802.3，反射多项式），暴露给测试与工具 */
uint32_t kvl_crc32(const uint8_t *data, uint32_t len);

#endif /* KVL_H */
