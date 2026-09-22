// examples/ex03-fsync.c —— fsync/fdatasync 的语义与耗时实测（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64，Apple Silicon 内置 SSD）
// 编译：cc -Wall -Wextra -std=c11 ex03-fsync.c -o ex03
// 运行：./ex03（演示文件写 /tmp/ph13-ex03-*.bin，运行后删除，退出码 0）
// 注意：耗时数字与机器/磁盘相关，以下为本文档引用的一次实测值；你的机器上
//       数量级关系一致、绝对值会不同。
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

/* CLOCK_MONOTONIC 毫秒计时（单调时钟，不受系统时间调整影响） */
static double now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

static void die(const char *msg) {
    perror(msg);
    _exit(1);
}

static int write_full(int fd, const void *buf, size_t n) {
    const char *p = buf;
    size_t left = n;
    while (left > 0) {
        ssize_t w = write(fd, p, left);
        if (w < 0)
            return -1;
        p += w;
        left -= (size_t)w;
    }
    return 0;
}

/* 写 nrec 条 128 字节 record；sync_every = 每多少条 fsync 一次（0 = 只在结尾 fsync 一次）。
 * 返回总耗时毫秒，flush_ms 返回所有刷盘调用的累计耗时。 */
static double bench(const char *path, int nrec, int sync_every, double *flush_ms) {
    int fd = open(path, O_CREAT | O_TRUNC | O_WRONLY, 0644);
    if (fd < 0)
        die("open");
    char rec[128];
    memset(rec, 'x', sizeof rec);

    double t0 = now_ms();
    double flush = 0.0;
    for (int i = 1; i <= nrec; i++) {
        if (write_full(fd, rec, sizeof rec) < 0)
            die("write");
        if (sync_every > 0 && i % sync_every == 0) {
            double f0 = now_ms();
            if (fsync(fd) < 0)
                die("fsync");
            flush += now_ms() - f0;
        }
    }
    /* 结尾统一 fsync：保证三种模式最终都落盘，也量出"最后这一刷"的成本 */
    double f0 = now_ms();
    if (fsync(fd) < 0)
        die("fsync");
    flush += now_ms() - f0;
    *flush_ms = flush;

    double total = now_ms() - t0;
    close(fd);
    unlink(path);
    return total;
}

int main(void) {
    /* ---- 第 1 部分：写 64 MiB 后，fsync 与 fdatasync 各花多久 ---- */
    const char *p1 = "/tmp/ph13-ex03-a.bin";
    const char *p2 = "/tmp/ph13-ex03-b.bin";
    static char big[1024 * 1024];          /* 1 MiB 缓冲 */
    memset(big, 0x5a, sizeof big);

    for (int round = 0; round < 2; round++) {
        const char *path = round == 0 ? p1 : p2;
        int fd = open(path, O_CREAT | O_TRUNC | O_WRONLY, 0644);
        if (fd < 0)
            die("open");
        for (int i = 0; i < 64; i++)        /* 64 × 1 MiB = 64 MiB */
            if (write_full(fd, big, sizeof big) < 0)
                die("write");
        double t0 = now_ms();
        int rc = round == 0 ? fsync(fd) : fdatasync(fd);
        double cost = now_ms() - t0;
        if (rc < 0)
            die(round == 0 ? "fsync" : "fdatasync");
        printf("写 64 MiB 后 %s() 耗时 %.1f ms\n",
               round == 0 ? "fsync" : "fdatasync", cost);
        close(fd);
        unlink(path);
    }

    /* ---- 第 2 部分：append 写 20000 条 128 字节 record，三种刷盘策略对比 ---- */
    const int nrec = 20000;
    printf("\nappend %d 条 x 128 字节 record（共 %.1f MiB）：\n",
           nrec, nrec * 128.0 / 1024 / 1024);

    double flush = 0.0;
    double t = bench("/tmp/ph13-ex03-c.bin", nrec, 0, &flush);
    printf("  只结尾 fsync 1 次: 总 %.1f ms（其中 flush %.1f ms），%.0f 条/秒\n",
           t, flush, nrec / (t / 1000.0));

    t = bench("/tmp/ph13-ex03-d.bin", nrec, 200, &flush);
    printf("  每 200 条 fsync:   总 %.1f ms（其中 flush %.1f ms），%.0f 条/秒\n",
           t, flush, nrec / (t / 1000.0));

    t = bench("/tmp/ph13-ex03-e.bin", nrec, 1, &flush);
    printf("  每条都 fsync:      总 %.1f ms（其中 flush %.1f ms），%.0f 条/秒\n",
           t, flush, nrec / (t / 1000.0));

    /* ---- 第 3 部分：macOS 的刷盘边界陷阱 —— fsync ≠ 真落盘 ----
     * POSIX fsync 只保证数据离开内核到达存储设备; macOS 上设备自身的
     * 写缓存不算"已持久化", 要 fcntl(F_FULLFSYNC) 才强制刷到介质。
     * （Linux 的 fsync 语义就是真落盘, 无此区分。） */
#ifdef F_FULLFSYNC
    printf("\nmacOS 刷盘边界对比（1000 次 4 KiB 写 + 每次刷盘）：\n");
    static char blk[4096];
    memset(blk, 'y', sizeof blk);
    for (int mode = 0; mode < 2; mode++) {
        int fd = open("/tmp/ph13-ex03-f.bin", O_CREAT | O_TRUNC | O_WRONLY, 0644);
        if (fd < 0)
            die("open");
        double flush2 = 0.0;
        for (int i = 0; i < 1000; i++) {
            if (write_full(fd, blk, sizeof blk) < 0)
                die("write");
            double f0 = now_ms();
            int rc = mode == 0 ? fsync(fd) : fcntl(fd, F_FULLFSYNC);
            if (rc < 0)
                die(mode == 0 ? "fsync" : "F_FULLFSYNC");
            flush2 += now_ms() - f0;
        }
        printf("  每次 %s: flush 累计 %.1f ms，%.0f 次/秒\n",
               mode == 0 ? "fsync      " : "F_FULLFSYNC",
               flush2, 1000.0 / (flush2 / 1000.0));
        close(fd);
        unlink("/tmp/ph13-ex03-f.bin");
    }
    printf("（F_FULLFSYNC 比 fsync 慢两个数量级 —— 后者才是真刷到介质的成本;\n");
    printf("  Linux 的 fsync 本身就是真落盘语义, 没有这一层区别。）\n");
#else
    printf("\n（非 macOS 平台：Linux 的 fsync 即真落盘语义，无 F_FULLFSYNC 对比。）\n");
#endif

    printf("\n结论: write 把数据交给内核 Page Cache 就返回（快）;\n");
    printf("      fsync 等数据到达存储设备（慢，次数与耗时近似成正比）;\n");
    printf("      fdatasync 不刷元数据（mtime 等），语义足够时比 fsync 便宜。\n");
    return 0;
}
