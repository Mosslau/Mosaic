// 来源：06-file-io.md 第 6 章示例 2 —— CSV 文件解析器（fgets + strtok/sscanf）
// 对应 roadmap 练习"CSV 文件解析"与推荐项目"CSV 解析器"
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99 零警告
// 编译：gcc -Wall -Wextra -std=c99 ex02-csv-parser.c -o ex02-csv-parser
// 运行：./ex02-csv-parser students.csv   （样例数据见同目录 students.csv）
// 验证状态：已验证
#include <stdio.h>
#include <string.h>
typedef struct {
    char   name[32];
    int    age;
    double score;
} Student;
int main(void) {
    FILE *fp = fopen("students.csv", "r");
    if (fp == NULL) { perror("students.csv"); return 1; }
    char line[256];
    int  line_no = 0, valid = 0, skipped = 0;
    while (fgets(line, sizeof(line), fp) != NULL) {
        line_no++;
        line[strcspn(line, "\r\n")] = '\0';   /* 兼容 \r\n 与 \n */
        if (line[0] == '\0') { skipped++; continue; }   /* 空行 */
        char *name  = strtok(line, ",");
        char *age   = strtok(NULL, ",");
        char *score = strtok(NULL, ",");
        char *extra = strtok(NULL, ",");
        if (name == NULL || age == NULL || score == NULL || extra != NULL) {
            fprintf(stderr, "第 %d 行: 字段数错误, 已跳过\n", line_no);
            skipped++;
            continue;
        }
        Student s;
        if (sscanf(age, "%d", &s.age) != 1 || sscanf(score, "%lf", &s.score) != 1) {
            fprintf(stderr, "第 %d 行: 数字格式错误, 已跳过\n", line_no);
            skipped++;
            continue;
        }
        if (strlen(name) >= sizeof(s.name)) {
            fprintf(stderr, "第 %d 行: 名字过长, 已跳过\n", line_no);
            skipped++;
            continue;
        }
        strcpy(s.name, name);
        printf("%-8s 年龄=%d 成绩=%.1f\n", s.name, s.age, s.score);
        valid++;
    }
    if (ferror(fp)) { perror("读取失败"); fclose(fp); return 1; }
    fclose(fp);
    printf("共 %d 行: 有效 %d 条, 跳过 %d 行\n", line_no, valid, skipped);
    return 0;
}
