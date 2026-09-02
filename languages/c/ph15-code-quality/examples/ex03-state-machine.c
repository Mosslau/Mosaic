// examples/ex03-state-machine.c —— 表驱动状态机：状态转移序列实测（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
// 编译：cc -Wall -Wextra -std=c11 ex03-state-machine.c -o ex03
// 运行：./ex03（无外部产物，退出码 0；实测输出见文件尾注释）
#include <stdio.h>

/* ---- 状态与事件 ---- */
enum state {
    ST_CLOSED,      /* 初始 */
    ST_LISTEN,
    ST_ESTABLISHED,
    ST_FIN_WAIT,
    ST_CLOSED_WAIT,
    ST_COUNT
};

enum event {
    EV_CONNECT,     /* 应用层请求建立连接 */
    EV_ACCEPT,      /* 对端接受 */
    EV_DATA,        /* 收到数据 */
    EV_CLOSE,       /* 应用层请求关闭 */
    EV_PEER_FIN,    /* 对端发起关闭 */
    EV_TIMEOUT,
    EV_COUNT
};

/* ---- 动作（函数指针, 打印做了什么） ---- */
typedef void (*action_fn)(void);

static void act_noop(void)          { printf("    [动作] (无)\n"); }
static void act_alloc_conn(void)    { printf("    [动作] 分配连接\n"); }
static void act_start_read(void)    { printf("    [动作] 开始监听读事件\n"); }
static void act_read_buf(void)      { printf("    [动作] 读取并处理数据\n"); }
static void act_flush_close(void)   { printf("    [动作] 刷缓冲并发出 FIN\n"); }
static void act_notify_app(void)    { printf("    [动作] 通知应用层连接已关闭\n"); }
static void act_free_conn(void)     { printf("    [动作] 释放连接资源\n"); }

/* ---- 转移表：一行 = 一条合法转移 ---- */
typedef struct {
    int from;
    int event;
    action_fn action;
    int to;
} transition_t;

static const transition_t g_trans[] = {
    { ST_CLOSED,      EV_CONNECT,   act_alloc_conn,   ST_LISTEN },
    { ST_LISTEN,      EV_ACCEPT,    act_start_read,   ST_ESTABLISHED },
    { ST_ESTABLISHED, EV_DATA,      act_read_buf,     ST_ESTABLISHED },
    { ST_ESTABLISHED, EV_CLOSE,     act_flush_close,  ST_FIN_WAIT },
    { ST_FIN_WAIT,    EV_PEER_FIN,  act_notify_app,   ST_CLOSED_WAIT },
    { ST_CLOSED_WAIT, EV_CLOSE,     act_free_conn,    ST_CLOSED },
    /* 超时兜底：LISTEN/ESTABLISHED 下超时回初始, 并打印动作 */
    { ST_LISTEN,      EV_TIMEOUT,   act_noop,         ST_CLOSED },
    { ST_ESTABLISHED, EV_TIMEOUT,   act_free_conn,    ST_CLOSED },
};

static const int g_trans_n = (int)(sizeof g_trans / sizeof g_trans[0]);

/* ---- 状态机对象（handle 风格, 简单版） ---- */
typedef struct {
    int state;
    char path[64];        /* 走过的状态序列, 用于自测 */
    int path_len;
} fsm_t;

static const char *state_name(int s) {
    static const char *const names[ST_COUNT] = {
        "CLOSED", "LISTEN", "ESTABLISHED", "FIN_WAIT", "CLOSED_WAIT"
    };
    return names[s];
}

static const char *event_name(int e);   /* 前向声明（定义在下方） */

static void fsm_reset(fsm_t *f) {
    f->state = ST_CLOSED;
    f->path_len = 0;
}

static void path_append(fsm_t *f, int s) {
    if (f->path_len < (int)sizeof f->path - 1)
        f->path[f->path_len++] = (char)('0' + s);   /* 用单字符记录状态号 */
    f->path[f->path_len] = '\0';
}

