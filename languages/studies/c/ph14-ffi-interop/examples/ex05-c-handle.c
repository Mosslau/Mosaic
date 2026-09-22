/* ex05-c-handle.c —— C 调用 session 句柄库（opaque pointer + create/destroy）
 *
 * 编译（macOS）：
 *   cc -Wall -Wextra -std=c11 -dynamiclib session.c -o /tmp/ph14-ex/libsession.dylib
 *   cc -Wall -Wextra -std=c11 ex05-c-handle.c -L/tmp/ph14-ex -lsession \
 *       -o /tmp/ph14-ex/ex05-c
 * 运行：/tmp/ph14-ex/ex05-c
 */
#include <stdio.h>

#include "session.h"

int main(void) {
    int err = 0;
    session_t *s = session_create("c-caller", &err);
    if (s == NULL) {
        printf("create 失败: %s\n", session_strerror(err));
        return 1;
    }
    printf("create 成功, name=%s\n", session_name(s));   /* 借用内部指针 */
    session_add(s, 40);
    session_add(s, 2);
    printf("total = %lld\n", (long long)session_total(s));

    int rc = session_destroy(s);                          /* 谁 create 谁 destroy */
    printf("destroy rc=%d (%s)\n", rc, session_strerror(rc));

    /* 错误路径：空 name → NULL + BADARG + 错误消息 */
    session_t *bad = session_create("", &err);
    printf("空 name create: ptr=%s err=%d (%s)\n",
           bad == NULL ? "NULL" : "非空?!", err, session_strerror(err));
    return 0;
}
