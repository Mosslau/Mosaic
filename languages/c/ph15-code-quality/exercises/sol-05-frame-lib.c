/* sol-05-frame-lib.c —— 参考实现: 可复用 frame 解析库（增量状态机 + 回调）
 *
 * 题目要点: 把"从字节流里拆 frame"做成可复用组件:
 *   - 状态机驱动: 每喂一段字节, 内部按 LEN_HI→LEN_LO→PAYLOAD 状态推进;
 *   - 解出一个完整 frame 就调一次 on_frame 回调（带 ctx, 衔接 ph15 回调约定）;
 *   - 长度超上限 → 返回稳定错误码 ERR_OVERSIZE 并进入错误态;
 *   - 数据不足 → 返回 0 (need more), 继续喂即可;
 *   - 全程零全局状态: 解析器句柄自包含, 可同时解析多个流(可复用性验证)。
 * 说明: 本组件只管"拆帧逻辑"; WAL record 的字节序/CRC/落盘语义分别属
 *   ph12/ph13/ph16, 这里演示的是 ph15 的组件 API 设计(状态机+回调+错误码)。
 * 实测: 3 个 frame 分 4 块喂入全部解出; 超限 frame 被拒; 两个解析器实例互不干扰。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-05-frame-lib.c -o sol05
// 运行：./sol05（无外部产物, 退出码 0）
// 验证状态：已验证（零警告; 3 frame 解出顺序/超限拒绝/双实例隔离为实测, 见文件尾）
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---- 稳定错误码 ---- */
enum {
    FR_OK = 0,          /* 本段喂入正常处理完 */
    FR_ERR_OVERSIZE = -1, /* frame 长度超上限 */
    FR_ERR_STATE = -2,  /* 错误态下继续喂 */
};

#define FRAME_LEN_MAX 64u

/* ---- 回调约定: 解出一个 frame 时调用; ctx 由解析器使用者提供 ---- */
typedef void (*frame_cb)(const uint8_t *payload, uint16_t len, void *ctx);

/* ---- opaque 解析器句柄 ---- */
typedef struct frame_parser fp_t;

fp_t *fp_create(frame_cb cb, void *ctx);
void fp_destroy(fp_t *p);
/* 错误态后调用 reset 才能继续解析同一解析器（新流的开头） */
void fp_reset(fp_t *p);
/* 喂入数据; 返回本段解出的 frame 数, 负数为错误码 */
int fp_feed(fp_t *p, const uint8_t *data, size_t n);
uint16_t fp_last_len(const fp_t *p);   /* 最近解出的 frame 长度(诊断用) */

struct frame_parser {
    frame_cb cb;
    void *ctx;
    enum { ST_LEN_HI, ST_LEN_LO, ST_PAYLOAD } st;
    uint16_t want;        /* 还差多少字节到完整 frame */
    uint16_t len;         /* 当前 frame 声明长度 */
    uint16_t got;         /* 已收 payload 字节数 */
    uint8_t buf[FRAME_LEN_MAX];
    uint16_t last_len;
    int broken;           /* 1 = 已进入错误态 */
};

fp_t *fp_create(frame_cb cb, void *ctx) {
    fp_t *p = (fp_t *)calloc(1, sizeof *p);
    if (p == NULL) return NULL;
    p->cb = cb;
    p->ctx = ctx;
    p->st = ST_LEN_HI;
    return p;
}

void fp_destroy(fp_t *p) { if (p) free(p); }

static void fp_reset_stream(fp_t *p) {
    p->st = ST_LEN_HI;
    p->broken = 0;
    p->len = 0;
    p->got = 0;
}

void fp_reset(fp_t *p) { if (p) fp_reset_stream(p); }

int fp_feed(fp_t *p, const uint8_t *data, size_t n) {
    if (p == NULL) return FR_ERR_STATE;
    if (p->broken) return FR_ERR_STATE;      /* 错误态: 必须重置流 */

    int frames = 0;
    for (size_t i = 0; i < n; i++) {
        uint8_t b = data[i];
        switch (p->st) {
        case ST_LEN_HI:
            p->len = (uint16_t)((uint16_t)b << 8);
            p->st = ST_LEN_LO;
            break;
        case ST_LEN_LO:
            p->len |= b;
            if (p->len > FRAME_LEN_MAX) {    /* 长度超限: 进入错误态 */
                p->broken = 1;
                return FR_ERR_OVERSIZE;
            }
            p->got = 0;
            p->st = p->len == 0 ? ST_LEN_HI : ST_PAYLOAD;  /* 空 frame 直接结束 */
            if (p->len == 0) {
                frames++;
                p->last_len = 0;
                if (p->cb) p->cb(NULL, 0, p->ctx);
            }
            break;
        case ST_PAYLOAD:
            p->buf[p->got++] = b;
            if (p->got == p->len) {          /* payload 收满: 解出一个 frame */
                p->last_len = p->len;
                if (p->cb) p->cb(p->buf, p->len, p->ctx);
                frames++;
                p->st = ST_LEN_HI;
            }
            break;
        }
    }
    return frames;
}

