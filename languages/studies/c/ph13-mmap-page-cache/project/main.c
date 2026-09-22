/* main.c —— kvlog 命令行工具与自测
 *
 * 用法：
 *   kvlog write <file> <n>            写 n 条记录, 结尾 fsync
 *   kvlog read  <file>                回放（报告完整记录数与残尾）
 *   kvlog bench <file> <n> <every>    压测：每 every 条 fsync（0 = 只结尾刷）
 *   kvlog crash <file>                崩溃演示：fork 子进程真实 SIGKILL 后回放
 *   kvlog torn  <file>                残尾演示：半写入 → 检测 → ftruncate 修复
 *   kvlog corrupt <file> <offset>     损坏演示：翻转 1 字节后回放（CRC 拦截）
 *   kvlog test                        自测套件（往返/残尾/损坏/magic, 退出码即结果）
 */
#include "kvl.h"

#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static double now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

/* 第 i 条 record 的 payload 内容与长度（写回 buf）。测试里按同一规则
 * 反推记录边界，所以写与算必须共用这一个函数，不得各写一份。 */
static int make_payload(int i, char *buf, size_t cap) {
    return snprintf(buf, cap, "op-%06d SET user:%d=score:%d", i, i, i * 7 % 100);
}

/* 往 fd 写 n 条 "op-%06d ..." 记录；每 every 条 fsync（0 = 不刷，调用方负责）。
 * 返回总耗时 ms，*flush_ms 输出刷盘累计耗时。失败返回 -1。 */
static double write_records(int fd, int n, int every, double *flush_ms) {
    double t0 = now_ms();
    double flush = 0.0;
    for (int i = 1; i <= n; i++) {
        char payload[64];
        int plen = make_payload(i, payload, sizeof payload);
        if (kvl_append(fd, payload, (uint32_t)plen) < 0)
            return -1;
        if (every > 0 && i % every == 0) {
            double f0 = now_ms();
            if (kvl_sync(fd) < 0)
                return -1;
            flush += now_ms() - f0;
        }
    }
    *flush_ms = flush;
    return now_ms() - t0;
}

static int cmd_write(const char *path, int n) {
    int fd = kvl_open_append(path);
    if (fd < 0) {
        perror("open");
        return 1;
    }
    double flush = 0.0;
    if (write_records(fd, n, 0, &flush) < 0) {
        perror("write");
        close(fd);
        return 1;
    }
    if (kvl_sync(fd) < 0) {
        perror("fsync");
        close(fd);
        return 1;
    }
    close(fd);
    printf("写入 %d 条记录并 fsync\n", n);
    return 0;
}

static int cmd_read(const char *path) {
    int count = 0;
    off_t torn_at = 0;
    kvl_end_t end = kvl_replay(path, NULL, NULL, &count, &torn_at);
    if (end == KVL_END_IOERR) {
        perror("replay");
        return 1;
    }
    printf("回放 %d 条完整记录", count);
    if (end == KVL_END_TORN)
        printf("，残尾在偏移 %lld（损坏/截断记录被安全跳过）", (long long)torn_at);
    printf("\n");
    return end == KVL_END_TORN ? 2 : 0;
}

static int cmd_bench(const char *path, int n, int every) {
    int fd = open(path, O_CREAT | O_TRUNC | O_WRONLY | O_APPEND, 0644);
    if (fd < 0) {
        perror("open");
        return 1;
    }
    double flush = 0.0;
    double total = write_records(fd, n, every, &flush);
    if (total < 0) {
        perror("bench write");
        close(fd);
        return 1;
    }
    /* 结尾统一 fsync：所有模式最终都落盘，flush 计入 */
    double f0 = now_ms();
    if (kvl_sync(fd) < 0) {
        perror("fsync");
        close(fd);
        return 1;
    }
    flush += now_ms() - f0;
    close(fd);
    printf("bench: %d 条, fsync 每 %s 条 → 总 %.1f ms（flush %.1f ms），%.0f 条/秒\n",
           n, every == 0 ? "仅结尾" : "N", total, flush, n / (total / 1000.0));
    if (every > 0)
        printf("       （每 %d 条刷一次）\n", every);
    return 0;
}

