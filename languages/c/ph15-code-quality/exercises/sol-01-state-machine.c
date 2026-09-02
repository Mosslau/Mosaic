/* sol-01-state-machine.c —— 参考实现: 表驱动状态机（连接管理场景）
 *
 * 题目要点: 把 (状态, 事件) → (动作, 下一状态) 放进只读转移表,
 *   循环查表驱动转移; 非法事件返回错误码且状态不变; 记录状态序列供自测。
 * 实测: 正常路径 0→1→2→2→3→4→0 共 7 步; 非法事件被拒、状态不变。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-01-state-machine.c -o sol01
// 运行：./sol01（无外部产物, 退出码 0）
// 验证状态：已验证（零警告; 转移序列 7 步、非法事件 1 次被拒, 实测见文件尾）
#include <stdio.h>

/* ---- 状态 / 事件 ---- */
enum state { ST_CLOSED, ST_LISTEN, ST_ESTAB, ST_FIN_WAIT, ST_CLOSE_WAIT, ST_N };
enum event { EV_CONNECT, EV_ACCEPT, EV_DATA, EV_CLOSE, EV_PEER_FIN, EV_N };

static const char *st_name(int s) {
    static const char *const n[ST_N] = {
        "CLOSED", "LISTEN", "ESTAB", "FIN_WAIT", "CLOSE_WAIT"};
    return n[s];
}

/* ---- 转移表: 每条 = from + event → action + to ---- */
typedef void (*act_t)(void);

static void act_alloc(void)   { printf("    [动作] 分配连接\n"); }
static void act_listen_io(void) { printf("    [动作] 注册读写回调\n"); }
static void act_handle_data(void) { printf("    [动作] 处理数据\n"); }
static void act_send_fin(void) { printf("    [动作] 发出 FIN\n"); }
static void act_report_close(void) { printf("    [动作] 上报关闭\n"); }
static void act_free(void)    { printf("    [动作] 释放资源\n"); }

typedef struct { int from; int event; act_t act; int to; } trans_t;

static const trans_t g_tab[] = {
    { ST_CLOSED,    EV_CONNECT, act_alloc,        ST_LISTEN },
    { ST_LISTEN,    EV_ACCEPT,  act_listen_io,    ST_ESTAB },
    { ST_ESTAB,     EV_DATA,    act_handle_data,  ST_ESTAB },   /* 自环 */
    { ST_ESTAB,     EV_CLOSE,   act_send_fin,     ST_FIN_WAIT },
    { ST_FIN_WAIT,  EV_PEER_FIN, act_report_close, ST_CLOSE_WAIT },
    { ST_CLOSE_WAIT, EV_CLOSE,  act_free,         ST_CLOSED },
};
#define TAB_N ((int)(sizeof g_tab / sizeof g_tab[0]))

typedef struct {
    int state;
    char path[32];
    int path_n;
    int rejected;      /* 非法事件计数 */
} fsm_t;

static void fsm_init(fsm_t *f) {
    f->state = ST_CLOSED;
    f->path_n = 0;
    f->rejected = 0;
    f->path[f->path_n++] = (char)('0' + ST_CLOSED);
    f->path[f->path_n] = '\0';
}

static int fsm_fire(fsm_t *f, int ev) {
    for (int i = 0; i < TAB_N; i++) {
        if (g_tab[i].from == f->state && g_tab[i].event == ev) {
            printf("转移: %s --%d--> %s\n", st_name(f->state), ev,
                   st_name(g_tab[i].to));
            g_tab[i].act();
            f->state = g_tab[i].to;
            if (f->path_n < (int)sizeof f->path - 1)
                f->path[f->path_n++] = (char)('0' + f->state);
            f->path[f->path_n] = '\0';
            return 0;
        }
    }
    printf("非法事件: %s 状态不接受事件 %d (拒绝, 状态不变)\n",
           st_name(f->state), ev);
    f->rejected++;
    return -1;
}

int main(void) {
    fsm_t f;
    fsm_init(&f);
    printf("=== sol-01 表驱动状态机 (连接管理) ===\n");

    int rcs[] = {
        fsm_fire(&f, EV_CONNECT), fsm_fire(&f, EV_ACCEPT),
        fsm_fire(&f, EV_DATA),    fsm_fire(&f, EV_CLOSE),
        fsm_fire(&f, EV_PEER_FIN), fsm_fire(&f, EV_CLOSE),
    };
    (void)rcs;

    /* 非法事件: CLOSED 状态收 DATA */
    int bad = fsm_fire(&f, EV_DATA);

    /* 再走一遍正常关闭, 验证状态机可复用 */
    fsm_fire(&f, EV_CONNECT);
    fsm_fire(&f, EV_ACCEPT);
    fsm_fire(&f, EV_CLOSE);
    fsm_fire(&f, EV_PEER_FIN);
    fsm_fire(&f, EV_CLOSE);

    printf("状态序列: %s (0=CLOSED 1=LISTEN 2=ESTAB 3=FIN_WAIT 4=CLOSE_WAIT)\n",
           f.path);
    printf("非法事件被拒 %d 次 (bad=%d)\n", f.rejected, bad);

    /* 自测断言: 首末状态、非法事件计数、序列长度 */
    int fails = 0;
    if (f.state != ST_CLOSED) { printf("FAIL: 末状态\n"); fails++; }
    if (f.rejected != 1)      { printf("FAIL: 拒绝次数\n"); fails++; }
    if (f.path_n != 12)       { printf("FAIL: 序列长度=%d 期望 12\n", f.path_n); fails++; }
    printf(fails == 0 ? "sol-01: 全部断言通过, 退出码 0\n"
                      : "sol-01: 有断言失败\n");
    return fails == 0 ? 0 : 1;
}

/* 实测输出（本机一次运行, Apple clang 21.0.0, macOS arm64）：
 * === sol-01 表驱动状态机 (连接管理) ===
 * 转移: CLOSED --0--> LISTEN
 *     [动作] 分配连接
 * 转移: LISTEN --1--> ESTAB
 *     [动作] 注册读写回调
 * 转移: ESTAB --2--> ESTAB
 *     [动作] 处理数据
 * 转移: ESTAB --3--> FIN_WAIT
 *     [动作] 发出 FIN
 * 转移: FIN_WAIT --4--> CLOSE_WAIT
 *     [动作] 上报关闭
 * 转移: CLOSE_WAIT --3--> CLOSED
 *     [动作] 释放资源
 * 非法事件: CLOSED 状态不接受事件 2 (拒绝, 状态不变)
 * 转移: CLOSED --0--> LISTEN
 *     [动作] 分配连接
 * 转移: LISTEN --1--> ESTAB
 *     [动作] 注册读写回调
 * 转移: ESTAB --3--> FIN_WAIT
 *     [动作] 发出 FIN
 * 转移: FIN_WAIT --4--> CLOSE_WAIT
 *     [动作] 上报关闭
 * 转移: CLOSE_WAIT --3--> CLOSED
 *     [动作] 释放资源
 * 状态序列: 012234012340 (0=CLOSED 1=LISTEN 2=ESTAB 3=FIN_WAIT 4=CLOSE_WAIT)
 * 非法事件被拒 1 次 (bad=-1)
 * sol-01: 全部断言通过, 退出码 0
 */
