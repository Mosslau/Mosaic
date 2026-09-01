// examples/ex04-pagecache.c —— Page Cache 的存在与影响实测（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64，Apple Silicon 内置 SSD）
// 编译：cc -Wall -Wextra -std=c11 ex04-pagecache.c -o ex04
// 运行：./ex04（演示文件写 /tmp/ph13-ex04.bin，运行后删除，退出码 0）
// 注意：耗时数字与机器/内存压力相关，以下为本文档引用的一次实测值。
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

static double now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

static void die(const char *msg) {
    perror(msg);
    _exit(1);
}

#define FILE_MIB 256
static char wbuf[1024 * 1024];   /* 1 MiB 写缓冲 */
static char rbuf[1024 * 1024];   /* 1 MiB 读缓冲 */

/* 顺序读整个文件（只摸每块首字节，防止编译器优化掉 read 以外的循环） */
static double read_pass(int fd, unsigned long long *guard) {
    if (lseek(fd, 0, SEEK_SET) < 0)
        die("lseek");
    double t0 = now_ms();
    ssize_t r;
    while ((r = read(fd, rbuf, sizeof rbuf)) > 0)
        *guard += (unsigned char)rbuf[0];
    if (r < 0)
        die("read");
    return now_ms() - t0;
}

/* 把文件的缓存页失效（逼出 Page Cache），下次读只能去磁盘。
 * macOS 注意: fcntl(F_NOCACHE) 只影响"之后"的缓存行为、不逐出已缓存页,
 * 实测对本场景无效; msync(MS_SYNC|MS_INVALIDATE) 才会真正失效缓存页。
 * Linux 对应手段: posix_fadvise(POSIX_FADV_DONTNEED) 或 drop_caches。 */
static void evict_page_cache(int fd, size_t len) {
    void *m = mmap(NULL, len, PROT_READ, MAP_SHARED, fd, 0);
    if (m == MAP_FAILED)
        die("mmap");
    if (msync(m, len, MS_SYNC | MS_INVALIDATE) < 0)
        die("msync");
    munmap(m, len);
}

int main(void) {
    const char *path = "/tmp/ph13-ex04.bin";
    const size_t len = (size_t)FILE_MIB * 1024 * 1024;
    memset(wbuf, 0xa5, sizeof wbuf);

    /* ---- 第 1 部分：write 阶段 vs 刷盘阶段分开计时 ----
     * write 只是把数据拷进内核 Page Cache 就返回;
     * macOS 上 fsync 只到设备缓存, F_FULLFSYNC 才到介质（Linux fsync 即到介质）。 */
    int fd = open(path, O_CREAT | O_TRUNC | O_RDWR, 0644);
    if (fd < 0)
        die("open");
    double t0 = now_ms();
    for (int i = 0; i < FILE_MIB; i++)
        if (write(fd, wbuf, sizeof wbuf) != (ssize_t)sizeof wbuf)
            die("write");
    double write_ms = now_ms() - t0;

    t0 = now_ms();
    if (fsync(fd) < 0)
        die("fsync");
    double fsync_ms = now_ms() - t0;

#ifdef F_FULLFSYNC
    t0 = now_ms();
    if (fcntl(fd, F_FULLFSYNC) < 0)
        die("F_FULLFSYNC");
    double full_ms = now_ms() - t0;
#endif

    printf("写 %d MiB: write 阶段 %.1f ms（%.0f MiB/s —— 进了 Page Cache）\n",
           FILE_MIB, write_ms, FILE_MIB / (write_ms / 1000.0));
    printf("  fsync %.1f ms（macOS 上到设备缓存为止）\n", fsync_ms);
#ifdef F_FULLFSYNC
    printf("  F_FULLFSYNC %.1f ms（真正刷到介质的成本）\n", full_ms);
#endif

    /* ---- 第 2 部分：热读（Page Cache 命中）vs 冷读（缓存被逐出） ----
     * fsync 不清缓存，刚写完的文件读第一遍就是热读。 */
    unsigned long long g1 = 0, g2 = 0, g3 = 0;
    double warm1 = read_pass(fd, &g1);
    printf("热读（写完立即读, Page Cache 命中）: %.1f ms（%.0f MiB/s）\n",
           warm1, FILE_MIB / (warm1 / 1000.0));

    evict_page_cache(fd, len);
    double cold = read_pass(fd, &g2);
    printf("冷读（msync(MS_INVALIDATE) 逐出缓存后）: %.1f ms（%.0f MiB/s）\n",
           cold, FILE_MIB / (cold / 1000.0));

    double warm2 = read_pass(fd, &g3);
    printf("再热读（重新进了缓存）: %.1f ms（%.0f MiB/s）\n",
           warm2, FILE_MIB / (warm2 / 1000.0));

    printf("三遍数据一致: %s；Page Cache 命中加速约 %.1f 倍\n",
           (g1 == g2 && g2 == g3) ? "是" : "否", cold / warm1);

    close(fd);
    printf("\n结论: 基准测试里「刚写完就读」的吞吐是 Page Cache 的速度, 不是磁盘的速度;\n");
    printf("      评估真实 IO 性能必须先想清楚缓存是否命中。\n");
    unlink(path);
    return 0;
}
