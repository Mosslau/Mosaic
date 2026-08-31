/* main.c —— 演示 + 自检
 * 4 个线程各写 200 条 INFO + 50 条 DEBUG; 默认级别 LOG_INFO 丢弃 DEBUG,
 * 期望落盘 4×200 + 主线程 2 条 = 802 行; 超过 MAX_LOG_SIZE 触发轮转,
 * 备份按序号递增(app.log.1, app.log.2, ...)不覆盖——"轮转不丢行"。
 * 自检: 读回 app.log 与全部备份文件, 校验每个文件头(magic/header_size),
 * 行数合计必须等于 802。
 *
 * 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64），-Wall -Wextra -std=c11 -pthread
 * 编译：make；运行/测试：make test（或 ./logdemo）
 * 验证状态：已验证（退出码 0, 输出"自检结果: 通过"）
 */
#include "log.h"

#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define THREADS          4
#define INFO_PER_THREAD  200 /* 每线程 200 条 INFO */
#define DEBUG_PER_THREAD 50  /* 每线程 50 条 DEBUG(会被级别过滤丢弃) */
#define EXPECT_LINES     (THREADS * INFO_PER_THREAD + 2) /* +主线程 2 条 */

static void *writer(void *arg) {
    int id = (int)(long)arg;
    for (int i = 0; i < INFO_PER_THREAD; i++)
        log_msg(LOG_INFO, "线程 %d 第 %d 条 INFO", id, i);
    for (int i = 0; i < DEBUG_PER_THREAD; i++)
        log_msg(LOG_DEBUG, "线程 %d 第 %d 条 DEBUG", id, i);
    return NULL;
}

/* 自检单个日志文件: 返回 0 不存在, 1 正常, -1 文件头/格式错误; lines 输出行数 */
static int check_file(const char *path, long *lines) {
    FILE *fp = fopen(path, "rb");
    if (fp == NULL)
        return 0;
    unsigned char hdr[12];
    if (fread(hdr, 1, 12, fp) != 12) { /* 不足 12 字节: 文件头缺失 */
        fclose(fp);
        return -1;
    }
    uint32_t magic; /* memcpy 读回数值, 同一机器上读写一致(字节序属 ph12) */
    uint16_t hsize;
    memcpy(&magic, hdr, 4);
    memcpy(&hsize, hdr + 6, 2);
    if (magic != 0x4C4F4731u || hsize != 12) {
        fclose(fp);
        return -1;
    }
    char line[512];
    long n = 0;
    while (fgets(line, sizeof line, fp) != NULL)
        n++;
    *lines = n;
    fclose(fp);
    return 1;
}

int main(void) {
    if (log_open("app.log") != 0) {
        fprintf(stderr, "log_open 失败\n");
        return 1;
    }
    log_set_level(LOG_INFO); /* 低于 INFO 的 DEBUG 被丢弃 */
    log_msg(LOG_INFO, "演示开始: %d 线程 × %d 条 INFO + %d 条 DEBUG(被过滤)",
            THREADS, INFO_PER_THREAD, DEBUG_PER_THREAD);
    pthread_t tids[THREADS];
    for (int i = 0; i < THREADS; i++)
        pthread_create(&tids[i], NULL, writer, (void *)(long)i);
    for (int i = 0; i < THREADS; i++)
        pthread_join(tids[i], NULL);
    log_msg(LOG_WARN, "轮转次数: %u", log_rotations());
    log_close();

    long total = 0;
    int all_ok = check_file("app.log", &total) > 0;
    for (unsigned i = 1; i <= log_rotations() && all_ok; i++) {
        char name[64];
        long n = 0;
        snprintf(name, sizeof name, "app.log.%u", i);
        if (check_file(name, &n) <= 0) {
            all_ok = 0;
            break;
        }
        total += n;
    }
    int ok = all_ok && total == EXPECT_LINES && log_rotations() >= 1;
    printf("轮转 %u 次, 全部日志文件行数合计: %ld (期望 %d)\n",
           log_rotations(), total, EXPECT_LINES);
    printf("自检结果: %s\n", ok ? "通过" : "失败");
    return ok ? 0 : 1;
}
