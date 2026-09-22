/* buffer.c —— 带测试的 append-only 字节 buffer 实现（ph11 阶段项目）
 * 实现要点:
 *  - 扩容先做溢出防护(cap 翻倍/加法前检查 SIZE_MAX), 再做 realloc,
 *    失败时原数据不丢(realloc 失败不释放原指针);
 *  - 边界检查全部在"入口"完成: 越界/空指针返回 -1, 不产生 UB;
 *  - append-only: 不提供按位置改写接口, 语义上为顺序写服务。
 */
#include "buffer.h"

#include <stdlib.h>
#include <string.h>

int buf_init(Buffer *b, size_t cap) {
    if (b == NULL) return -1;
    if (cap == 0) cap = 1;                 /* 0 容量退化为 1, 简化后续判断 */
    b->data = malloc(cap);
    if (b->data == NULL) return -1;
    b->len = 0;
    b->cap = cap;
    return 0;
}

void buf_destroy(Buffer *b) {
    if (b == NULL) return;
    free(b->data);
    b->data = NULL;
    b->len = b->cap = 0;
}

int buf_append(Buffer *b, const void *src, size_t n) {
    if (b == NULL || (src == NULL && n > 0)) return -1;
    if (n > b->cap - b->len) {             /* 容量不足: 先检查再做算术 */
        /* 溢出防护: new_cap 至少要 b->len + n, 且要翻倍 */
        if (b->cap > (SIZE_MAX - n) / 2) return -1;
        size_t new_cap = b->cap;
        while (new_cap < b->len + n)
            new_cap *= 2;
        unsigned char *tmp = realloc(b->data, new_cap);
        if (tmp == NULL) return -1;        /* 扩容失败: 原数据不丢 */
        b->data = tmp;
        b->cap = new_cap;
    }
    if (n > 0)
        memcpy(b->data + b->len, src, n);
    b->len += n;
    return 0;
}

int buf_get(const Buffer *b, size_t idx, unsigned char *out) {
    if (b == NULL || out == NULL) return -1;
    if (idx >= b->len) return -1;          /* 边界检查: 越界返回 -1 */
    *out = b->data[idx];
    return 0;
}

size_t buf_len(const Buffer *b) {
    return b == NULL ? 0 : b->len;
}
