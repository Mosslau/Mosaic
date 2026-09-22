// 来源：06-file-io.md 第 6 章示例 5 —— append-only 日志文件
// 参考实现复用自 examples/ex05-append-log.c（题解分离：题目见 README.md）
// 对应 roadmap 练习"日志系统"与推荐项目"append-only 数据文件"
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99 零警告
// 编译：gcc -Wall -Wextra -std=c99 ex05-append-log.c -o ex05-append-log
// 运行：./ex05-append-log   （生成 app.log；运行产物验证后清理）
// 验证状态：已验证
#include <stdio.h>
#include <time.h>
static int log_write(const char *path, const char *msg) {
    FILE *fp = fopen(path, "a");         /* "a": 每次写入前定位到末尾 */
    if (fp == NULL) { perror(path); return -1; }
    time_t now = time(NULL);
    struct tm *t = localtime(&now);
    if (fprintf(fp, "%04d-%02d-%02d %02d:%02d:%02d  %s\n",
                t->tm_year + 1900, t->tm_mon + 1, t->tm_mday,
                t->tm_hour, t->tm_min, t->tm_sec, msg) < 0) {
        fclose(fp);
        return -1;
    }
    if (fflush(fp) != 0) {               /* 用户态缓冲 → 内核 */
        perror("fflush");
        fclose(fp);
        return -1;
    }
    fclose(fp);
    return 0;
}
int main(void) {
    const char *path = "app.log";
    log_write(path, "server start");
    log_write(path, "user login: alice");
    log_write(path, "order created: #1001");
    printf("日志已追加写入 %s\n", path);
    return 0;
}