/* 崩溃演示：子进程写 2000 条（每 200 条 fsync）+ 半条残记录, 然后真实 SIGKILL */
static int cmd_crash(const char *path) {
    int fd = open(path, O_CREAT | O_TRUNC | O_RDWR, 0644);
    if (fd < 0) {
        perror("open");
        return 1;
    }
    close(fd);

    pid_t pid = fork();
    if (pid < 0) {
        perror("fork");
        return 1;
    }
    if (pid == 0) {
        int wfd = kvl_open_append(path);
        if (wfd < 0)
            _exit(2);
        double flush = 0.0;
        if (write_records(wfd, 2000, 200, &flush) < 0)
            _exit(2);
        /* 第 2001 条只写半个头部就"崩溃"（半写入） */
        uint8_t half[6] = {0x4B, 0x56, 0x4C, 0x31, 0, 0};
        if (write(wfd, half, sizeof half) != (ssize_t)sizeof half)
            _exit(2);
        kill(getpid(), SIGKILL);        /* 真实 kill -9：不走任何退出流程 */
        _exit(0);
    }

    int status = 0;
    waitpid(pid, &status, 0);
    if (!(WIFSIGNALED(status) && WTERMSIG(status) == SIGKILL)) {
        printf("子进程死因异常\n");
        return 1;
    }
    printf("子进程写完 2000 条 + 半条残记录后被 SIGKILL（真实 kill -9）\n");

    int count = 0;
    off_t torn_at = 0;
    kvl_end_t end = kvl_replay(path, NULL, NULL, &count, &torn_at);
    printf("崩溃后回放：恢复 %d/2000 条，残尾在偏移 %lld\n",
           count, (long long)torn_at);
    printf("进程崩溃没丢数据（Page Cache 属内核）；断电才丢 —— 那是 fsync 防的\n");

    if (kvl_repair(path, torn_at) < 0) {
        perror("repair");
        return 1;
    }
    int count2 = 0;
    off_t torn2 = 0;
    kvl_end_t end2 = kvl_replay(path, NULL, NULL, &count2, &torn2);
    printf("ftruncate 修复后回放：%d 条，%s\n",
           count2, end2 == KVL_END_CLEAN ? "已恢复干净状态" : "仍有残尾!");
    return (end == KVL_END_TORN && count == 2000 && end2 == KVL_END_CLEAN) ? 0 : 1;
}

/* 残尾演示：10 条 + fsync，再写半条，检测并修复 */
static int cmd_torn(const char *path) {
    int fd = open(path, O_CREAT | O_TRUNC | O_WRONLY | O_APPEND, 0644);
    if (fd < 0) {
        perror("open");
        return 1;
    }
    double flush = 0.0;
    if (write_records(fd, 10, 0, &flush) < 0 || kvl_sync(fd) < 0) {
        perror("write");
        close(fd);
        return 1;
    }
    uint8_t half[5] = {0x4B, 0x56, 0x4C, 0x31, 0};   /* 半条头部 */
    if (write(fd, half, sizeof half) != (ssize_t)sizeof half) {
        perror("write half");
        close(fd);
        return 1;
    }
    close(fd);
    printf("写入 10 条 + fsync，再模拟半写入（5 字节残头部）\n");
    return cmd_read(path) == 2 ? 0 : 1;
}

/* 损坏演示：翻转指定偏移的 1 字节，回放应被 CRC 拦在该记录处 */
static int cmd_corrupt(const char *path, off_t off) {
    int fd = open(path, O_RDWR);
    if (fd < 0) {
        perror("open");
        return 1;
    }
    uint8_t b;
    if (pread(fd, &b, 1, off) != 1) {
        perror("pread");
        close(fd);
        return 1;
    }
    b ^= 0xFF;
    if (pwrite(fd, &b, 1, off) != 1) {
        perror("pwrite");
        close(fd);
        return 1;
    }
    close(fd);
    printf("已翻转偏移 %lld 的字节，回放：\n", (long long)off);
    return cmd_read(path) == 2 ? 0 : 1;
}

/* ---------------- 自测 ---------------- */
static int failures = 0;
#define CHECK(cond, name) do {                                   \
        if (cond) {                                              \
            printf("[PASS] %s\n", name);                         \
        } else {                                                 \
            printf("[FAIL] %s (%s:%d)\n", name, __FILE__, __LINE__); \
            failures++;                                          \
        }                                                        \
    } while (0)

static int count_visit(const uint8_t *payload, uint32_t len, void *ctx) {
    (void)payload;
    (void)len;
    int *c = ctx;
    (*c)++;
    return 0;
}

