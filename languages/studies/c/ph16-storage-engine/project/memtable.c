/* memtable.c —— MemTable 实现（接口见 memtable.h） */
#include "memtable.h"

#include <stdlib.h>
#include <string.h>

void mt_init(memtable_t *m) {
    m->e = NULL;
    m->len = 0;
    m->cap = 0;
    m->bytes = 0;
}

void mt_free(memtable_t *m) {
    for (size_t i = 0; i < m->len; i++) {
        free(m->e[i].key);
        free(m->e[i].val);
    }
    free(m->e);
    mt_init(m);
}

static char *xstrdup(const char *s) {
    size_t n = strlen(s) + 1;
    char *p = malloc(n);
    if (p) memcpy(p, s, n);
    return p;
}

/* 二分定位: 找到返回下标且 *found=1; 未找到返回插入点且 *found=0 */
static size_t mt_lower(const memtable_t *m, const char *key, int *found) {
    size_t lo = 0, hi = m->len;
    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;
        if (strcmp(m->e[mid].key, key) < 0) lo = mid + 1;
        else hi = mid;
    }
    *found = (lo < m->len && strcmp(m->e[lo].key, key) == 0);
    return lo;
}

int mt_put(memtable_t *m, const char *key, const char *val) {
    int found;
    size_t pos = mt_lower(m, key, &found);
    if (found) {
        size_t old = m->e[pos].val ? strlen(m->e[pos].val) : 0;
        free(m->e[pos].val);
        m->e[pos].val = xstrdup(val);
        if (!m->e[pos].val) return -1;
        m->e[pos].type = MT_PUT;
        m->bytes += strlen(val) - old;
        return 0;
    }
    if (m->len == m->cap) {
        size_t ncap = m->cap ? m->cap * 2 : 32;
        mt_entry_t *ne = realloc(m->e, ncap * sizeof *ne);
        if (!ne) return -1;
        m->e = ne;
        m->cap = ncap;
    }
    memmove(&m->e[pos + 1], &m->e[pos], (m->len - pos) * sizeof *m->e);
    m->e[pos].key = xstrdup(key);
    m->e[pos].val = xstrdup(val);
    m->e[pos].type = MT_PUT;
    if (!m->e[pos].key || !m->e[pos].val) return -1;
    m->len++;
    m->bytes += strlen(key) + strlen(val);
    return 0;
}

int mt_del(memtable_t *m, const char *key) {
    int found;
    size_t pos = mt_lower(m, key, &found);
    if (!found) {
        /* tombstone 一个从未见过的 key: 用空值占位（flush 时仍是 DEL） */
        if (mt_put(m, key, "") != 0) return -1;
        pos = mt_lower(m, key, &found);
    }
    free(m->e[pos].val);
    m->e[pos].val = NULL;
    m->e[pos].type = MT_DEL;
    return 0;
}

int mt_probe(const memtable_t *m, const char *key, const char **val) {
    int found;
    size_t pos = mt_lower(m, key, &found);
    if (!found) return 1;
    if (m->e[pos].type == MT_DEL) return 2;
    *val = m->e[pos].val;
    return 0;
}
