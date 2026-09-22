// 来源：06-file-io.md 第 6 章示例 1 —— 文本文件逐行读取与统计（fgets）
// 对应 roadmap 练习"日志系统/文本统计工具"的读取骨架
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99 零警告
// 编译：gcc -Wall -Wextra -std=c99 ex01-line-stats.c -o ex01-line-stats
// 运行：./ex01-line-stats sample.txt
// 验证状态：已验证
#include <stdio.h>
#include <string.h>
int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "用法: %s <文件名>\n", argv[0]);
        return 1;
    }
    FILE *fp = fopen(argv[1], "r");
    if (fp == NULL) {                 /* 文件不存在/权限不足 */
        perror(argv[1]);
        return 1;
    }
    char line[512];
    int  lines = 0, words = 0, chars = 0;
    while (fgets(line, sizeof(line), fp) != NULL) {
        lines++;
        chars += (int)strlen(line);
        for (char *tok = strtok(line, " \t\n"); tok != NULL; tok = strtok(NULL, " \t\n"))
            words++;
    }
    if (ferror(fp)) {                 /* 区分"读完"与"读出错" */
        perror("读取失败");
        fclose(fp);
        return 1;
    }
    fclose(fp);
    printf("%s: %d 行, %d 单词, %d 字符\n", argv[1], lines, words, chars);
    return 0;
}
