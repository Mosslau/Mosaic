// 来源：project/ —— darray 动态数组库头文件
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99
// 编译：gcc -Wall -Wextra -std=c99 darray.c main.c -o darray
// 验证状态：已验证
#ifndef DARRAY_H
#define DARRAY_H

#include <stddef.h>

typedef struct {
    int   *data;
    size_t len;    /* 已用元素数 */
    size_t cap;    /* 容量（元素数） */
    int    last_err; /* 0 正常；非 0 记录最近一次错误（越界/空 pop） */
} DArray;

/* 创建：初始容量 4；失败返回 NULL */
DArray *darray_create(void);

/* 销毁：释放全部内存 */
void darray_destroy(DArray *da);

/* 尾部追加，自动 2x 扩容；realloc 失败返回 -1，原数据不丢失 */
int darray_push(DArray *da, int val);

/* 弹出末尾元素；空数组返回 0 并置 last_err */
int darray_pop(DArray *da);

/* 按下标读；越界返回 0 并置 last_err */
int darray_get(const DArray *da, size_t idx);

/* 按下标写；越界返回 -1 */
int darray_set(DArray *da, size_t idx, int val);

size_t darray_size(const DArray *da);
size_t darray_capacity(const DArray *da);

#endif /* DARRAY_H */