uint16_t fp_last_len(const fp_t *p) { return p == NULL ? 0 : p->last_len; }

/* ---- 演示: 回调统计解出的 frame ---- */

struct sink {
    int count;
    char out[3][16];
    void *tag;              /* 演示 ctx 携带身份 */
};

static void on_frame(const uint8_t *payload, uint16_t len, void *ctx) {
    struct sink *s = (struct sink *)ctx;
    if (s->count < 3) {
        size_t cp = len < 15u ? len : 15u;
        memcpy(s->out[s->count], payload, cp);
        s->out[s->count][cp] = '\0';
    }
    s->count++;
}

static void dump_sink(const char *name, const struct sink *s) {
    printf("%s: 解出 %d 个 frame:", name, s->count);
    for (int i = 0; i < s->count && i < 3; i++)
        printf(" \"%s\"", s->out[i]);
    printf("\n");
}

int main(void) {
    printf("=== sol-05 可复用 frame 解析库 ===\n");

    struct sink s1 = {0, {{0}}, (void *)0x1};
    struct sink s2 = {0, {{0}}, (void *)0x2};

    fp_t *p1 = fp_create(on_frame, &s1);
    fp_t *p2 = fp_create(on_frame, &s2);

    /* 流 1: "ping" + "pong" + "data!" 三个 frame, 按 [len:u16 大端][payload] */
    const char *msgs1[3] = {"ping", "pong", "data!"};
    uint8_t stream1[128];
    size_t n1 = 0;
    for (int i = 0; i < 3; i++) {
        size_t ml = strlen(msgs1[i]);
        stream1[n1++] = (uint8_t)(ml >> 8);
        stream1[n1++] = (uint8_t)(ml & 0xff);
        memcpy(stream1 + n1, msgs1[i], ml);
        n1 += ml;
    }

    /* 分 4 块喂入: 先 1 字节、2 字节、3 字节, 再把剩下的全喂 —— 增量解析 */
    int total = 0;
    size_t off = 0;
    const size_t chunk_sizes[4] = {1, 2, 3, n1 - 6};
    for (int c = 0; c < 4; c++) {
        size_t end = off + chunk_sizes[c];
        if (end > n1) end = n1;
        int got = fp_feed(p1, stream1 + off, end - off);
        printf("流1 喂入 %zu 字节 → 解出 %d 个\n", end - off, got);
        total += got;
        off = end;
    }
    dump_sink("流1 汇总", &s1);

    /* 流 2: 一个超限 frame(长度 100 > 64) —— 应报 OVERSIZE */
    uint8_t big[3] = {0x00, 100, 0x61};
    int rc = fp_feed(p2, big, sizeof big);
    printf("流2 喂入超限 frame → rc=%d (%s)\n", rc,
           rc == FR_ERR_OVERSIZE ? "FR_ERR_OVERSIZE" : "?");
    printf("流2 错误态下继续喂 → rc=%d (FR_ERR_STATE)\n",
           fp_feed(p2, big, 1));

    /* 流 2 重置后正常解析, 证明可复用/隔离 */
    fp_reset(p2);
    uint8_t ok2[4] = {0x00, 2, 'o', 'k'};
    int got2 = fp_feed(p2, ok2, sizeof ok2);
    (void)got2;
    dump_sink("流2 重置后", &s2);

    int fails = 0;
    if (s1.count != 3) { printf("FAIL: 流1 frame 数=%d\n", s1.count); fails++; }
    if (strcmp(s1.out[0], "ping") != 0 || strcmp(s1.out[1], "pong") != 0 ||
        strcmp(s1.out[2], "data!") != 0) {
        printf("FAIL: 流1 payload 内容\n"); fails++;
    }
    if (total != 3) { printf("FAIL: 分块喂入解出总数=%d\n", total); fails++; }
    if (s2.count != 1 || strcmp(s2.out[0], "ok") != 0) {
        printf("FAIL: 流2 重置后解析\n"); fails++;
    }

    fp_destroy(p1);
    fp_destroy(p2);
    printf(fails == 0 ? "sol-05: 全部断言通过, 退出码 0\n"
                      : "sol-05: 有断言失败\n");
    return fails == 0 ? 0 : 1;
}

/* 实测输出（本机一次运行, Apple clang 21.0.0, macOS arm64）：
 * === sol-05 可复用 frame 解析库 ===
 * 流1 喂入 1 字节 → 解出 0 个
 * 流1 喂入 2 字节 → 解出 0 个
 * 流1 喂入 3 字节 → 解出 1 个
 * 流1 喂入 13 字节 → 解出 2 个
 * 流1 汇总: 解出 3 个 frame: "ping" "pong" "data!"
 * 流2 喂入超限 frame → rc=-1 (FR_ERR_OVERSIZE)
 * 流2 错误态下继续喂 → rc=-2 (FR_ERR_STATE)
 * 流2 重置后: 解出 1 个 frame: "ok"
 * sol-05: 全部断言通过, 退出码 0
 */
