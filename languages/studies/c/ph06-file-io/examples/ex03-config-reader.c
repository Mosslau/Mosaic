// 来源：06-file-io.md 第 6 章示例 3 —— 配置文件的 key=value 读取
// 对应 roadmap 练习"读取配置文件"
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99 零警告
// 编译：gcc -Wall -Wextra -std=c99 ex03-config-reader.c -o ex03-config-reader
// 运行：./ex03-config-reader app.conf   （样例数据见同目录 app.conf）
// 验证状态：已验证
#include <stdio.h>
#include <string.h>
#define MAX_KEY 32
#define MAX_VAL 128
static char *trim(char *s) {               /* 去掉首尾空白(含行尾换行) */
    while (*s == ' ' || *s == '\t') s++;
    size_t len = strlen(s);
    while (len > 0 && (s[len - 1] == ' ' || s[len - 1] == '\t' ||
                       s[len - 1] == '\n' || s[len - 1] == '\r'))
        s[--len] = '\0';
    return s;
}
int main(void) {
    FILE *fp = fopen("app.conf", "r");
    if (fp == NULL) { perror("app.conf"); return 1; }
    char line[256];
    int  line_no = 0, loaded = 0;
    while (fgets(line, sizeof(line), fp) != NULL) {
        line_no++;
        char *s = trim(line);
        if (*s == '\0' || *s == '#') continue;       /* 空行/注释 */
        char *eq = strchr(s, '=');
        if (eq == NULL) {
            fprintf(stderr, "第 %d 行: 缺少 '=', 已忽略\n", line_no);
            continue;
        }
        *eq = '\0';                                  /* 拆成 key 与 value */
        char *key = trim(s);
        char *val = trim(eq + 1);
        if (*key == '\0' || *val == '\0') {
            fprintf(stderr, "第 %d 行: key 或 value 为空, 已忽略\n", line_no);
            continue;
        }
        if (strlen(key) >= MAX_KEY || strlen(val) >= MAX_VAL) {
            fprintf(stderr, "第 %d 行: 字段超长, 已忽略\n", line_no);
            continue;
        }
        printf("key=%-12s value=%s\n", key, val);
        loaded++;
    }
    if (ferror(fp)) { perror("读取失败"); fclose(fp); return 1; }
    fclose(fp);
    printf("共 %d 行, 成功解析 %d 条配置\n", line_no, loaded);
    return 0;
}
