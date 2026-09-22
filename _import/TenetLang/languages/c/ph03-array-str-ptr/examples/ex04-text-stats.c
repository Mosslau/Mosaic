/* examples/ex04-text-stats.c —— 简单文本统计工具（字符数/单词数/行数）
 * 验证环境：Apple clang 17.0.0（gcc 兼容），C99
 * 编译：gcc -Wall -Wextra -std=c99 ex04-text-stats.c -o ex04
 * 运行：./ex04 < 输入文件   （或 echo "hello world" | ./ex04）
 * 已验证：本环境编译零警告，echo "hello world" 管道输入输出 字符数 12 / 单词数 2 / 行数 1
 */
#include <stdio.h>

void text_stats(const char *text) {
    int chars = 0, words = 0, lines = 0, in_word = 0;
    for (const char *p = text; *p != '\0'; p++) {
        chars++;
        if (*p == '\n') lines++;
        if (*p == ' ' || *p == '\n' || *p == '\t')
            in_word = 0;
        else if (!in_word) { in_word = 1; words++; }
    }
    /* 若最后一行没有换行符结尾，行数要 +1；否则 lines 已经等于行数 */
    int total_lines = (chars > 0 && text[chars - 1] != '\n') ? lines + 1 : lines;
    printf("字符数: %d\n单词数: %d\n行数: %d\n", chars, words, total_lines);
}

int main(void) {
    /* 输入格式: 多行文本，Ctrl+D（Unix）或 Ctrl+Z（Windows）结束 */
    char buf[4096] = {0};
    size_t total = 0;
    int c;
    while (total < sizeof(buf) - 1 && (c = getchar()) != EOF)
        buf[total++] = (char)c;
    buf[total] = '\0';
    text_stats(buf);
    return 0;
}
