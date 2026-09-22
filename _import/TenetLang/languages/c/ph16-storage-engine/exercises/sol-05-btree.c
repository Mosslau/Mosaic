/* sol-05-btree.c —— 参考实现: 简化 B+Tree（内存版, 阶 4, 插入/查找/范围扫描）
 *
 * 题目要点:
 *   - B+Tree 与 B-Tree 的差别: 数据全在叶子, 叶子间链表串联（范围扫描友好）
 *   - 阶 4: 每节点最多 3 个 key; 插入溢出即分裂, 中位 key 上提（叶子是上提副本）
 *   - 查找 = 从根沿内部节点下行到叶子; 范围扫描 = 定位起点叶 + 沿链表推进
 * 自测断言: 乱序插入 1..20 全部可查且值正确; 范围扫描 [5,12] 输出升序;
 *           不存在的 key 查不到; 20 个 key 下树高 ≤ 3。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：mkdir -p /tmp/ph16c-sol && cc -Wall -Wextra -std=c11 sol-05-btree.c -o /tmp/ph16c-sol/sol05
// 运行：/tmp/ph16c-sol/sol05（无外部产物, 退出码 0）
// 验证状态：已验证（零警告; 查找/扫描/树高断言全 PASS）
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ORDER 4
#define MAXK (ORDER - 1) /* 每节点最多 3 个 key */

static int g_pass = 0, g_fail = 0;
#define CHECK(cond, name) do { \
    if (cond) { g_pass++; printf("PASS: %s\n", name); } \
    else { g_fail++; printf("FAIL: %s\n", name); } \
} while (0)

typedef struct bpnode {
    int is_leaf;
    int n;                 /* 当前 key 数 */
    int keys[ORDER];       /* 分裂瞬间可临时到 ORDER 个 */
    union {
        struct { struct bpnode *child[ORDER + 1]; } in;
        struct { int val[ORDER]; struct bpnode *next; } leaf;
    } u;
} bpnode_t;

static bpnode_t *node_new(int is_leaf) {
    bpnode_t *p = calloc(1, sizeof *p);
    p->is_leaf = is_leaf;
    return p;
}

/* 叶子查找: 命中返回下标; 未命中返回 -1 */
static int leaf_find(bpnode_t *leaf, int key) {
    for (int i = 0; i < leaf->n; i++)
        if (leaf->keys[i] == key) return i;
    return -1;
}

/* 内部节点选路: 返回应进入的孩子下标 */
static int child_idx(bpnode_t *in, int key) {
    int i = 0;
    while (i < in->n && key >= in->keys[i]) i++;
    return i;
}

/* 查找: 命中返回 1 且 *out 有效 */
static int bp_get(bpnode_t *root, int key, int *out) {
    bpnode_t *p = root;
    while (p && !p->is_leaf) p = p->u.in.child[child_idx(p, key)];
    if (!p) return 0;
    int i = leaf_find(p, key);
    if (i < 0) return 0;
    *out = p->u.leaf.val[i];
    return 1;
}

/* 递归插入; 若本节点分裂返回 1, *up_key 为上提 key, *right 为新右兄弟 */
static int insert_rec(bpnode_t *p, int key, int val, int *up_key, bpnode_t **right) {
    if (p->is_leaf) {
        int i = 0;
        while (i < p->n && p->keys[i] < key) i++;
        /* 简化: 重复 key 直接覆盖 */
        if (i < p->n && p->keys[i] == key) { p->u.leaf.val[i] = val; return 0; }
        memmove(&p->keys[i + 1], &p->keys[i], (size_t)(p->n - i) * sizeof(int));
        memmove(&p->u.leaf.val[i + 1], &p->u.leaf.val[i], (size_t)(p->n - i) * sizeof(int));
        p->keys[i] = key;
        p->u.leaf.val[i] = val;
        p->n++;
        if (p->n < ORDER) return 0; /* 未溢出 */
        /* 叶子分裂: 4 个 key → 左 2 右 2, 上提右兄弟首 key 的副本 */
        bpnode_t *r = node_new(1);
        r->n = 2;
        r->keys[0] = p->keys[2]; r->keys[1] = p->keys[3];
        r->u.leaf.val[0] = p->u.leaf.val[2]; r->u.leaf.val[1] = p->u.leaf.val[3];
        r->u.leaf.next = p->u.leaf.next;
        p->u.leaf.next = r;
        p->n = 2;
        *up_key = r->keys[0];
        *right = r;
        return 1;
    }
    /* 内部节点: 下行, 孩子分裂则插入上提 key 与右孩子 */
    int ci = child_idx(p, key);
    int child_up = 0;
    bpnode_t *child_right = NULL;
    if (!insert_rec(p->u.in.child[ci], key, val, &child_up, &child_right)) return 0;
    memmove(&p->keys[ci + 1], &p->keys[ci], (size_t)(p->n - ci) * sizeof(int));
    memmove(&p->u.in.child[ci + 2], &p->u.in.child[ci + 1],
            (size_t)(p->n - ci) * sizeof(bpnode_t *));
    p->keys[ci] = child_up;
    p->u.in.child[ci + 1] = child_right;
    p->n++;
    if (p->n < ORDER) return 0;
    /* 内部分裂: 4 个 key → 左 2, 中位上提(不保留), 右 1 */
    bpnode_t *r = node_new(0);
    r->n = 1;
    r->keys[0] = p->keys[3];
    r->u.in.child[0] = p->u.in.child[3];
    r->u.in.child[1] = p->u.in.child[4];
    *up_key = p->keys[2];
    *right = r;
    p->n = 2;
    return 1;
}

