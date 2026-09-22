// 来源：project/ —— CSV 解析器 CLI 入口（支持 -s 按成绩排序）
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99
// 编译：gcc -Wall -Wextra -std=c99 csv_parser.c main.c -o csvparser
// 运行：./csvparser students.csv  或  ./csvparser -s students.csv
// 验证状态：已验证
#include <stdio.h>
#include <string.h>

#include "csv_parser.h"

int main(int argc, char *argv[]) {
    int    sort_flag = 0;
    char  *path = NULL;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-s") == 0) sort_flag = 1;
        else if (path == NULL)          path = argv[i];
        else {
            fprintf(stderr, "用法: %s [-s] <csv文件>\n", argv[0]);
            return 2;
        }
    }
    if (path == NULL) {
        fprintf(stderr, "用法: %s [-s] <csv文件>\n", argv[0]);
        return 2;
    }

    CSVParser p = {0};
    if (csv_parse(&p, path) != 0) return 1;

    if (sort_flag) csv_sort_by_score(&p);
    csv_print(&p);
    csv_stats(&p);

    csv_free(&p);
    return 0;
}
