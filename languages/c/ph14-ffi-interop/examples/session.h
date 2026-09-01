/* session.h —— opaque pointer 句柄库（create/destroy + 错误码/错误消息）
 *
 * 本库示范跨语言接口的三种关键约定（roadmap §14 必会概念）：
 *   - opaque pointer：typedef struct session session_t；结构体定义藏在
 *     session.c 里，调用方（任何语言）只持有指针，永远不拆解内部布局
 *   - create/destroy API："谁 create 谁 destroy"，内存所有权在 C 侧闭环
 *   - 错误码与错误消息：0 成功、负数错误；错误消息经 session_strerror
 *     读取（静态字符串，借用），不依赖 errno（errno 是 C 的线程局部
 *     全局，ctypes / Rust FFI 读取麻烦且不可移植）
 */
#ifndef SESSION_H
#define SESSION_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct session session_t;   /* opaque：具体定义只在 session.c */

/* 错误码（数值一经发布不再改，Python/Rust 按同一数值判断） */
enum {
    SESSION_OK = 0,
    SESSION_ERR_BADARG = -1,   /* 参数非法（如 name 为空） */
    SESSION_ERR_NOMEM = -2,    /* 内存不足 */
};

/* create：分配并初始化句柄；失败返回 NULL 且 *err_out 写入错误码 */
session_t *session_create(const char *name, int *err_out);

/* 借用内部字符串（name 的拷贝，由 C 侧持有）；调用方不得 free 返回值 */
const char *session_name(const session_t *s);

/* 向会话累加一个值；失败返回错误码（负数） */
int session_add(session_t *s, int32_t v);

/* 当前累计值 */
int64_t session_total(const session_t *s);

/* destroy：释放句柄（谁 create 谁 destroy）；返回 SESSION_OK */
int session_destroy(session_t *s);

/* 错误消息：静态字符串，借用（无需释放） */
const char *session_strerror(int err);

#ifdef __cplusplus
}
#endif

#endif /* SESSION_H */