static void bp_put(bpnode_t **root, int key, int val) {
    int up_key = 0;
    bpnode_t *right = NULL;
    if (insert_rec(*root, key, val, &up_key, &right)) {
        /* 根分裂: 新建根 */
        bpnode_t *nr = node_new(0);
        nr->n = 1;
        nr->keys[0] = up_key;
        nr->u.in.child[0] = *root;
        nr->u.in.child[1] = right;
        *root = nr;
    }
}

/* 范围扫描 [lo, hi]: 定位起点叶后沿链表推进; 返回收集个数 */
static int bp_scan(bpnode_t *root, int lo, int hi, int *out, int cap) {
    bpnode_t *p = root;
    while (p && !p->is_leaf) p = p->u.in.child[child_idx(p, lo)];
    int cnt = 0;
    while (p && cnt < cap) {
        for (int i = 0; i < p->n; i++) {
            if (p->keys[i] < lo) continue;
            if (p->keys[i] > hi) return cnt;
            out[cnt++] = p->keys[i];
        }
        p = p->u.leaf.next;
    }
    return cnt;
}

static int tree_height(bpnode_t *p) {
    int h = 1;
    while (p && !p->is_leaf) { p = p->u.in.child[0]; h++; }
    return h;
}

static void node_free(bpnode_t *p) {
    if (!p) return;
    if (!p->is_leaf)
        for (int i = 0; i <= p->n; i++) node_free(p->u.in.child[i]);
    free(p);
}

int main(void) {
    printf("=== sol-05: 简化 B+Tree（阶 %d） ===\n", ORDER);
    bpnode_t *root = node_new(1);

    /* 乱序插入 1..20（固定置换, 可复现） */
    static const int perm[20] = { 11, 3, 17, 8, 20, 1, 14, 6, 19, 9,
                                  2, 16, 12, 5, 18, 7, 13, 4, 15, 10 };
    for (int i = 0; i < 20; i++) bp_put(&root, perm[i], perm[i] * 10);
    CHECK(tree_height(root) <= 3, "20 个 key 树高 ≤ 3（阶 4 下 log 增长）");

    int v = 0, ok = 1;
    for (int k = 1; k <= 20; k++)
        if (!(bp_get(root, k, &v) && v == k * 10)) ok = 0;
    CHECK(ok, "乱序插入后 1..20 全部可查且值 = key*10");

    CHECK(!bp_get(root, 0, &v) && !bp_get(root, 21, &v) && !bp_get(root, 99, &v),
          "不存在的 key (0/21/99) 查不到");

    int out[16];
    int cnt = bp_scan(root, 5, 12, out, 16);
    ok = (cnt == 8);
    for (int i = 0; ok && i < 8; i++)
        if (out[i] != 5 + i) ok = 0;
    CHECK(ok, "范围扫描 [5,12] 输出 8 个且严格升序");
    printf("    扫描结果:");
    for (int i = 0; i < cnt; i++) printf(" %d", out[i]);
    printf("\n");

    /* 重复 key 覆盖 */
    bp_put(&root, 7, 777);
    CHECK(bp_get(root, 7, &v) && v == 777, "重复 key 覆盖生效");

    node_free(root);
    printf("sol-05: %d PASS, %d FAIL, 退出码 %d\n", g_pass, g_fail, g_fail ? 1 : 0);
    return g_fail ? 1 : 0;
}
