/* fsm.c —— ph15 阶段项目: 通用状态机框架实现
 *
 * 实现要点:
 *   - 转移表在 create 时拷贝进句柄(结构体在 .c 定义, 头文件只见不透明句柄)
 *   - fsm_fire 线性查表(教学规模足够; 大规模可换成按 (from,event) 索引的哈希)
 *   - 轨迹缓冲: 定长数组记录最近 FSM_TRACE_MAX 次转移, 满后返回 FSM_ERR_FULL
 *     但仍执行转移 —— "诊断尽力而为, 语义不因诊断而中断"
 */
#include "fsm.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct fsm {
    fsm_trans_t *table;
    size_t ntrans;
    int state;
    void *ctx;

    /* 轨迹缓冲: ring 语义的定长数组 */
    int trace_from[FSM_TRACE_MAX];
    int trace_event[FSM_TRACE_MAX];
    int trace_to[FSM_TRACE_MAX];
    int trace_count;
};

fsm_t *fsm_new(const fsm_trans_t *table, size_t ntrans, int init_state,
               void *ctx, int *err_out) {
    if (err_out) *err_out = FSM_OK;
    if (table == NULL || ntrans == 0 || init_state < 0) {
        if (err_out) *err_out = FSM_ERR_BADARG;
        return NULL;
    }
    fsm_t *f = (fsm_t *)calloc(1, sizeof *f);
    if (f == NULL) { if (err_out) *err_out = FSM_ERR_NOMEM; return NULL; }
    f->table = (fsm_trans_t *)malloc(ntrans * sizeof *f->table);
    if (f->table == NULL) {
        free(f);
        if (err_out) *err_out = FSM_ERR_NOMEM;
        return NULL;
    }
    memcpy(f->table, table, ntrans * sizeof *f->table);
    f->ntrans = ntrans;
    f->state = init_state;
    f->ctx = ctx;
    f->trace_count = 0;
    return f;
}

void fsm_destroy(fsm_t *f) {
    if (f == NULL) return;
    free(f->table);
    free(f);
}

int fsm_fire(fsm_t *f, int event) {
    if (f == NULL || event < 0)
        return FSM_ERR_BADARG;

    /* 查表: 找到第一条 (当前状态, 事件) 匹配的转移 */
    const fsm_trans_t *hit = NULL;
    for (size_t i = 0; i < f->ntrans; i++) {
        if (f->table[i].from_state == f->state &&
            f->table[i].event == event) {
            hit = &f->table[i];
            break;
        }
    }
    if (hit == NULL)
        return FSM_ERR_ILLEGAL;          /* 当前状态下无此转移 */

    /* 先记录轨迹, 再执行动作、换状态 —— 动作里可安全查询 fsm_state */
    if (f->trace_count < FSM_TRACE_MAX) {
        int i = f->trace_count;
        f->trace_from[i] = f->state;
        f->trace_event[i] = event;
        f->trace_to[i] = hit->to_state;
        f->trace_count++;
    } else {
        /* 轨迹满: 返回提示, 但转移照常执行(见头文件注释) */
        /* 注: 为教学清晰, 满时先执行动作再返回 FULL */
    }

    int from = f->state;
    if (hit->action != NULL)
        hit->action(f->ctx, from, event, hit->to_state);
    f->state = hit->to_state;

    if (f->trace_count >= FSM_TRACE_MAX)
        return FSM_ERR_FULL;
    return f->state;
}

int fsm_state(const fsm_t *f) { return f == NULL ? FSM_ERR_BADARG : f->state; }

int fsm_trace_len(const fsm_t *f) {
    return f == NULL ? 0 : f->trace_count;
}

int fsm_trace(const fsm_t *f, int i, int *from, int *event, int *to) {
    if (f == NULL || i < 0 || i >= f->trace_count ||
        from == NULL || event == NULL || to == NULL)
        return 0;
    *from = f->trace_from[i];
    *event = f->trace_event[i];
    *to = f->trace_to[i];
    return 1;
}

const char *fsm_strerror(int err) {
    switch (err) {
    case FSM_OK:          return "ok";
    case FSM_ERR_BADARG:  return "bad argument";
    case FSM_ERR_ILLEGAL: return "illegal event for current state";
    case FSM_ERR_NOMEM:   return "out of memory";
    case FSM_ERR_FULL:    return "trace buffer full";
    default:              return "unknown error";
    }
}
