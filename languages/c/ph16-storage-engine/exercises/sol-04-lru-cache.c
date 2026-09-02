/* sol-04-lru-cache.c —— 参考实现: LRU Cache（哈希表 + 双向链表）
 *
 * 题目要点:
 *   - O(1) get/put: 哈希表定位 + 双向链表维护"最近使用"顺序
 *   - 头 = 最新, 尾 = 淘汰候选; get/put 命中都挪到头部
 *   - 容量满时淘汰尾部; 淘汰事件通过回调或计数可观测
 * 自测断言: 命中/未命中、覆盖更新、淘汰顺序（最久未用先出局）、容量恒不超。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：mkdir -p /tmp/ph16c-sol && cc -Wall -Wextra -std=c11 sol-04-lru-cache.c -o /tmp/ph16c-sol/sol04
// 运行：/tmp/ph16c-sol/sol04（无外部产物, 退出码 0）
// 验证状态：已验证（零警告; 淘汰顺序与命中统计为实测, 全部断言 PASS）
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define CAP 3
#define HBITS 8

static int g_pass = 0, g_fail = 0;
#define CHECK(cond, name) do { \
    if (cond) { g_pass++; printf("PASS: %s\n", name); } \
    else { g_fail++; printf("FAIL: %s\n", name); } \
} while (0)

typedef struct node {
    int key, val;
    struct node *prev, *next;  /* LRU 链 */
    struct node *hnext;        /* 哈希链 */
} node_t;

typedef struct {
    node_t nodes[CAP];
    node_t *head, *tail;
    node_t *htab[HBITS];
    node_t *free_list;
    int size;
    int evict_log[16];  /* 记录被淘汰的 key 序列, 供断言 */
    int evict_n;
} lru_t;

static void lru_init(lru_t *c) {
    memset(c, 0, sizeof *c);
    for (int i = 0; i < CAP; i++) {
        c->nodes[i].key = -1;
        c->nodes[i].next = c->free_list;
        c->free_list = &c->nodes[i];
    }
}

static void detach(lru_t *c, node_t *n) {
    if (n->prev) n->prev->next = n->next; else c->head = n->next;
    if (n->next) n->next->prev = n->prev; else c->tail = n->prev;
}
static void push_front(lru_t *c, node_t *n) {
    n->prev = NULL;
    n->next = c->head;
    if (c->head) c->head->prev = n;
    c->head = n;
    if (!c->tail) c->tail = n;
}
static node_t *hfind(lru_t *c, int key) {
    for (node_t *q = c->htab[key % HBITS]; q; q = q->hnext)
        if (q->key == key) return q;
    return NULL;
}
static void hadd(lru_t *c, node_t *n) {
    int b = n->key % HBITS;
    n->hnext = c->htab[b];
    c->htab[b] = n;
}
static void hdel(lru_t *c, node_t *n) {
    int b = n->key % HBITS;
    node_t **pp = &c->htab[b];
    while (*pp && *pp != n) pp = &(*pp)->hnext;
    if (*pp) *pp = n->hnext;
}

/* 命中返回 1 且 *out 有效; 未命中返回 0 */
static int lru_get(lru_t *c, int key, int *out) {
    node_t *n = hfind(c, key);
    if (!n) return 0;
    *out = n->val;
    detach(c, n);
    push_front(c, n);
    return 1;
}

static void lru_put(lru_t *c, int key, int val) {
    node_t *n = hfind(c, key);
    if (n) { /* 覆盖 + 挪头部 */
        n->val = val;
        detach(c, n);
        push_front(c, n);
        return;
    }
    if (c->free_list) {
        n = c->free_list;
        c->free_list = n->next;
        c->size++;
    } else { /* 淘汰尾部（最久未用） */
        n = c->tail;
        if (c->evict_n < 16) c->evict_log[c->evict_n++] = n->key;
        hdel(c, n);
        detach(c, n);
    }
    n->key = key;
    n->val = val;
    hadd(c, n);
    push_front(c, n);
}

int main(void) {
    printf("=== sol-04: LRU Cache（容量 %d） ===\n", CAP);
    lru_t c;
    lru_init(&c);
    int v;

    lru_put(&c, 1, 10);
    lru_put(&c, 2, 20);
    lru_put(&c, 3, 30);           /* 满: [3,2,1]（头→尾） */
    CHECK(c.size == CAP, "容量满, size = 3");

    CHECK(lru_get(&c, 1, &v) == 1 && v == 10, "get(1) = 10（命中, 挪头部）");
    /* 现在 [1,3,2], 2 最久未用 */
    lru_put(&c, 4, 40);           /* 应淘汰 2 */
    CHECK(c.evict_n == 1 && c.evict_log[0] == 2, "put(4) 淘汰最久未用的 2");
    CHECK(lru_get(&c, 2, &v) == 0, "get(2) 未命中（已被淘汰）");

    lru_put(&c, 1, 100);          /* 覆盖 */
    CHECK(lru_get(&c, 1, &v) == 1 && v == 100, "put(1,100) 覆盖生效");
    CHECK(c.size == CAP, "覆盖不增容量, size 仍 = 3");

    /* 顺序推演: get(2) 未命中不改序; put(1,100) 与 get(1) 把 1 挪头
     * → 当前 [1,4,3]（头→尾）, 最久未用的是 3 → put(5) 淘汰 3 */
    lru_put(&c, 5, 50);
    CHECK(c.evict_n == 2 && c.evict_log[1] == 3, "put(5) 淘汰 3（淘汰序列 = 2,3）");
    CHECK(lru_get(&c, 3, &v) == 0, "get(3) 未命中（已被淘汰）");
    CHECK(lru_get(&c, 4, &v) == 1 && v == 40, "get(4) 仍命中 = 40");

    printf("sol-04: %d PASS, %d FAIL, 退出码 %d\n", g_pass, g_fail, g_fail ? 1 : 0);
    return g_fail ? 1 : 0;
}
