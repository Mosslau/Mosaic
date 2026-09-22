// 来源：project/ —— main.c 命令行入口（多文件统计 + -v verbose）
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c11
// 构建：make
// 运行：./app file1.txt [file2.txt ...] 或 ./app -v file1.txt ...
// 验证状态：已验证
#include <stdio.h>
#include <string.h>

#include "io.h"
#include "parse.h"
#include "report.h"

#define LINE_MAX 512

int main(int argc, char *argv[]) {
    int   verbose = 0;
    int   first_file = 1;

    /* 解析 -v 选项 */
    if (argc > 1 && strcmp(argv[1], "-v") == 0) {
        verbose = 1;
        first_file = 2;
    }

    if (first_file >= argc) {
        fprintf(stderr, "用法: %s [-v] <文件1> [文件2 ...]\n", argv[0]);
        return 2;
    }

    Stats total = {0};
    int   processed = 0;

    for (int i = first_file; i < argc; i++) {
        FILE *fp = io_open(argv[i]);
        if (fp == NULL) {
            fprintf(stderr, "跳过 %s\n", argv[i]);
            continue;
        }
        Stats file_stats = {0};
        char  line[LINE_MAX];
        while (io_read_line(fp, line, sizeof(line)) == 0)
            parse_line(line, &file_stats);
        io_close(fp);

        report_print(argv[i], &file_stats, verbose);
        total.lines  += file_stats.lines;
        total.words  += file_stats.words;
        total.chars  += file_stats.chars;
        if (file_stats.longest_line > total.longest_line)
            total.longest_line = file_stats.longest_line;
        processed++;
    }

    if (processed > 1)
        report_print_total(&total, processed);

    return processed > 0 ? 0 : 1;
}
