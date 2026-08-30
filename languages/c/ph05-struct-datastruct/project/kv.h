// 来源：project/ —— kvstore 内存表（HashMap KV 表）头文件
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99
// 编译：gcc -Wall -Wextra -std=c99 kv.c main.c -o kvstore
// 验证状态：已验证
#ifndef KV_H
#define KV_H

#include <stddef.h>

typedef struct KVNode {
    char          *key;
    char          *value;
    struct KVNode *next;
} KVNode;

typedef struct {
    KVNode **buckets;
    size_t   bucket_count;
    size_t   size;
} KVStore;

/* 创建：默认 101 桶；失败返回 NULL */
KVStore *kv_create(void);

/* 销毁：释放全部 key/value/节点 */
void kv_destroy(KVStore *kv);

/* 写入：键已存在覆盖值返回 1；新建返回 0；内存不足返回 -1 */
int kv_put(KVStore *kv, const char *key, const char *value);

/* 读取：存在则拷入 out 缓冲区（out_cap 含 \0）返回 1；不存在返回 0 */
int kv_get(const KVStore *kv, const char *key, char *out, size_t out_cap);

/* 删除：存在返回 1，不存在返回 0 */
int kv_delete(KVStore *kv, const char *key);

int kv_contains(const KVStore *kv, const char *key);

size_t kv_size(const KVStore *kv);

/* 遍历：对每个 key 调用 visitor(key)；返回访问的键数 */
size_t kv_keys(const KVStore *kv, void (*visitor)(const char *key));

#endif /* KV_H */
