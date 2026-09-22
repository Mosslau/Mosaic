/* kvdb.h —— ph14 阶段项目: C ABI KV 库（WAL 持久化, opaque handle, 错误码/消息）
 *
 * 跨语言契约（roadmap §14 必会概念全部落地）：
 *   - opaque pointer：kvdb_t 结构体藏在 kvdb.c，调用方（任何语言）只持有指针
 *   - create/destroy API：kvdb_create 打开/创建 WAL 并回放重建内存态，
 *     kvdb_destroy 释放全部资源——"谁 create 谁 destroy"
 *   - 简单稳定类型：int32_t / uint32_t / const char * / uint8_t *（定宽,
 *     不依赖平台 int 宽度）
 *   - 错误码与错误消息：0 成功、负数错误（数值稳定，一经发布不改），
 *     消息经 kvdb_strerror 读取（静态字符串，借用）；不用 errno
 *   - 所有权规则：kvdb_put 拷贝 key/val（C 侧持有副本，不持有调用方内存）；
 *     kvdb_get 写入调用方缓冲区（缓冲区由调用方分配）；字符串只读借用
 *   - WAL 语义（衔接 ph13 可靠文件 IO）：每次 put 追加一条记录
 *     [magic "KVDB"][plen u32][crc32 u32][klen u32][key][vlen u32][val]；
 *     kvdb_sync 显式 fsync——write 成功 ≠ 持久化，崩溃最多丢最后一次
 *     sync 之后的数据
 */
#ifndef KVDB_H
#define KVDB_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct kvdb kvdb_t;   /* opaque */

/* 错误码（跨语言消费: Python/Rust 按同一数值判断 + kvdb_strerror 读消息） */
#define KVDB_OK        0
#define KVDB_ERR_BADARG   (-1)  /* 参数非法（NULL/空 key、缓冲区不够） */
#define KVDB_ERR_NOMEM    (-2)  /* 内存不足 */
#define KVDB_ERR_IO       (-3)  /* 文件 IO / WAL 写失败 */
#define KVDB_ERR_FULL     (-4)  /* 容量已满（教学实现用固定容量） */
#define KVDB_ERR_NOTFOUND (-5)  /* key 不存在 */

#define KVDB_MAX_KEYS 256u
#define KVDB_MAX_KEY_LEN 128u
#define KVDB_MAX_VAL_LEN (1024u * 1024u)

/* create：打开/创建 path 处的 WAL，回放重建内存态；
 * 失败返回 NULL 且 *err_out 写入错误码 */
kvdb_t *kvdb_create(const char *path, int32_t *err_out);

/* put：写入/覆盖 key（拷贝语义）；追加一条 WAL 记录（未 fsync，
 * 持久化边界见 kvdb_sync）；返回 0 成功或负错误码 */
int32_t kvdb_put(kvdb_t *db, const char *key,
                 const uint8_t *val, uint32_t vlen);

/* get：读 key 到调用方缓冲区 out（cap 为容量）；
 * 成功返回 0 且 *vlen_out = 值长度；缓冲区不够返回 KVDB_ERR_BADARG；
 * key 不存在返回 KVDB_ERR_NOTFOUND */
int32_t kvdb_get(kvdb_t *db, const char *key,
                 uint8_t *out, uint32_t cap, uint32_t *vlen_out);

/* sync：fsync WAL（write 成功 ≠ 持久化，ph13 语义） */
int32_t kvdb_sync(kvdb_t *db);

/* destroy：释放全部资源（内存 + 关闭文件）；返回 KVDB_OK */
int32_t kvdb_destroy(kvdb_t *db);

/* 错误消息：静态字符串，借用（无需释放） */
const char *kvdb_strerror(int32_t err);

#ifdef __cplusplus
}
#endif

#endif /* KVDB_H */
