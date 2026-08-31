/* main.c —— 演示 + 自检
 * 4 个线程各写 200 条 INFO + 50 条 DEBUG; 默认级别 LOG_INFO 丢弃 DEBUG,
 * 期望落盘 4×200 + 主线程 2 条 = 802 行; 超过 MAX_LOG_SIZE 触发轮转,
 * 备份序号跨运行单调递增(app.log.N 不覆盖上次运行的备份)——"轮转不丢行"。
 * 自检: 运行前先统计存量行数, 运行后统计 app.log 与全部备份文件的总行数,
 * 两者之差等于本轮写入 802 行即通过——连续运行互不影响; 同时校验每个
 * 文件头(magic/header_size)。
 *
 * 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64），-Wall -Wextra -std=c11 -pthread
 * 编译：make；运行/测试：make test（或 ./logdemo）
 * 验证状态：已验证（退出码 0, 连续运行自检均通过）
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

/* 统计 app.log 与全部备份文件的总行数(备份序号连续, 遇空缺即停);
 * 任一文件头不合法返回 -1 */
static long count_all_lines(void) {
    long total = 0;
    unsigned found = 0;
    for (unsigned i = 0; i < 1000000; i++) {
        char name[64];
        long n = 0;
        if (i == 0)
            snprintf(name, sizeof name, "app.log");
        else
            snprintf(name, sizeof name, "app.log.%u", i);
        int r = check_file(name, &n);
        if (r < 0)
            return -1; /* 文件头/格式错误 */
        if (r == 0) {
            if (i > 0 && found > 0 && i > found + 1)
                break; /* 备份序号连续, 遇空缺即停 */
            continue;
        }
        total += n;
        found = i;
    }
    return total;
}

int main(void) {
    long before = count_all_lines(); /* 运行前存量行数(上次运行的残留) */
    if (before < 0) {
        fprintf(stderr, "运行前日志文件校验失败\n");
        return 1;
    }
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

    long total = count_all_lines(); /* 运行后: 当前文件 + 全部备份 */
    long written = total - before;  /* 本轮新增行数(与存量无关) */
    int ok = total >= 0 && written == EXPECT_LINES && log_rotations() >= 1;
    printf("轮转 %u 次, 本轮新增行数: %ld (期望 %d, 文件合计 %ld)\n",
           log_rotations(), written, EXPECT_LINES, total);
    printf("自检结果: %s\n", ok ? "通过" : "失败");
    return ok ? 0 : 1;
}
