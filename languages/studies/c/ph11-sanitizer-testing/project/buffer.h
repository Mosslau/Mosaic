/* buffer.h —— 带测试的 append-only 字节 buffer（ph11 阶段项目）
 * 语义: append-only（只追加, 不随机改）——为 ph12 length-prefix frame /
 * ph16 WAL 的"顺序写"语义预演; 所有接口带边界检查与错误路径。
 * 边界声明: 字节序/长度前缀编码等二进制格式细节属 ph12 字节序、内存对齐
 * 与二进制格式解析阶段（roadmap 第 12 节）, 本库只提供字节存储原语。
 */
#ifndef BUFFER_H
#define BUFFER_H

#include <stddef.h>

typedef struct {
    unsigned char *data;   /* 数据区(由库管理) */
    size_t         len;    /* 已写字节数 */
    size_t         cap;    /* 容量(字节数) */
} Buffer;

/* 初始化: cap 为初始容量(0 则给 1); 成功 0, 失败(参数非法/分配失败) -1 */
int    buf_init(Buffer *b, size_t cap);
/* 释放并重置; 接受 NULL */
void   buf_destroy(Buffer *b);
/* 追加 n 字节: 容量不足自动扩容(至少翻倍); 成功 0, 失败 -1(原数据不丢) */
int    buf_append(Buffer *b, const void *src, size_t n);
/* 读取第 idx 字节: 越界或参数非法返回 -1; 成功 0 且 *out 为字节值 */
int    buf_get(const Buffer *b, size_t idx, unsigned char *out);
/* 当前长度; 接受 NULL(返回 0) */
size_t buf_len(const Buffer *b);

#endif /* BUFFER_H */
