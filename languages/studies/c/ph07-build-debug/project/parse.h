// 来源：project/ —— parse.h 行解析模块接口
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c11
// 构建：make
// 验证状态：已验证
#ifndef PARSE_H
#define PARSE_H

typedef struct {
    int lines;
    int words;
    int chars;
    int longest_line;   /* 最长行的字符数 */
} Stats;

/* 解析一行，累计到 stats */
void parse_line(const char *line, Stats *stats);

#endif /* PARSE_H */