/* 喂一个事件；合法转移执行动作并换状态（返回 0），非法事件返回 -1 状态不变 */
static int fsm_fire(fsm_t *f, int ev) {
    for (int i = 0; i < g_trans_n; i++) {
        if (g_trans[i].from == f->state && g_trans[i].event == ev) {
            int from = f->state;
            int to = g_trans[i].to;
            printf("转移: %s --%s--> %s\n",
                   state_name(from), event_name(ev), state_name(to));
            g_trans[i].action();
            f->state = to;
            path_append(f, to);
            return 0;
        }
    }
    printf("非法事件: %s 状态下不能处理 %s (返回 -1, 状态不变)\n",
           state_name(f->state), event_name(ev));
    return -1;
}

static const char *event_name(int e) {
    static const char *const names[EV_COUNT] = {
        "CONNECT", "ACCEPT", "DATA", "CLOSE", "PEER_FIN", "TIMEOUT"
    };
    return names[e];
}

int main(void) {
    fsm_t f;
    fsm_reset(&f);
    path_append(&f, ST_CLOSED);

    printf("=== ex03 表驱动状态机 ===\n");
    printf("转移表共 %d 条 (from, event) → (action, to)\n\n", g_trans_n);

    /* 正常路径：连接 → 收发 → 关闭（每步打印"转移 + 动作"） */
    fsm_fire(&f, EV_CONNECT);
    fsm_fire(&f, EV_ACCEPT);
    fsm_fire(&f, EV_DATA);        /* 自环转移: ESTABLISHED --DATA--> ESTABLISHED */
    fsm_fire(&f, EV_CLOSE);
    fsm_fire(&f, EV_PEER_FIN);
    fsm_fire(&f, EV_CLOSE);

    /* 非法事件：已关闭状态下发数据 → 应报错且状态不变 */
    printf("\n非法转移演示: 在 %s 状态发 EV_DATA\n", state_name(f.state));
    int rc = fsm_fire(&f, EV_DATA);
    printf("  返回码 = %d, 状态仍是 %s\n", rc, state_name(f.state));

    /* 自测：走过的状态序列 = 0(CLOSED)→1(LISTEN)→2(ESTABLISHED)→2→3(FIN_WAIT)
     * →4(CLOSED_WAIT)→0(CLOSED) */
    printf("\n走过的状态序列: %s (用状态号 0~4 表示)\n", f.path);
    printf("自测: 序列长度=%d (期望 7: 0→1→2→2→3→4→0)\n", f.path_len);

    return 0;
}

/* 实测输出（本机一次运行, Apple clang 21.0.0, macOS arm64）：
 * === ex03 表驱动状态机 ===
 * 转移表共 8 条 (from, event) → (action, to)
 * 
 * 转移: CLOSED --CONNECT--> LISTEN
 *     [动作] 分配连接
 * 转移: LISTEN --ACCEPT--> ESTABLISHED
 *     [动作] 开始监听读事件
 * 转移: ESTABLISHED --DATA--> ESTABLISHED
 *     [动作] 读取并处理数据
 * 转移: ESTABLISHED --CLOSE--> FIN_WAIT
 *     [动作] 刷缓冲并发出 FIN
 * 转移: FIN_WAIT --PEER_FIN--> CLOSED_WAIT
 *     [动作] 通知应用层连接已关闭
 * 转移: CLOSED_WAIT --CLOSE--> CLOSED
 *     [动作] 释放连接资源
 * 
 * 非法转移演示: 在 CLOSED 状态发 EV_DATA
 * 非法事件: CLOSED 状态下不能处理 DATA (返回 -1, 状态不变)
 *   返回码 = -1, 状态仍是 CLOSED
 * 
 * 走过的状态序列: 0122340 (用状态号 0~4 表示)
 * 自测: 序列长度=7 (期望 7: 0→1→2→2→3→4→0)
 */
