/* main.c —— ph15 阶段项目: 通用状态机框架 演示 + 自测
 *
 * 两个场景验证框架"可复用":
 *   场景 A: 连接管理状态机(CLOSED→LISTEN→ESTAB→...), 动作打印到 stdout
 *   场景 B: 迷你"数据包解析"状态机(IDLE→GOT_HEADER→DONE), 只用框架的
 *           状态转移与轨迹, 不带动作 —— 证明动作可缺省(NULL)
 * 自测: 用 fsm_trace 读回轨迹, 断言两次演示的完整转移序列与错误路径。
 */
#include <stdio.h>

#include "fsm.h"

/* ---------- 场景 A: 连接管理状态机 ---------- */

enum conn_state { C_CLOSED, C_LISTEN, C_ESTAB, C_FIN_WAIT, C_CLOSED_WAIT };
enum conn_ev { C_CONNECT, C_ACCEPT, C_DATA, C_CLOSE, C_PEER_FIN };

static void act_alloc(void *ctx, int from, int ev, int to) {
    (void)ctx; (void)from; (void)ev; (void)to;
    printf("    [动作] 分配连接\n");
}
static void act_listen(void *ctx, int from, int ev, int to) {
    (void)ctx; (void)from; (void)ev; (void)to;
    printf("    [动作] 注册 IO 回调\n");
}
static void act_data(void *ctx, int from, int ev, int to) {
    (void)ctx; (void)from; (void)ev; (void)to;
    printf("    [动作] 处理数据\n");
}
static void act_fin(void *ctx, int from, int ev, int to) {
    (void)ctx; (void)from; (void)ev; (void)to;
    printf("    [动作] 发 FIN\n");
}
static void act_close(void *ctx, int from, int ev, int to) {
    (void)ctx; (void)from; (void)ev; (void)to;
    printf("    [动作] 通知应用层关闭\n");
}
static void act_free(void *ctx, int from, int ev, int to) {
    (void)ctx; (void)from; (void)ev; (void)to;
    printf("    [动作] 释放资源\n");
}

static const fsm_trans_t g_conn_tab[] = {
    { C_CLOSED,       C_CONNECT,   act_alloc, C_LISTEN },
    { C_LISTEN,       C_ACCEPT,    act_listen, C_ESTAB },
    { C_ESTAB,        C_DATA,      act_data,  C_ESTAB },   /* 自环 */
    { C_ESTAB,        C_CLOSE,     act_fin,   C_FIN_WAIT },
    { C_FIN_WAIT,     C_PEER_FIN,  act_close, C_CLOSED_WAIT },
    { C_CLOSED_WAIT,  C_CLOSE,     act_free,  C_CLOSED },
};

/* ---------- 场景 B: 数据包解析状态机(无动作) ---------- */

enum pkt_state { P_IDLE, P_GOT_LEN, P_DONE };
enum pkt_ev { P_EV_HEADER, P_EV_PAYLOAD };

static const fsm_trans_t g_pkt_tab[] = {
    { P_IDLE, P_EV_HEADER,  NULL, P_GOT_LEN },
    { P_GOT_LEN, P_EV_PAYLOAD, NULL, P_DONE },
};

/* ---------- 自测 ---------- */

static int g_fails = 0;
#define CHECK(cond, msg)                                        \
    do {                                                        \
        if (cond)                                               \
            printf("PASS: %s\n", msg);                          \
        else {                                                  \
            printf("FAIL: %s\n", msg);                          \
            g_fails++;                                          \
        }                                                       \
    } while (0)

