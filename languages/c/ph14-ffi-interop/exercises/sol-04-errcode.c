/* sol-04-errcode.c —— 参考实现: 设计跨语言错误码 + 错误消息 + err_out 上报
 *
 * 编译: cc -Wall -Wextra -std=c11 sol-04-errcode.c -o sol04
 * 运行: ./sol04
 * 验证环境: Apple clang 21.0.0（cc，macOS arm64）
 * 验证状态: 已验证（零警告; 3 种可确定性触发的错误全部 PASS, 退出码 0;
 *          实测输出见文件尾）
 *
 * ============ 设计契约（写进头文件注释, 跨语言消费方按此实现） ============
 * 1. 0 = 成功; 负数为错误码。数值与含义一一对应, 一经发布不再改值
 *    （ABI 稳定优先——下游 Python/Rust 可能已经按旧值写好了判断）。
 * 2. 不使用 errno: errno 是 C 的线程局部全局, ctypes/Rust FFI 读取
 *    麻烦且不可移植。错误码一律走 err_out 出参。
 * 3. 错误消息经 box_errstr 读取: 返回静态字符串（借用, 无需释放）。
 * 4. Python 侧消费:  err_out 用 ctypes.byref(ctypes.c_int) 传地址,
 *    消息用 c_char_p restype 读回; Rust 侧消费: *mut c_int + *const c_char,
 *    create 失败判 NULL 后读 err_out。
 * ==========================================================================
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---- 错误码（0 成功, 负数错误; 数值稳定） ---- */
enum {
    BOX_OK = 0,
    BOX_ERR_BADARG = -1,   /* 参数非法: label 为空/NULL, 或句柄为 NULL */
    BOX_ERR_TOOLONG = -2,  /* label 超过上限 BOX_LABEL_MAX */
    BOX_ERR_FULL = -3,     /* push 次数超过上限 BOX_PUSH_MAX */
    BOX_ERR_NOMEM = -4,    /* 内存不足（本自测无法确定性触发, 代码路径需人工审） */
};

#define BOX_LABEL_MAX 8u
#define BOX_PUSH_MAX 100   /* 有符号字面量: 与 int32_t/循环计数比较不触发 sign-compare */

typedef struct box box_t;   /* opaque 句柄 */

box_t *box_new(const char *label, int32_t *err_out);
int32_t box_push(box_t *b, int32_t v);
int64_t box_total(const box_t *b);
int32_t box_free(box_t *b);
const char *box_errstr(int32_t err);

/* ---- 实现 ---- */
struct box {
    char label[BOX_LABEL_MAX + 1];
    int64_t total;
    int32_t pushes;
};

box_t *box_new(const char *label, int32_t *err_out) {
    if (err_out != NULL)
        *err_out = BOX_OK;
    if (label == NULL || label[0] == '\0') {
        if (err_out != NULL)
            *err_out = BOX_ERR_BADARG;
        return NULL;
    }
    if (strlen(label) > BOX_LABEL_MAX) {
        if (err_out != NULL)
            *err_out = BOX_ERR_TOOLONG;
        return NULL;
    }
    box_t *b = malloc(sizeof *b);
    if (b == NULL) {                       /* 无法确定性触发, 仍要写对 */
        if (err_out != NULL)
            *err_out = BOX_ERR_NOMEM;
        return NULL;
    }
    strcpy(b->label, label);
    b->total = 0;
    b->pushes = 0;
    return b;
}

int32_t box_push(box_t *b, int32_t v) {
    if (b == NULL)
        return BOX_ERR_BADARG;
    if (b->pushes >= BOX_PUSH_MAX)
        return BOX_ERR_FULL;
    b->pushes++;
    b->total += v;
    return BOX_OK;
}

int64_t box_total(const box_t *b) {
    return b == NULL ? 0 : b->total;
}

