/* session.c —— opaque 句柄实现（结构体定义只在这里，对外不可见）
 *
 * 编译（macOS）：
 *   cc -Wall -Wextra -std=c11 -dynamiclib session.c -o /tmp/ph14-ex/libsession.dylib
 */
#include "session.h"

#include <stdlib.h>
#include <string.h>

struct session {              /* 内部布局：只有 session.c 知道 */
    char *name;               /* C 侧分配、C 侧释放 */
    int64_t total;
};

/* 小工具：strdup 是 POSIX 函数，这里手写一份保持严格 ISO C11 可移植 */
static char *dup_str(const char *s) {
    size_t n = strlen(s) + 1;
    char *p = malloc(n);
    if (p != NULL)
        memcpy(p, s, n);
    return p;
}

session_t *session_create(const char *name, int *err_out) {
    if (err_out != NULL)
        *err_out = SESSION_OK;
    if (name == NULL || name[0] == '\0') {
        if (err_out != NULL)
            *err_out = SESSION_ERR_BADARG;
        return NULL;
    }
    session_t *s = malloc(sizeof *s);
    if (s == NULL) {
        if (err_out != NULL)
            *err_out = SESSION_ERR_NOMEM;
        return NULL;
    }
    s->name = dup_str(name);          /* 拷贝一份：不持有调用方内存 */
    if (s->name == NULL) {
        free(s);
        if (err_out != NULL)
            *err_out = SESSION_ERR_NOMEM;
        return NULL;
    }
    s->total = 0;
    return s;
}

const char *session_name(const session_t *s) {
    if (s == NULL)
        return NULL;
    return s->name;                   /* 借用：调用方不得 free */
}

int session_add(session_t *s, int32_t v) {
    if (s == NULL)
        return SESSION_ERR_BADARG;
    s->total += v;
    return SESSION_OK;
}

int64_t session_total(const session_t *s) {
    return s == NULL ? 0 : s->total;
}

int session_destroy(session_t *s) {
    if (s == NULL)
        return SESSION_ERR_BADARG;
    free(s->name);
    free(s);
    return SESSION_OK;
}

const char *session_strerror(int err) {
    switch (err) {
    case SESSION_OK:         return "ok";
    case SESSION_ERR_BADARG: return "invalid argument";
    case SESSION_ERR_NOMEM:  return "out of memory";
    default:                 return "unknown error";
    }
}
