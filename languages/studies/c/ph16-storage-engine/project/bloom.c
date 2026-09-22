/* bloom.c —— Bloom Filter 实现（FNV-1a 双哈希法） */
#include "bloom.h"

#include <stdlib.h>

static uint64_t fnv1a(const char *s, uint64_t seed) {
    uint64_t h = 1469598103934665603ULL ^ (seed * 1099511628211ULL);
    for (; *s; s++) {
        h ^= (uint8_t)*s;
        h *= 1099511628211ULL;
    }
    return h;
}

int bloom_init(bloom_t *b, size_t nbits, uint32_t k) {
    b->bits = calloc(nbits / 8 + 1, 1);
    if (!b->bits) return -1;
    b->nbits = nbits;
    b->k = k;
    return 0;
}

void bloom_free(bloom_t *b) {
    free(b->bits);
    b->bits = NULL;
}

void bloom_add(bloom_t *b, const char *key) {
    uint64_t h1 = fnv1a(key, 1), h2 = fnv1a(key, 2);
    for (uint32_t i = 0; i < b->k; i++) {
        size_t bit = (size_t)((h1 + (uint64_t)i * h2) % b->nbits);
        b->bits[bit / 8] |= (uint8_t)(1u << (bit % 8));
    }
}

int bloom_maybe(const bloom_t *b, const char *key) {
    uint64_t h1 = fnv1a(key, 1), h2 = fnv1a(key, 2);
    for (uint32_t i = 0; i < b->k; i++) {
        size_t bit = (size_t)((h1 + (uint64_t)i * h2) % b->nbits);
        if (!(b->bits[bit / 8] & (uint8_t)(1u << (bit % 8)))) return 0;
    }
    return 1;
}