static int cmd_test(void) {
    const char *path = "/tmp/kvlog-test.log";

    /* 1. 往返：写 100 条 → 回放 100 条干净 */
    int fd = open(path, O_CREAT | O_TRUNC | O_WRONLY | O_APPEND, 0644);
    CHECK(fd >= 0, "open 测试文件");
    double flush = 0.0;
    CHECK(write_records(fd, 100, 0, &flush) >= 0, "写 100 条记录");
    CHECK(kvl_sync(fd) == 0, "fsync");
    close(fd);
    int count = 0, visited = 0;
    off_t torn_at = 0;
    kvl_end_t end = kvl_replay(path, count_visit, &visited, &count, &torn_at);
    CHECK(end == KVL_END_CLEAN && count == 100 && visited == 100,
          "往返：回放 100 条干净");

    /* 2. 残尾：追加半个头部 → KVL_END_TORN 停在准确偏移 → 修复后干净 */
    off_t clean_end = torn_at;
    fd = kvl_open_append(path);
    CHECK(fd >= 0, "以 O_APPEND 重开");
    uint8_t half[7] = {0x4B, 0x56, 0x4C, 0x31, 0, 0, 0};
    CHECK(write(fd, half, sizeof half) == (ssize_t)sizeof half, "写入残头部");
    close(fd);
    end = kvl_replay(path, NULL, NULL, &count, &torn_at);
    CHECK(end == KVL_END_TORN && count == 100 && torn_at == clean_end,
          "残尾：停在准确偏移");
    CHECK(kvl_repair(path, torn_at) == 0, "ftruncate 修复");
    end = kvl_replay(path, NULL, NULL, &count, &torn_at);
    CHECK(end == KVL_END_CLEAN && count == 100, "修复后回放干净");

    /* 3. 损坏：翻转第 50 条 payload 一字节 → 停在第 50 条前。
     * payload 长度随 i 位数变化（i=1 是 28 字节, i=2..9 是 29, i>=10 是 30），
     * 不能假设定长——按 make_payload 反推前 49 条的真实边界。 */
    fd = open(path, O_RDWR);
    CHECK(fd >= 0, "可写重开");
    off_t rec50 = (off_t)KVL_HDR_SIZE;      /* 记录 1 的 payload 起点 */
    for (int i = 1; i < 50; i++) {
        char pbuf[64];
        int plen = make_payload(i, pbuf, sizeof pbuf);
        rec50 += (off_t)KVL_HDR_SIZE + plen; /* 累加 49 条 → 记录 50 的 payload 起点 */
    }
    uint8_t b = 0;
    CHECK(pread(fd, &b, 1, rec50) == 1, "读出待翻转字节");
    b ^= 0xFF;
    CHECK(pwrite(fd, &b, 1, rec50) == 1, "翻转 1 字节");
    close(fd);
    end = kvl_replay(path, NULL, NULL, &count, &torn_at);
    CHECK(end == KVL_END_TORN && count == 49, "损坏：CRC 拦截在第 50 条");

    /* 4. 非本格式：全零文件 → 0 条 + TORN(magic 不符) */
    fd = open(path, O_CREAT | O_TRUNC | O_WRONLY, 0644);
    CHECK(fd >= 0, "重建文件");
    uint8_t zeros[64] = {0};
    CHECK(write(fd, zeros, sizeof zeros) == (ssize_t)sizeof zeros, "写全零垃圾");
    close(fd);
    end = kvl_replay(path, NULL, NULL, &count, &torn_at);
    CHECK(end == KVL_END_TORN && count == 0 && torn_at == 0,
          "非本格式：magic 拦截在偏移 0");

    unlink(path);
    printf("自测结束：%s（%d 个失败）\n", failures == 0 ? "全部通过" : "有失败", failures);
    return failures == 0 ? 0 : 1;
}

static void usage(const char *prog) {
    fprintf(stderr,
            "用法：\n"
            "  %s write <file> <n>            写 n 条记录, 结尾 fsync\n"
            "  %s read  <file>                回放\n"
            "  %s bench <file> <n> <every>    压测：每 every 条 fsync（0=只结尾刷）\n"
            "  %s crash <file>                崩溃演示（真实 SIGKILL + 回放 + 修复）\n"
            "  %s torn  <file>                残尾演示（半写入 → 检测）\n"
            "  %s corrupt <file> <offset>     损坏演示（翻转 1 字节 → CRC 拦截）\n"
            "  %s test                        自测套件\n",
            prog, prog, prog, prog, prog, prog, prog);
}

int main(int argc, char **argv) {
    if (argc >= 2 && strcmp(argv[1], "test") == 0)
        return cmd_test();
    if (argc == 4 && strcmp(argv[1], "write") == 0)
        return cmd_write(argv[2], atoi(argv[3]));
    if (argc == 3 && strcmp(argv[1], "read") == 0)
        return cmd_read(argv[2]);
    if (argc == 5 && strcmp(argv[1], "bench") == 0)
        return cmd_bench(argv[2], atoi(argv[3]), atoi(argv[4]));
    if (argc == 3 && strcmp(argv[1], "crash") == 0)
        return cmd_crash(argv[2]);
    if (argc == 3 && strcmp(argv[1], "torn") == 0)
        return cmd_torn(argv[2]);
    if (argc == 4 && strcmp(argv[1], "corrupt") == 0)
        return cmd_corrupt(argv[2], (off_t)atoll(argv[3]));
    usage(argv[0]);
    return 64; /* EX_USAGE */
}
