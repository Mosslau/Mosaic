/* fsm.h —— ph15 阶段项目: 通用状态机框架（表驱动）
 *
 * 一个可复用的表驱动 FSM 框架:
 *   - 转移表: 只读数组, 每行 (from, event, action, to)
 *   - 动作 action 是函数指针, 收 (ctx, from, event, to)
 *   - 错误码: 0 成功 / 负数错误(坏参数/非法事件/内存不足)
 *   - 诊断: 每次转移记录到内部轨迹缓冲, fsm_trace 可读出(可测试的 API)
 *
 * 设计原则(ph15): 零全局状态(状态机状态全在句柄内, 可同时开多个实例)、
 *   稳定错误码不用 errno、opaque 句柄隐藏实现、API 可测试。
 */
#ifndef FSM_H
#define FSM_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* 错误码(0 成功/负数错误; 数值稳定, 发布后不改) */
enum {
    FSM_OK = 0,
    FSM_ERR_BADARG = -1,     /* 空句柄 / 空表 / 初始状态越界 */
    FSM_ERR_ILLEGAL = -2,    /* 当前状态下无该事件的转移 */
    FSM_ERR_NOMEM = -3,      /* 内部分配失败 */
};

#define FSM_TRACE_MAX 64     /* 轨迹缓冲容量: 满后停止记录(不影响转移与返回值) */

/* 动作回调: 转移发生时调用。ctx 由状态机使用者提供并负责生命周期。 */
typedef void (*fsm_action_fn)(void *ctx, int from_state, int event, int to_state);

typedef struct {
    int from_state;
    int event;
    fsm_action_fn action;   /* 可为 NULL(无动作) */
    int to_state;
} fsm_trans_t;

typedef struct fsm fsm_t;

/* create: 表指针 + 表长 + 初始状态。句柄自包含(拷贝表), 可同时开多个实例 */
fsm_t *fsm_new(const fsm_trans_t *table, size_t ntrans, int init_state,
               void *ctx, int *err_out);

void fsm_destroy(fsm_t *f);

/* 喂事件; 返回新状态(>=0) 或负数错误码。合法转移执行动作、换状态并记录轨迹
 * (轨迹满后不再记录, fsm_trace_len 封顶 FSM_TRACE_MAX 可检测, 返回值不变) */
int fsm_fire(fsm_t *f, int event);

int fsm_state(const fsm_t *f);          /* 当前状态 */
int fsm_trace_len(const fsm_t *f);      /* 已记录转移数 */
/* 读第 i 条轨迹(0 = 最早); 越界返回 0 */
int fsm_trace(const fsm_t *f, int i, int *from, int *event, int *to);

const char *fsm_strerror(int err);

#ifdef __cplusplus
}
#endif

#endif /* FSM_H */
