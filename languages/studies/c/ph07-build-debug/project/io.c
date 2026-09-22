// 来源：project/ —— io.c 文件读取模块实现
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c11
// 构建：make
// 验证状态：已验证
#include "io.h"
#include <string.h>

FILE *io_open(const char *path) {
    FILE *fp = fopen(path, "r");
    if (fp == NULL) perror(path);
    return fp;
}

int io_read_line(FILE *fp, char *line, size_t cap) {
    if (fgets(line, (int)cap, fp) == NULL) return -1;
    return 0;
}

void io_close(FILE *fp) {
    if (fp != NULL) fclose(fp);
}
