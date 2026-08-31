/* sol-05-safe-str.c —— 参考实现: 给字符串处理函数补边界检查
 * 把 ph03 手写的 strcpy/strcat 升级为带容量的 sstr(参考 examples/ex05-safe-str.c),
 * 并补两个能力: ① 写入返回"是否被截断"(0=完整, 1=截断); ② 追加前先查剩余容量。
 * 核心保证: 所有写入带边界、永远补 \0 —— 超长输入被截断而非溢出。
 * strncpy 不保证 \0(必须手动补), strncat 总是补 \0 但 n 不含 \0(要留 1 字节)。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-05-safe-str.c -o sol05
// 运行：./sol05（3 次写入分别验证 完整/截断/截断, 退出码 0）
// 验证状态：已验证（-Wall -Wextra 零警告; 加 -fsanitize=address,undefined 运行零报告）
#include <stdio.h>
#include <string.h>

typedef struct {
    char  *buf;   /* 缓冲区指针(由调用方提供存储) */
    size_t cap;   /* 总容量(含 \0) */
    size_t len;   /* 当前长度(不含 \0) */
} sstr_t;

static void sstr_init(sstr_t *s, char *buf, size_t cap) {
    s->buf = buf; s->cap = cap; s->len = 0;
    if (cap > 0) buf[0] = '\0';
}

/* 安全拷贝: 返回 0=完整写入, 1=被截断(源长度 ≥ 容量) */
static int sstr_copy(sstr_t *s, const char *src) {
    if (s->cap == 0) return 1;
    size_t need = strlen(src);              /* 源长度(不含 \0) */
    strncpy(s->buf, src, s->cap - 1);       /* 至多拷 cap-1 字节, 绝不越界 */
    s->buf[s->cap - 1] = '\0';              /* 手动补 \0: strncpy 不保证 */
    s->len = strlen(s->buf);
    return need >= s->cap ? 1 : 0;          /* 源比容量还长 → 截断 */
}

/* 安全追加: strncat 总是补 \0, 但 n 不含 \0, 要留 1 字节 */
static int sstr_append(sstr_t *s, const char *src) {
    if (s->len >= s->cap - 1) return 1;     /* 已满, 拒绝 */
    size_t room = s->cap - 1 - s->len;      /* 还能写多少字符 */
    size_t need = strlen(src);
    strncat(s->buf, src, room);
    s->len = strlen(s->buf);
    return need > room ? 1 : 0;             /* 装不下 → 截断 */
}

static void report(const char *label, int truncated, const sstr_t *s) {
    printf("%s: [%s] len=%zu cap=%zu 截断=%s\n",
           label, s->buf, s->len, s->cap, truncated ? "是" : "否");
}

int main(void) {
    char storage[16];
    sstr_t s;
    sstr_init(&s, storage, sizeof storage);
    report("copy 完整",   sstr_copy(&s, "hello"),             &s);
    report("append 截断", sstr_append(&s, "0123456789AB"),    &s);  /* 12 > 剩余 10 → 截断 */
    report("copy 截断",   sstr_copy(&s, "0123456789ABCDEFGH"), &s);  /* 18 ≥ 16 → 截断 */
    return 0;
}
