/* ex06-lru-buffer-pool.c —— Buffer Pool / LRU：哈希表 + 双向链表
 *
 * Buffer Pool 缓存磁盘页（SSTable 数据块）: 读页先查池, 命中直接用,
 * 未命中从"磁盘"载入, 池满时淘汰最久未用（LRU）的页。脏页被淘汰前必须
 * 先写回——这是 Buffer Pool 与普通 LRU Cache 的唯一本质差别（主文档 3.8）。
 *
 * 结构 = 哈希表（O(1) 按页号找节点） + 双向链表（O(1) 挪到头部/淘汰尾部）：
 *   头部 = 最近使用, 尾部 = 最久未用（淘汰候选）
 *
 * 本例用数组模拟 100 个磁盘页, 统计命中率与脏页写回次数。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：mkdir -p /tmp/ph16c-ex && cc -Wall -Wextra -std=c11 ex06-lru-buffer-pool.c -o /tmp/ph16c-ex/ex06
// 运行：/tmp/ph16c-ex/ex06（无外部产物, 退出码 0）
// 验证状态：已验证（零警告; 命中率/写回次数/淘汰顺序均为实测）
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define POOL_CAP 4          /* 池容量 4 页（小容量好演示淘汰） */
#define DISK_PAGES 100      /* 模拟磁盘 100 页 */
#define HASH_SIZE 16        /* 哈希桶数（页号 % 16） */

typedef struct page {
    int page_no;
    int dirty;              /* 脏页: 被淘汰前必须写回 */
    char data[32];
    struct page *prev, *next;   /* LRU 双向链表 */
    struct page *hnext;         /* 哈希链 */
} page_t;

typedef struct {
    page_t pages[POOL_CAP];
    page_t *head, *tail;        /* LRU 链表: 头=最新, 尾=最旧 */
    page_t *htab[HASH_SIZE];    /* 页号 → 页 */
    page_t *free_list;          /* 空闲页框 */
    int hits, misses, writebacks;
    char disk[DISK_PAGES][32];  /* 模拟磁盘 */
} pool_t;

static void pool_init(pool_t *p) {
    memset(p, 0, sizeof *p);
    for (int i = 0; i < POOL_CAP; i++) {
        p->pages[i].page_no = -1;
        p->pages[i].next = p->free_list;
        p->free_list = &p->pages[i];
    }
    for (int i = 0; i < DISK_PAGES; i++)
        snprintf(p->disk[i], 32, "page-data-%d", i);
}

/* 从 LRU 链表摘除 */
static void lru_remove(pool_t *p, page_t *pg) {
    if (pg->prev) pg->prev->next = pg->next; else p->head = pg->next;
    if (pg->next) pg->next->prev = pg->prev; else p->tail = pg->prev;
}

/* 插到头部（最近使用） */
static void lru_push_front(pool_t *p, page_t *pg) {
    pg->prev = NULL;
    pg->next = p->head;
    if (p->head) p->head->prev = pg;
    p->head = pg;
    if (!p->tail) p->tail = pg;
}

static page_t *hash_find(pool_t *p, int no) {
    for (page_t *q = p->htab[no % HASH_SIZE]; q; q = q->hnext)
        if (q->page_no == no) return q;
    return NULL;
}
static void hash_add(pool_t *p, page_t *pg) {
    int b = pg->page_no % HASH_SIZE;
    pg->hnext = p->htab[b];
    p->htab[b] = pg;
}
static void hash_del(pool_t *p, page_t *pg) {
    int b = pg->page_no % HASH_SIZE;
    page_t **pp = &p->htab[b];
    while (*pp && *pp != pg) pp = &(*pp)->hnext;
    if (*pp) *pp = pg->hnext;
}

/* 取页: 命中挪头部; 未命中淘汰尾部（脏页先写回）再载入 */
static page_t *pool_get(pool_t *p, int no, int *hit) {
    page_t *pg = hash_find(p, no);
    if (pg) {
        p->hits++;
        *hit = 1;
        lru_remove(p, pg);
        lru_push_front(p, pg);
        return pg;
    }
    p->misses++;
    *hit = 0;
    if (p->free_list) {             /* 有空闲页框直接用 */
        pg = p->free_list;
        p->free_list = pg->next;
    } else {                        /* 淘汰 LRU 尾部 */
        pg = p->tail;
        if (pg->dirty) {            /* 脏页先写回模拟磁盘 */
            memcpy(p->disk[pg->page_no], pg->data, 32);
            p->writebacks++;
            printf("    [淘汰写回] 页 %d 是脏页, 写回磁盘\n", pg->page_no);
        } else {
            printf("    [淘汰丢弃] 页 %d 干净, 直接覆盖\n", pg->page_no);
        }
        hash_del(p, pg);
        lru_remove(p, pg);
    }
    pg->page_no = no;
    pg->dirty = 0;
    memcpy(pg->data, p->disk[no], 32); /* 从"磁盘"读入 */
    hash_add(p, pg);
    lru_push_front(p, pg);
    return pg;
}

int main(void) {
    pool_t p;
    pool_init(&p);
    int hit;

    printf("=== Buffer Pool / LRU（池容量 %d 页, 模拟磁盘 %d 页） ===\n",
           POOL_CAP, DISK_PAGES);

    printf("[1] 顺序读页 0..3（装满池, 全部 miss）:\n");
    for (int i = 0; i < 4; i++) {
        page_t *pg = pool_get(&p, i, &hit);
        printf("    read 页 %d → miss, 载入 \"%s\"\n", i, pg->data);
    }

    printf("[2] 再读页 0（hit, 挪到头部成为最新）:\n");
    pool_get(&p, 0, &hit);
    printf("    read 页 0 → %s\n", hit ? "hit" : "miss");

    printf("[3] 读页 4（池满 → 淘汰 LRU 尾部; 页 1 此时最旧）:\n");
    pool_get(&p, 4, &hit);

    printf("[4] 写页 2（置脏）再连续读页 5 6 7 8（逼出脏页, 观察写回）:\n");
    page_t *pg = pool_get(&p, 2, &hit);
    snprintf(pg->data, 32, "page-data-2-DIRTY");
    pg->dirty = 1;
    for (int i = 5; i <= 8; i++) pool_get(&p, i, &hit);

    printf("[5] 读页 2 验证脏数据未丢（它被淘汰过, 但已先写回磁盘）:\n");
    pg = pool_get(&p, 2, &hit);
    printf("    read 页 2 → %s, data=\"%s\"\n", hit ? "hit" : "miss(从磁盘重载)", pg->data);

    int total = p.hits + p.misses;
    printf("\n统计: 共 %d 次访问, 命中 %d, 未命中 %d（命中率 %.1f%%）, 脏页写回 %d 次\n",
           total, p.hits, p.misses, 100.0 * p.hits / total, p.writebacks);
    return 0;
}
