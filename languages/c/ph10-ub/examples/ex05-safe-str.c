/* ex05-safe-str.c —— 安全字符串工具库 sstr（安全示例, 可任意编译运行）
 * 演示 3.10 的"边界检查三件套"落成一个带容量的字符串类型:
 * 所有写入都带边界、永远保证 \0 结尾 —— 超长输入被截断而非溢出。
 * strncpy 不保证 \0(必须手动补), strncat 总是补 \0 但 n 不含 \0(要留 1 字节),
 * 两个函数的语义差异是必背点。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 ex05-safe-str.c -o ex05
// 运行：./ex05（输出 [hello, world!] len=13 cap=16）
// 验证状态：已验证（-Wall -Wextra 零警告; 加 -fsanitize=address,undefined 运行零报告）
#include <stdio.h>
#include <string.h>

typedef struct {
    char  *buf;   /* 缓冲区指针(由调用方提供存储) */
    size_t cap;   /* 缓冲区总容量(含 \0) */
    size_t len;   /* 当前长度(不含 \0) */
} sstr_t;

void sstr_init(sstr_t *s, char *buf, size_t cap) {
    s->buf = buf; s->cap = cap; s->len = 0;
    if (cap > 0) buf[0] = '\0';
}

/* 安全拷贝: strncpy 不保证 \0, 必须手动补 —— 这是最常见的 strncpy 坑 */
int sstr_copy(sstr_t *s, const char *src) {
    if (s->cap == 0) return -1;
    strncpy(s->buf, src, s->cap - 1);   /* 至多拷 cap-1 字节, 绝不越界 */
    s->buf[s->cap - 1] = '\0';          /* 手动补 \0 */
    s->len = strlen(s->buf);
    return 0;
}

/* 安全追加: strncat 最多拷 n 个字符且总是补 \0, 但 n 不含 \0, 要留 1 字节 */
int sstr_append(sstr_t *s, const char *src) {
    if (s->len >= s->cap - 1) return -1;          /* 已满, 拒绝 */
    size_t room = s->cap - 1 - s->len;            /* 还能写多少字符 */
    strncat(s->buf, src, room);                   /* room 个字符 + 自动 \0 */
    s->len = strlen(s->buf);
    return 0;
}

int main(void) {
    char storage[16];
    sstr_t s;
    sstr_init(&s, storage, sizeof storage);
    sstr_copy(&s, "hello");
    sstr_append(&s, ", world!");   /* 超出容量 → 被截断, 但不越界、不丢 \0 */
    printf("[%s] len=%zu cap=%zu\n", s.buf, s.len, s.cap);
    return 0;
}
