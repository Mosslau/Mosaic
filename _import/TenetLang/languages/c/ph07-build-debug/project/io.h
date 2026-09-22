// 来源：project/ —— io.h 文件读取模块接口
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c11
// 构建：make
// 验证状态：已验证
#ifndef IO_H
#define IO_H

#include <stdio.h>

/* 打开文件；失败返回 NULL 且 perror 已打印 */
FILE *io_open(const char *path);

/* 逐行读取；返回 0 成功（line 含内容），-1 结束/出错 */
int io_read_line(FILE *fp, char *line, size_t cap);

/* 关闭文件 */
void io_close(FILE *fp);

#endif /* IO_H */
