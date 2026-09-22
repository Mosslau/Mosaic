/* ex03-memtable.c —— MemTable：有序内存表（动态数组 + 二分查找）
 *
 * MemTable 是 LSM 树的内存层：所有写入先进它, 保持 key 有序, 写满后整体
 * flush 成 SSTable（ex04）。本例用"动态数组 + 二分插入"实现最小可用版：
 *   - put: 二分定位, 已存在则覆盖, 不存在则插入保序（O(log n) 定位 + O(n) 搬移）
 *   - del: 写入 tombstone（删除标记）而不是真删——与 WAL/SSTable 的删除语义一致
 *   - get: 二分命中后看 type: tombstone → "不存在"
 *   - 迭代: 数组天然有序, for 循环即 range scan（衔接 3.9 iterator）
 *
 * 工程上 MemTable 常用跳表（LevelDB）或平衡树; 数组版胜在 30 行讲清语义,
 * 二分定位的 O(log n) 与跳表一致, 差别只在插入搬移成本（见主文档 3.3）。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：mkdir -p /tmp/ph16c-ex && cc -Wall -Wextra -std=c11 ex03-memtable.c -o /tmp/ph16c-ex/ex03
// 运行：/tmp/ph16c-ex/ex03（无外部产物, 退出码 0）
// 验证状态：已验证（零警告; 覆盖/删除/有序遍历输出均为实测）
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { MT_PUT = 1, MT_DEL = 2 }; /* DEL = tombstone */

typedef struct {
    char *key;
    char *val;   /* DEL 记录里 val 为 NULL */
    uint8_t type;
} mt_entry_t;

typedef struct {
    mt_entry_t *e;
    size_t len;
    size_t cap;
} memtable_t;

static void mt_init(memtable_t *m) { m->e = NULL; m->len = 0; m->cap = 0; }

static void mt_free(memtable_t *m) {
    for (size_t i = 0; i < m->len; i++) {
        free(m->e[i].key);
        free(m->e[i].val);
    }
    free(m->e);
    mt_init(m);
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

static char *xstrdup(const char *s) {
    size_t n = strlen(s) + 1;
    char *p = malloc(n);
    if (p) memcpy(p, s, n);
    return p;
}

static int mt_put(memtable_t *m, const char *key, const char *val) {
    int found;
    size_t pos = mt_lower(m, key, &found);
    if (found) { /* 覆盖: 换 value, type 归 PUT */
        free(m->e[pos].val);
        m->e[pos].val = xstrdup(val);
        m->e[pos].type = MT_PUT;
        return m->e[pos].val ? 0 : -1;
    }
    if (m->len == m->cap) {
        size_t ncap = m->cap ? m->cap * 2 : 16;
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
    return 0;
}

static int mt_del(memtable_t *m, const char *key) {
    int found;
    size_t pos = mt_lower(m, key, &found);
    if (!found) return -1; /* 简化: 只删存在的 key（工程上允许 tombstone 不存在的 key） */
    free(m->e[pos].val);
    m->e[pos].val = NULL;
    m->e[pos].type = MT_DEL; /* tombstone: 不挪数组, 只改标记 */
    return 0;
}

/* 返回 0 命中; 1 不存在（含 tombstone）; value 为借用指针 */
static int mt_get(const memtable_t *m, const char *key, const char **val) {
    int found;
    size_t pos = mt_lower(m, key, &found);
    if (!found || m->e[pos].type == MT_DEL) return 1;
    *val = m->e[pos].val;
    return 0;
}

int main(void) {
    memtable_t m;
    mt_init(&m);

    printf("=== MemTable: 有序内存表 ===\n");
    mt_put(&m, "banana", "3");
    mt_put(&m, "apple", "1");
    mt_put(&m, "cherry", "5");
    mt_put(&m, "apple", "2"); /* 覆盖 */
    printf("[1] 乱序写入 4 次后, 内部保持有序（len=%zu）:\n", m.len);
    for (size_t i = 0; i < m.len; i++)
        printf("    %s = %s\n", m.e[i].key, m.e[i].val);

    const char *v = NULL;
    int rc = mt_get(&m, "apple", &v);
    printf("[2] get(apple) rc=%d value=%s (覆盖生效)\n", rc, v);
    rc = mt_get(&m, "grape", &v);
    printf("    get(grape) rc=%d (未命中)\n", rc);

    mt_del(&m, "banana");
    rc = mt_get(&m, "banana", &v);
    printf("[3] del(banana) 后 get rc=%d (tombstone: 记录在, 标记删除)\n", rc);
    printf("    内部仍有 %zu 项——tombstone 要等 flush/compact 才真正消失\n", m.len);

    printf("[4] range scan [apple, cherry]（迭代器即下标区间）:\n");
    int f1, f2;
    size_t lo = mt_lower(&m, "apple", &f1);
    size_t hi = mt_lower(&m, "cherry", &f2);
    if (f2) hi++; /* 含端点 */
    for (size_t i = lo; i < hi; i++)
        if (m.e[i].type == MT_PUT)
            printf("    %s = %s\n", m.e[i].key, m.e[i].val);

    mt_free(&m);
    return 0;
}
