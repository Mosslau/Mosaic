/* sol-02-event-framework.c —— 参考实现: 事件驱动框架（注册 → 按序分发）
 *
 * 题目要点: 事件 = 数字编号; 处理器 = (事件, ctx) 回调。框架支持:
 *   注册（尾部追加, 保持注册顺序）、按序分发（同一事件按注册顺序回调）、
 *   注销（移除指定回调, 验证不再被调用）。核心验证 = 回调顺序实测。
 * 生命周期约定: ctx 由注册方负责; 分发期间不得注销（简化版, 见主文档 3.4）。
 * 实测: A/B/C 注册顺序 0/1/2 → 分发顺序 A,B,C; 注销 B 后只剩 A,C;
 *       再注册 D 后分发顺序 A,C,D; B 的计数在注销后不再增加。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-02-event-framework.c -o sol02
// 运行：./sol02（无外部产物, 退出码 0）
// 验证状态：已验证（零警告; 分发顺序/注销行为为实测, 见文件尾）
#include <stdio.h>

#define MAX_HANDLERS 8

typedef void (*handler_fn)(int ev, void *ctx);

typedef struct {
    handler_fn fn;
    void *ctx;
    char tag[8];
} slot_t;

static slot_t g_slots[MAX_HANDLERS];
static int g_nslots = 0;
static int g_order[MAX_HANDLERS];   /* 最近一次分发中被调用的槽位序, 供自测 */
static int g_norder = 0;

/* 注册: 返回槽位号(>=0) 或 -1(满) */
static int ev_register(const char *tag, handler_fn fn, void *ctx) {
    if (g_nslots >= MAX_HANDLERS)
        return -1;
    slot_t *s = &g_slots[g_nslots];
    snprintf(s->tag, sizeof s->tag, "%s", tag);
    s->fn = fn;
    s->ctx = ctx;
    return g_nslots++;      /* 槽位号 = 注册顺序 */
}

/* 注销: 按槽位号移除, 后续槽位前移（其余注册相对顺序不变） */
static int ev_unregister(int seq) {
    if (seq < 0 || seq >= g_nslots)
        return -1;
    for (int i = seq; i < g_nslots - 1; i++)
        g_slots[i] = g_slots[i + 1];
    g_nslots--;
    return 0;
}

/* 分发: 按注册顺序依次回调 */
static void ev_dispatch(int ev) {
    g_norder = 0;
    for (int i = 0; i < g_nslots; i++) {
        g_slots[i].fn(ev, g_slots[i].ctx);
        if (g_norder < MAX_HANDLERS)
            g_order[g_norder++] = i;
    }
}

/* ---- 处理器 ---- */

struct counter { const char *who; int n; };

static void h_count(int ev, void *ctx) {
    (void)ev;
    struct counter *c = (struct counter *)ctx;
    c->n++;
    printf("  [%s] 被回调, 累计 %d\n", c->who, c->n);
}

static void print_order(const char *label) {
    printf("  分发顺序: ");
    for (int i = 0; i < g_norder; i++)
        printf("%s ", g_slots[g_order[i]].tag);
    printf("(%s)\n", label);
}

int main(void) {
    struct counter ca = {"A", 0}, cb = {"B", 0}, cc = {"C", 0}, cd = {"D", 0};

    printf("=== sol-02 事件驱动框架 ===\n");

    int sa = ev_register("A", h_count, &ca);
    int sb = ev_register("B", h_count, &cb);
    int sc = ev_register("C", h_count, &cc);
    printf("注册: A@%d B@%d C@%d\n", sa, sb, sc);

    printf("分发 #1 (A,B,C 全在):\n");
    ev_dispatch(1);
    print_order("期望 A B C");

    printf("注销 B@%d, rc=%d:\n", sb, ev_unregister(sb));
    printf("分发 #2 (只剩 A,C):\n");
    ev_dispatch(2);
    print_order("期望 A C");

    int sd = ev_register("D", h_count, &cd);
    printf("再注册 D@%d (槽位前移后 D 排最后):\n", sd);
    printf("分发 #3 (A,C,D):\n");
    ev_dispatch(3);
    print_order("期望 A C D");

    /* 自测断言 */
    int fails = 0;
    if (ca.n != 3) { printf("FAIL: A 被回调 %d 次(期望 3)\n", ca.n); fails++; }
    if (cb.n != 1) { printf("FAIL: B 被回调 %d 次(期望 1, 注销后不再被调)\n", cb.n); fails++; }
    if (cc.n != 3) { printf("FAIL: C 被回调 %d 次(期望 3)\n", cc.n); fails++; }
    if (cd.n != 1) { printf("FAIL: D 被回调 %d 次(期望 1)\n", cd.n); fails++; }

    printf(fails == 0 ? "sol-02: 全部断言通过, 退出码 0\n"
                      : "sol-02: 有断言失败\n");
    return fails == 0 ? 0 : 1;
}

/* 实测输出（本机一次运行, Apple clang 21.0.0, macOS arm64）：
 * === sol-02 事件驱动框架 ===
 * 注册: A@0 B@1 C@2
 * 分发 #1 (A,B,C 全在):
 *   [A] 被回调, 累计 1
 *   [B] 被回调, 累计 1
 *   [C] 被回调, 累计 1
 *   分发顺序: A B C (期望 A B C)
 * 注销 B@1, rc=0:
 * 分发 #2 (只剩 A,C):
 *   [A] 被回调, 累计 2
 *   [C] 被回调, 累计 2
 *   分发顺序: A C (期望 A C)
 * 再注册 D@2 (槽位前移后 D 排最后):
 * 分发 #3 (A,C,D):
 *   [A] 被回调, 累计 3
 *   [C] 被回调, 累计 3
 *   [D] 被回调, 累计 1
 *   分发顺序: A C D (期望 A C D)
 * sol-02: 全部断言通过, 退出码 0
 */
