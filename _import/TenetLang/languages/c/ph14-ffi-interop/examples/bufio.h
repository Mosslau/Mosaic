/* bufio.h —— 跨语言所有权约定演示库
 *
 * 三种约定对应 roadmap §14 必会概念"字符串、数组、结构体都要定义所有权规则"：
 *   约定 1（谁分配谁释放）：bufio_str_dup 用 C 的 malloc 分配新串，
 *     调用方用完必须调用 bufio_str_free 释放——跨语言时"释放"也必须
 *     回到 C 侧，不能交给其他语言的运行时
 *   约定 2（调用方分配，C 只写）：bufio_str_copy 写入调用方提供的缓冲区，
 *     缓冲区的分配与生命周期都属于调用方
 *   约定 3（C 只读借用调用方数据）：bufio_sum 借用调用方的数组，不复制
 *     不释放；调用方保证数组在调用期间有效
 * 另有简单 POD 结构体 bufio_pt 按值传递：跨语言时布局必须一致
 *（ctypes 的 Structure / Rust 的 repr(C) struct 都要对齐字段与宽度）。
 */
#ifndef BUFIO_H
#define BUFIO_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* 约定 1：C 分配新串，调用方负责用 bufio_str_free 释放 */
char *bufio_str_dup(const char *s);
void bufio_str_free(char *s);

/* 约定 2：把 s 拷进调用方缓冲区 dst；返回需要的长度（不含 \0），
 * 返回值 >= cap 表示缓冲区不够（内容已按 cap-1 截断）；
 * s == NULL 返回 0（与 bufio_str_dup 的 NULL 契约一致） */
size_t bufio_str_copy(char *dst, size_t cap, const char *s);

/* 约定 3：只读借用调用方数组求和；n 由调用方传入 */
int64_t bufio_sum(const int32_t *arr, size_t n);

/* 简单 POD 结构体，按值传递（跨语言布局需一致） */
typedef struct {
    int32_t x;
    int32_t y;
} bufio_pt;

bufio_pt bufio_pt_add(bufio_pt a, bufio_pt b);

#ifdef __cplusplus
}
#endif

#endif /* BUFIO_H */
