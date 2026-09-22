// 来源：project/ —— report.c 结果输出模块实现
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c11
// 构建：make
// 验证状态：已验证
#include <stdio.h>
#include "report.h"

void report_print(const char *filename, const Stats *stats, int verbose) {
    printf("%s: %d 行, %d 单词, %d 字符",
           filename, stats->lines, stats->words, stats->chars);
    if (verbose)
        printf(" (最长行 %d 字符)", stats->longest_line);
    printf("\n");
}

void report_print_total(const Stats *total, int file_count) {
    printf("合计: %d 个文件, %d 行, %d 单词, %d 字符\n",
           file_count, total->lines, total->words, total->chars);
}
