/* bloom.h —— Bloom Filter: 位数组 + 双哈希（k 个哈希由 h1/h2 合成） */
#ifndef BLOOM_H
#define BLOOM_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint8_t *bits;
    size_t nbits;
    uint32_t k;
} bloom_t;

/* 创建（nbits 向上取整到字节）; 失败返回 -1 */
int bloom_init(bloom_t *b, size_t nbits, uint32_t k);
void bloom_free(bloom_t *b);

void bloom_add(bloom_t *b, const char *key);
/* 返回 1=可能在, 0=肯定不在 */
int bloom_maybe(const bloom_t *b, const char *key);

#endif /* BLOOM_H */
