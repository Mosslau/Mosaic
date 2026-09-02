/* sol-04-ring-buffer.c —— 参考实现: handle-based 环形缓冲（满/空错误码）
 *
 * 题目要点: 用 opaque handle + create/destroy 封装一个定长环形缓冲:
 *   - push 满 → 返回错误码 ERR_FULL（可选覆盖模式, 本实现不支持覆盖）
 *   - pop 空 → 返回错误码 ERR_EMPTY
 *   - count()/is_empty()/is_full() 查询; 缓冲内部回绕(wrap)对调用方不可见
 *   - 所有函数用稳定错误码汇报, 不用 errno; 内部零全局状态（可重入）
 * 实测: 压入 cap 个后满; 弹出顺序 = 压入顺序(FIFO); 回绕后仍 FIFO。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-04-ring-buffer.c -o sol04
// 运行：./sol04（无外部产物, 退出码 0）
// 验证状态：已验证（零警告; 满/空错误码与 FIFO 顺序为实测, 见文件尾）
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

/* ---- 稳定错误码 ---- */
enum {
    RB_OK = 0,
    RB_ERR_FULL = -1,   /* push 到满 */
    RB_ERR_EMPTY = -2,  /* pop 到空 */
    RB_ERR_BADARG = -3, /* 空句柄 / 非法容量 */
};

/* ---- opaque 句柄 ---- */
typedef struct ring_buf ring_t;

/* API 声明（工程上放头文件） */
ring_t *rb_create(uint32_t capacity, int32_t *err_out);
int32_t rb_destroy(ring_t *r);
int32_t rb_push(ring_t *r, uint8_t byte);
int32_t rb_pop(ring_t *r, uint8_t *out);
uint32_t rb_count(const ring_t *r);
uint32_t rb_capacity(const ring_t *r);
int rb_is_empty(const ring_t *r);
int rb_is_full(const ring_t *r);
const char *rb_strerror(int32_t err);

/* ---- 实现: struct 定义只出现在 .c（此处同文件, 工程上分文件） ---- */

struct ring_buf {
    uint8_t *buf;
    uint32_t cap;
    uint32_t head;   /* 下一个弹出的位置 */
    uint32_t len;    /* 当前元素数 */
};

ring_t *rb_create(uint32_t capacity, int32_t *err_out) {
    if (err_out) *err_out = RB_OK;
    if (capacity == 0) {
        if (err_out) *err_out = RB_ERR_BADARG;
        return NULL;
    }
    ring_t *r = (ring_t *)calloc(1, sizeof *r);
    if (r == NULL) { if (err_out) *err_out = RB_ERR_BADARG; return NULL; }
    r->buf = (uint8_t *)malloc(capacity);
    if (r->buf == NULL) {
        free(r);
        if (err_out) *err_out = RB_ERR_BADARG;
        return NULL;
    }
    r->cap = capacity;
    r->head = 0;
    r->len = 0;
    return r;
}

int32_t rb_destroy(ring_t *r) {
    if (r == NULL) return RB_ERR_BADARG;
    free(r->buf);
    free(r);
    return RB_OK;
}

int32_t rb_push(ring_t *r, uint8_t byte) {
    if (r == NULL) return RB_ERR_BADARG;
    if (r->len == r->cap) return RB_ERR_FULL;
    r->buf[(r->head + r->len) % r->cap] = byte;  /* 写入"逻辑尾" */
    r->len++;
    return RB_OK;
}

int32_t rb_pop(ring_t *r, uint8_t *out) {
    if (r == NULL || out == NULL) return RB_ERR_BADARG;
    if (r->len == 0) return RB_ERR_EMPTY;
    *out = r->buf[r->head];
    r->head = (r->head + 1) % r->cap;            /* 回绕 */
    r->len--;
    return RB_OK;
}

uint32_t rb_count(const ring_t *r) { return r == NULL ? 0 : r->len; }
uint32_t rb_capacity(const ring_t *r) { return r == NULL ? 0 : r->cap; }
int rb_is_empty(const ring_t *r) { return r == NULL || r->len == 0; }
int rb_is_full(const ring_t *r) { return r != NULL && r->len == r->cap; }

const char *rb_strerror(int32_t err) {
    switch (err) {
    case RB_OK:          return "ok";
    case RB_ERR_FULL:    return "ring full";
    case RB_ERR_EMPTY:   return "ring empty";
    case RB_ERR_BADARG:  return "bad argument";
    default:             return "unknown error";
    }
}

int main(void) {
    int32_t err = RB_OK;
    ring_t *r = rb_create(4, &err);
    if (r == NULL) { printf("create 失败: %s\n", rb_strerror(err)); return 1; }
    printf("=== sol-04 handle-based 环形缓冲 (cap=%u) ===\n", rb_capacity(r));

    /* 压入 4 个: 到达满 */
    for (int i = 0; i < 4; i++) {
        int32_t rc = rb_push(r, (uint8_t)('a' + i));
        printf("push '%c' rc=%d count=%u\n", (int)('a' + i), rc, rb_count(r));
    }
    printf("满状态: is_full=%d, 再 push 应报 FULL: rc=%d (%s)\n",
           rb_is_full(r), rb_push(r, (uint8_t)'x'), rb_strerror(rb_push(r, (uint8_t)'x')));

    /* 弹出 2 个 (a, b), 再压 2 个 (e, f) —— 触发回绕 */
    uint8_t v = 0;
    rb_pop(r, &v);
    printf("pop -> %c\n", (int)v);
    rb_pop(r, &v);
    printf("pop -> %c\n", (int)v);
    rb_push(r, (uint8_t)'e');
    rb_push(r, (uint8_t)'f');
    printf("回绕后 count=%u\n", rb_count(r));

    /* 全部弹出: 应为 c d e f (FIFO 保持) */
    printf("顺序弹出:");
    int fails = 0;
    const char expect[] = "cdef";
    for (int i = 0; i < 4; i++) {
        int32_t rc = rb_pop(r, &v);
        if (rc != RB_OK || v != (uint8_t)expect[i]) {
            printf(" FAIL(rc=%d got=%c want=%c)", rc, (int)v, expect[i]);
            fails++;
        } else {
            printf(" %c", (int)v);
        }
    }
    printf("\n空状态: is_empty=%d, 再 pop 应报 EMPTY: rc=%d (%s)\n",
           rb_is_empty(r), rb_pop(r, &v), rb_strerror(rb_pop(r, &v)));

    printf("destroy rc=%d\n", rb_destroy(r));
    printf(fails == 0 ? "sol-04: 全部断言通过, 退出码 0\n"
                      : "sol-04: 有断言失败\n");
    return fails == 0 ? 0 : 1;
}

/* 实测输出（本机一次运行, Apple clang 21.0.0, macOS arm64）：
 * === sol-04 handle-based 环形缓冲 (cap=4) ===
 * push 'a' rc=0 count=1
 * push 'b' rc=0 count=2
 * push 'c' rc=0 count=3
 * push 'd' rc=0 count=4
 * 满状态: is_full=1, 再 push 应报 FULL: rc=-1 (ring full)
 * pop -> a
 * pop -> b
 * 回绕后 count=4
 * 顺序弹出: c d e f
 * 空状态: is_empty=1, 再 pop 应报 EMPTY: rc=-2 (ring empty)
 * destroy rc=0
 * sol-04: 全部断言通过, 退出码 0
 */