static void test_conn(void) {
    printf("场景 A: 连接状态机\n");
    int err = FSM_OK;
    fsm_t *f = fsm_new(g_conn_tab,
                       (size_t)(sizeof g_conn_tab / sizeof g_conn_tab[0]),
                       C_CLOSED, NULL, &err);
    CHECK(f != NULL && err == FSM_OK, "A: 创建成功");

    if (f == NULL) return;
    /* 合法路径 */
    int s = fsm_fire(f, C_CONNECT);
    CHECK(s == C_LISTEN, "A: CONNECT → LISTEN");
    s = fsm_fire(f, C_ACCEPT);
    CHECK(s == C_ESTAB, "A: ACCEPT → ESTAB");
    s = fsm_fire(f, C_DATA);
    CHECK(s == C_ESTAB, "A: DATA 自环保持 ESTAB");
    s = fsm_fire(f, C_CLOSE);
    CHECK(s == C_FIN_WAIT, "A: CLOSE → FIN_WAIT");
    s = fsm_fire(f, C_PEER_FIN);
    CHECK(s == C_CLOSED_WAIT, "A: PEER_FIN → CLOSED_WAIT");
    s = fsm_fire(f, C_CLOSE);
    CHECK(s == C_CLOSED, "A: CLOSE → CLOSED");
    CHECK(fsm_state(f) == C_CLOSED, "A: 末状态 CLOSED");

    /* 非法事件: CLOSED 下收 DATA 应返回错误码且状态不变 */
    err = fsm_fire(f, C_DATA);
    CHECK(err == FSM_ERR_ILLEGAL, "A: CLOSED 下 DATA 被拒(FSM_ERR_ILLEGAL)");
    CHECK(fsm_state(f) == C_CLOSED, "A: 被拒后状态不变");

    /* 轨迹自测: 6 次合法转移 + 1 次被拒(不计入轨迹) = 6 条 */
    CHECK(fsm_trace_len(f) == 6, "A: 轨迹共 6 条(非法事件不计入)");
    int from = -1, ev = -1, to = -1;
    fsm_trace(f, 0, &from, &ev, &to);
    CHECK(from == C_CLOSED && ev == C_CONNECT && to == C_LISTEN,
          "A: 轨迹[0] = CLOSED--CONNECT-->LISTEN");

    fsm_destroy(f);
}

static void test_pkt(void) {
    printf("场景 B: 数据包解析状态机(动作缺省)\n");
    int err = FSM_OK;
    fsm_t *f = fsm_new(g_pkt_tab,
                       (size_t)(sizeof g_pkt_tab / sizeof g_pkt_tab[0]),
                       P_IDLE, NULL, &err);
    CHECK(f != NULL, "B: 创建成功(动作全 NULL 也合法)");
    if (f == NULL) return;

    int s = fsm_fire(f, P_EV_HEADER);
    CHECK(s == P_GOT_LEN, "B: HEADER → GOT_LEN");
    s = fsm_fire(f, P_EV_PAYLOAD);
    CHECK(s == P_DONE, "B: PAYLOAD → DONE");
    CHECK(fsm_trace_len(f) == 2, "B: 轨迹 2 条");

    /* 错误路径: DONE 后再收 HEADER */
    s = fsm_fire(f, P_EV_HEADER);
    CHECK(s == FSM_ERR_ILLEGAL, "B: DONE 后 HEADER 被拒");

    fsm_destroy(f);
}

static void test_badarg(void) {
    printf("错误路径: 坏参数\n");
    int err = FSM_OK;
    fsm_t *f = fsm_new(g_conn_tab,
                       (size_t)(sizeof g_conn_tab / sizeof g_conn_tab[0]),
                       C_CLOSED, NULL, &err);
    CHECK(f != NULL, "badarg: 正常创建对照组");
    if (f != NULL) {
        CHECK(fsm_fire(NULL, C_DATA) == FSM_ERR_BADARG, "badarg: 空句柄 fire");
        fsm_destroy(f);
    }
    f = fsm_new(NULL, 3, 0, NULL, &err);
    CHECK(f == NULL && err == FSM_ERR_BADARG, "badarg: 空表被拒");
}

int main(void) {
    printf("=== ph15 project: 通用状态机框架 ===\n");
    test_conn();
    test_pkt();
    test_badarg();

    if (g_fails == 0)
        printf("project: 全部断言通过, 退出码 0\n");
    else
        printf("project: %d 个断言失败\n", g_fails);
    return g_fails == 0 ? 0 : 1;
}
