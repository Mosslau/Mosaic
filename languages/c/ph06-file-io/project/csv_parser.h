// 来源：project/ —— CSV 解析器头文件
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99
// 编译：gcc -Wall -Wextra -std=c99 csv_parser.c main.c -o csvparser
// 验证状态：已验证
#ifndef CSV_PARSER_H
#define CSV_PARSER_H

#include <stddef.h>

#define CSV_NAME_MAX 32

typedef struct {
    char   name[CSV_NAME_MAX];
    int    age;
    double score;
} CSVRecord;

typedef struct {
    CSVRecord *records;
    size_t     count;      /* 有效记录数 */
    size_t     capacity;
    size_t     total_lines;   /* 总行数 */
    size_t     skipped;       /* 跳过行数 */
    int        err_field;     /* 字段数错误 */
    int        err_number;    /* 数字格式错误 */
    int        err_length;    /* 名字超长 */
} CSVParser;

/* 解析文件；失败返回 -1（perror 已打印） */
int csv_parse(CSVParser *p, const char *path);

/* 按 score 降序排序（qsort 比较函数） */
void csv_sort_by_score(CSVParser *p);

/* 打印全部有效记录 */
void csv_print(const CSVParser *p);

/* 打印统计：总行/有效/跳过 + 失败原因分布 */
void csv_stats(const CSVParser *p);

/* 释放内部资源 */
void csv_free(CSVParser *p);

#endif /* CSV_PARSER_H */