int32_t box_free(box_t *b) {
    if (b == NULL)
        return BOX_ERR_BADARG;
    free(b);                               /* 谁 new 谁 free（C 侧闭环） */
    return BOX_OK;
}

const char *box_errstr(int32_t err) {
    switch (err) {
    case BOX_OK:         return "ok";
    case BOX_ERR_BADARG: return "invalid argument";
    case BOX_ERR_TOOLONG:return "label too long";
    case BOX_ERR_FULL:   return "box full";
    case BOX_ERR_NOMEM:  return "out of memory";
    default:             return "unknown error";
    }
}

/* ---- 自测 ---- */
static int failures = 0;

#define CHECK(cond, msg)                                          \
    do {                                                          \
        if (cond)                                                 \
            printf("PASS: %s\n", msg);                            \
        else {                                                    \
            printf("FAIL: %s\n", msg);                            \
            failures++;                                           \
        }                                                         \
    } while (0)

int main(void) {
    int32_t err = BOX_OK;

    /* 正常路径: create → push ×2 → total=42 → free */
    box_t *b = box_new("tally", &err);
    CHECK(b != NULL && err == BOX_OK, "正常 create: 返回非 NULL, err=0");
    if (b != NULL) {
        CHECK(box_push(b, 40) == BOX_OK, "push(40) 成功");
        CHECK(box_push(b, 2) == BOX_OK, "push(2) 成功");
        CHECK(box_total(b) == 42, "total == 42");
        CHECK(box_free(b) == BOX_OK, "free 成功");
    }

    /* 错误 1: 空 label → BADARG + 消息 */
    box_t *bad = box_new("", &err);
    CHECK(bad == NULL && err == BOX_ERR_BADARG, "空 label: 返回 NULL, err=-1");
    CHECK(strcmp(box_errstr(err), "invalid argument") == 0,
          "err=-1 的消息 == \"invalid argument\"");

    /* 错误 2: 超长 label → TOOLONG + 消息 */
    bad = box_new("toolonglabel", &err);
    CHECK(bad == NULL && err == BOX_ERR_TOOLONG,
          "超长 label: 返回 NULL, err=-2");
    CHECK(strcmp(box_errstr(err), "label too long") == 0,
          "err=-2 的消息 == \"label too long\"");

    /* 错误 3: push 超过上限 → FULL + 消息 */
    b = box_new("tally2", &err);
    CHECK(b != NULL, "正常 create tally2");
    if (b != NULL) {
        int32_t rc = BOX_OK;
        for (int i = 0; i < BOX_PUSH_MAX; i++)
            rc = box_push(b, 1);
        CHECK(rc == BOX_OK, "第 100 次 push 仍成功");
        rc = box_push(b, 1);
        CHECK(rc == BOX_ERR_FULL, "第 101 次 push: err=-3(FULL)");
        CHECK(strcmp(box_errstr(rc), "box full") == 0,
              "err=-3 的消息 == \"box full\"");
        CHECK(box_free(b) == BOX_OK, "free tally2 成功");
    }

    if (failures == 0)
        printf("sol-04: 全部断言通过, 退出码 0\n");
    return failures == 0 ? 0 : 1;
}

/* 实测输出（本机一次运行）：
 * PASS: 正常 create: 返回非 NULL, err=0
 * PASS: push(40) 成功
 * PASS: push(2) 成功
 * PASS: total == 42
 * PASS: free 成功
 * PASS: 空 label: 返回 NULL, err=-1
 * PASS: err=-1 的消息 == "invalid argument"
 * PASS: 超长 label: 返回 NULL, err=-2
 * PASS: err=-2 的消息 == "label too long"
 * PASS: 正常 create tally2
 * PASS: 第 100 次 push 仍成功
 * PASS: 第 101 次 push: err=-3(FULL)
 * PASS: err=-3 的消息 == "box full"
 * PASS: free tally2 成功
 * sol-04: 全部断言通过, 退出码 0
 */
