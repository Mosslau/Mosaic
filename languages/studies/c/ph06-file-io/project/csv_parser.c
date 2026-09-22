// 来源：project/ —— CSV 解析器实现（三重校验 + 坏行报告 + 排序）
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99
// 编译：gcc -Wall -Wextra -std=c99 csv_parser.c main.c -o csvparser
// 验证状态：已验证
#include "csv_parser.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CSV_INIT_CAP 16

static int csv_reserve(CSVParser *p, size_t need) {
    if (need <= p->capacity) return 0;
    size_t new_cap = p->capacity ? p->capacity * 2 : CSV_INIT_CAP;
    while (new_cap < need) new_cap *= 2;
    CSVRecord *tmp = realloc(p->records, new_cap * sizeof(CSVRecord));
    if (tmp == NULL) return -1;
    p->records = tmp;
    p->capacity = new_cap;
    return 0;
}

int csv_parse(CSVParser *p, const char *path) {
    FILE *fp = fopen(path, "r");
    if (fp == NULL) { perror(path); return -1; }

    char line[256];
    while (fgets(line, sizeof(line), fp) != NULL) {
        p->total_lines++;
        line[strcspn(line, "\r\n")] = '\0';
        if (line[0] == '\0') { p->skipped++; continue; }

        char *name  = strtok(line, ",");
        char *age   = strtok(NULL, ",");
        char *score = strtok(NULL, ",");
        char *extra = strtok(NULL, ",");
        if (name == NULL || age == NULL || score == NULL || extra != NULL) {
            fprintf(stderr, "第 %zu 行: 字段数错误, 已跳过\n", p->total_lines);
            p->err_field++;
            p->skipped++;
            continue;
        }
        CSVRecord r;
        if (sscanf(age, "%d", &r.age) != 1 || sscanf(score, "%lf", &r.score) != 1) {
            fprintf(stderr, "第 %zu 行: 数字格式错误, 已跳过\n", p->total_lines);
            p->err_number++;
            p->skipped++;
            continue;
        }
        if (strlen(name) >= sizeof(r.name)) {
            fprintf(stderr, "第 %zu 行: 名字过长, 已跳过\n", p->total_lines);
            p->err_length++;
            p->skipped++;
            continue;
        }
        strcpy(r.name, name);
        if (csv_reserve(p, p->count + 1) != 0) {
            fclose(fp);
            return -1;
        }
        p->records[p->count++] = r;
    }
    if (ferror(fp)) { perror("读取失败"); fclose(fp); return -1; }
    fclose(fp);
    return 0;
}

static int cmp_score_desc(const void *a, const void *b) {
    const CSVRecord *ra = a, *rb = b;
    if (ra->score > rb->score) return -1;
    if (ra->score < rb->score) return 1;
    return 0;
}

void csv_sort_by_score(CSVParser *p) {
    qsort(p->records, p->count, sizeof(CSVRecord), cmp_score_desc);
}

void csv_print(const CSVParser *p) {
    for (size_t i = 0; i < p->count; i++)
        printf("%-8s 年龄=%d 成绩=%.1f\n",
               p->records[i].name, p->records[i].age, p->records[i].score);
}

void csv_stats(const CSVParser *p) {
    printf("共 %zu 行: 有效 %zu 条, 跳过 %zu 行\n",
           p->total_lines, p->count, p->skipped);
    printf("  失败原因: 字段数 %d, 数字格式 %d, 名字超长 %d\n",
           p->err_field, p->err_number, p->err_length);
}

void csv_free(CSVParser *p) {
    free(p->records);
    p->records = NULL;
    p->count = p->capacity = 0;
}
