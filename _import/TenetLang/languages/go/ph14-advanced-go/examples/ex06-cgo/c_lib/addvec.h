/*
 * addvec.h —— ph14-advanced-go 示例 6 的 C 库头文件。
 * 一个极简"向量加法"库：把两个 int 数组逐元素相加写入第三个数组。
 * 与 addvec.c 配套；构建命令见模块 README 与 main.go 文件头。
 */
#ifndef ADDVEC_H
#define ADDVEC_H

#include <stddef.h>

/* out[i] = a[i] + b[i]，n 为元素个数；out 必须与 a/b 不重叠或允许就地。 */
void addvec(const int *a, const int *b, int *out, size_t n);

/* 两个 int 相加（演示最简单标量导出）。 */
int add(int a, int b);

#endif /* ADDVEC_H */
