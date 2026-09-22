// examples/ex05-mmap.c —— mmap/munmap/msync 与 mmap vs read 实测对比（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64，Apple Silicon 内置 SSD）
// 编译：cc -Wall -Wextra -std=c11 ex05-mmap.c -o ex05
// 运行：./ex05（演示文件写 /tmp/ph13-ex05-*.bin，运行后删除，退出码 0）
// 注意：耗时数字与机器相关，以下为本文档引用的一次实测值。
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
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

static void demo_readonly_mmap(void) {
    /* ---- 第 1 部分：只读 mmap 解析数据文件 ---- */
    const char *path = "/tmp/ph13-ex05-idx.bin";
    int fd = open(path, O_CREAT | O_TRUNC | O_RDWR, 0644);
    if (fd < 0)
        die("open");
    /* 文件布局: magic(u32, 主机序仅演示用) + count(u32) + count 个 u32 值 */
    unsigned hdr[2] = {0x31495844u /* "DIX1" */, 5};
    unsigned vals[5] = {10, 20, 30, 40, 50};
    if (write(fd, hdr, sizeof hdr) != (ssize_t)sizeof hdr ||
        write(fd, vals, sizeof vals) != (ssize_t)sizeof vals)
        die("write");
    if (fsync(fd) < 0)
        die("fsync");

    /* 取文件大小：mmap 需要长度；空文件（长度 0）mmap 会失败，要先检查 */
    struct stat st;
    if (fstat(fd, &st) < 0)
        die("fstat");
    printf("索引文件 %lld 字节\n", (long long)st.st_size);

    /* PROT_READ + MAP_SHARED：只读映射，内核按需从磁盘翻页进来 */
    unsigned *p = mmap(NULL, (size_t)st.st_size, PROT_READ, MAP_SHARED, fd, 0);
    if (p == MAP_FAILED)
        die("mmap");
    /* 映射建立后 fd 即可关闭，映射本身继续持有文件 */
    close(fd);

    if (p[0] != 0x31495844u) {
        printf("magic 不匹配!\n");
        munmap(p, (size_t)st.st_size);
        unlink(path);
        _exit(1);
    }
    unsigned count = p[1];
    unsigned long long sum = 0;
    for (unsigned i = 0; i < count; i++)
        sum += p[2 + i];              /* 像访问数组一样访问文件内容 */
    printf("magic 校验通过, %u 个值求和 = %llu（mmap 当数组读）\n", count, sum);

    munmap(p, (size_t)st.st_size);    /* 配对解除映射 */
    unlink(path);
}

static void demo_mmap_write_msync(void) {
    /* ---- 第 2 部分：MAP_SHARED 写 + msync 刷回 ---- */
    const char *path = "/tmp/ph13-ex05-rw.bin";
    int fd = open(path, O_CREAT | O_TRUNC | O_RDWR, 0644);
    if (fd < 0)
        die("open");
    if (ftruncate(fd, 4096) < 0)      /* 先撑出长度再映射 */
        die("ftruncate");

    char *m = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (m == MAP_FAILED)
        die("mmap rw");
    memcpy(m, "written via mmap", 16);   /* 直接改内存 = 改文件的 Page Cache */
    if (msync(m, 4096, MS_SYNC) < 0)     /* 等效 mmap 世界的 fsync */
        die("msync");
    munmap(m, 4096);

    char back[17] = {0};
    if (pread(fd, back, 16, 0) != 16)    /* 用 pread 验证真的写进了文件 */
        die("pread");
    printf("MAP_SHARED 写 + msync 后, pread 读回: \"%s\"\n", back);
    close(fd);
    unlink(path);
}

#define BENCH_MIB 256
static char rbuf[1024 * 1024];

static double bench_read(const char *path, unsigned long long *guard) {
    int fd = open(path, O_RDONLY);
    if (fd < 0)
        die("open bench read");
    double t0 = now_ms();
    ssize_t r;
    while ((r = read(fd, rbuf, sizeof rbuf)) > 0)
        for (ssize_t i = 0; i < r; i += 4096)   /* 每页摸一个字节: 强制每页都进缓存 */
            *guard += (unsigned char)rbuf[i];
    if (r < 0)
        die("read bench");
    close(fd);
    return now_ms() - t0;
}

static double bench_mmap(const char *path, unsigned long long *guard) {
    int fd = open(path, O_RDONLY);
    if (fd < 0)
        die("open bench mmap");
    size_t len = (size_t)BENCH_MIB * 1024 * 1024;
    volatile const unsigned char *p = mmap(NULL, len, PROT_READ, MAP_SHARED, fd, 0);
    if (p == MAP_FAILED)
        die("mmap bench");
    close(fd);
    double t0 = now_ms();
    for (size_t i = 0; i < len; i += 4096)      /* 每页摸一个字节: 触发缺页 */
        *guard += p[i];
    double cost = now_ms() - t0;
    munmap((void *)p, len);
    return cost;
}

int main(void) {
    demo_readonly_mmap();
    demo_mmap_write_msync();

    /* ---- 第 3 部分：mmap vs read 吞吐对比（256 MiB，逐页触摸求和） ---- */
    const char *path = "/tmp/ph13-ex05-big.bin";
    int fd = open(path, O_CREAT | O_TRUNC | O_WRONLY, 0644);
    if (fd < 0)
        die("open big");
    memset(rbuf, 0x5a, sizeof rbuf);
    for (int i = 0; i < BENCH_MIB; i++)
        if (write(fd, rbuf, sizeof rbuf) != (ssize_t)sizeof rbuf)
            die("write big");
    if (fsync(fd) < 0)
        die("fsync big");
    close(fd);

    unsigned long long g1 = 0, g2 = 0;
    double t_read = bench_read(path, &g1);      /* 第一遍：双方都是热缓存条件 */
    double t_mmap = bench_mmap(path, &g2);
    printf("\n扫 %d MiB（逐页触摸求和, 热缓存条件）:\n", BENCH_MIB);
    printf("  read(1 MiB 块): %.1f ms（%.0f MiB/s）\n",
           t_read, BENCH_MIB / (t_read / 1000.0));
    printf("  mmap 直接访问: %.1f ms（%.0f MiB/s）\n",
           t_mmap, BENCH_MIB / (t_mmap / 1000.0));
    printf("  两遍求和一致: %s\n", g1 == g2 ? "是" : "否");
    unlink(path);

    printf("\n结论: mmap 省去 read 的「内核→用户态」拷贝与每块一次系统调用;\n");
    printf("      代价是缺页异常处理与更复杂的错误模型（文件被截断访问会 SIGBUS）。\n");
    return 0;
}
