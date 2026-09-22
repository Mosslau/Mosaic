// 来源：project/ —— parse.c 行解析模块实现
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c11
// 构建：make
// 验证状态：已验证
#include "parse.h"
#include <string.h>

void parse_line(const char *line, Stats *stats) {
    stats->lines++;
    stats->chars += (int)strlen(line);
    int line_len = (int)strlen(line);
    if (line_len > stats->longest_line) stats->longest_line = line_len;

    /* strtok 会破坏 line，但调用方传的是只读字符串字面量/缓冲区副本——这里用 strtok_r 风格手动切 */
    int in_word = 0;
    for (const char *p = line; *p != '\0'; p++) {
        if (*p == ' ' || *p == '\t' || *p == '\n')
            in_word = 0;
        else if (!in_word) {
            in_word = 1;
            stats->words++;
        }
    }
}
