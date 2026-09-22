// 来源：project/ —— kvstore 内存表（HashMap KV 表）实现
// 链地址法 + djb2 变体哈希；值拷贝语义，不依赖调用者缓冲区生命周期
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99
// 编译：gcc -Wall -Wextra -std=c99 kv.c main.c -o kvstore
// 验证状态：已验证
#include "kv.h"

#include <stdlib.h>
#include <string.h>

#define KV_DEFAULT_BUCKETS 101

static unsigned int kv_hash(const char *key, size_t bucket_count) {
    unsigned int hash = 5381;
    int c;
    while ((c = *key++)) hash = ((hash << 5) + hash) + (unsigned int)c;
    return hash % bucket_count;
}

static char *kv_strdup(const char *s) {
    size_t len = strlen(s) + 1;
    char *copy = malloc(len);
    if (copy != NULL) memcpy(copy, s, len);
    return copy;
}

KVStore *kv_create(void) {
    KVStore *kv = malloc(sizeof(KVStore));
    if (kv == NULL) return NULL;
    kv->buckets = calloc(KV_DEFAULT_BUCKETS, sizeof(KVNode *));
    if (kv->buckets == NULL) { free(kv); return NULL; }
    kv->bucket_count = KV_DEFAULT_BUCKETS;
    kv->size = 0;
    return kv;
}

void kv_destroy(KVStore *kv) {
    if (kv == NULL) return;
    for (size_t i = 0; i < kv->bucket_count; i++) {
        KVNode *cur = kv->buckets[i];
        while (cur != NULL) {
            KVNode *tmp = cur;
            cur = cur->next;
            free(tmp->key);
            free(tmp->value);
            free(tmp);
        }
    }
    free(kv->buckets);
    free(kv);
}

int kv_put(KVStore *kv, const char *key, const char *value) {
    unsigned int idx = kv_hash(key, kv->bucket_count);
    for (KVNode *cur = kv->buckets[idx]; cur != NULL; cur = cur->next) {
        if (strcmp(cur->key, key) == 0) {          /* 覆盖写入 */
            char *new_value = kv_strdup(value);
            if (new_value == NULL) return -1;
            free(cur->value);
            cur->value = new_value;
            return 1;
        }
    }
    KVNode *n = malloc(sizeof(KVNode));
    if (n == NULL) return -1;
    n->key = kv_strdup(key);
    n->value = kv_strdup(value);
    if (n->key == NULL || n->value == NULL) {
        free(n->key);
        free(n->value);
        free(n);
        return -1;
    }
    n->next = kv->buckets[idx];
    kv->buckets[idx] = n;
    kv->size++;
    return 0;
}

int kv_get(const KVStore *kv, const char *key, char *out, size_t out_cap) {
    unsigned int idx = kv_hash(key, kv->bucket_count);
    for (KVNode *cur = kv->buckets[idx]; cur != NULL; cur = cur->next) {
        if (strcmp(cur->key, key) == 0) {
            size_t vlen = strlen(cur->value);
            if (out == NULL || out_cap == 0) return 1;   /* 只探测存在性 */
            if (vlen >= out_cap) vlen = out_cap - 1;     /* 截断防溢出 */
            memcpy(out, cur->value, vlen);
            out[vlen] = '\0';
            return 1;
        }
    }
    return 0;
}

int kv_delete(KVStore *kv, const char *key) {
    unsigned int idx = kv_hash(key, kv->bucket_count);
    KVNode *cur = kv->buckets[idx], *prev = NULL;
    while (cur != NULL && strcmp(cur->key, key) != 0) {
        prev = cur;
        cur = cur->next;
    }
    if (cur == NULL) return 0;
    if (prev == NULL) kv->buckets[idx] = cur->next;
    else              prev->next = cur->next;
    free(cur->key);
    free(cur->value);
    free(cur);
    kv->size--;
    return 1;
}

int kv_contains(const KVStore *kv, const char *key) {
    unsigned int idx = kv_hash(key, kv->bucket_count);
    for (KVNode *cur = kv->buckets[idx]; cur != NULL; cur = cur->next)
        if (strcmp(cur->key, key) == 0) return 1;
    return 0;
}

size_t kv_size(const KVStore *kv) {
    return kv ? kv->size : 0;
}

size_t kv_keys(const KVStore *kv, void (*visitor)(const char *key)) {
    size_t visited = 0;
    for (size_t i = 0; i < kv->bucket_count; i++)
        for (KVNode *cur = kv->buckets[i]; cur != NULL; cur = cur->next) {
            if (visitor != NULL) visitor(cur->key);
            visited++;
        }
    return visited;
}
