/* sol-03-mmap-readonly.c —— 参考实现: 用 mmap 读取只读数据文件
 * 布局（大端）: magic("IDX1", 4) + count(u32, 4) + count 个 u32 值
 * 要点: 只读场景 mmap(PROT_READ) 把文件当数组访问, 内核按需翻页;
 *   两个必须先检查的坑: ① 空文件（长度 0）mmap 直接失败;
 *   ② 文件长度要先校验（magic/count 字段都要在长度范围内）再访问。
 * 实测: 100000 个值求和 = 5000050000, 与公式 n(n+1)/2 一致;
 *   空文件路径正确走「长度不足」分支（没有崩溃）。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-03-mmap-readonly.c -o sol03
// 运行：./sol03（写 /tmp/ph13-sol03*.bin 后删除, 退出码 0）
// 验证状态：已验证（-Wall -Wextra 零警告; 实测输出见文件尾注释）
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

static void write_be32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24);
    p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8);
    p[3] = (uint8_t)v;
}

static uint32_t read_be32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}

/* mmap 只读扫描：返回 0 成功（*sum 输出）, 1 格式非法, -1 系统错误 */
static int mmap_sum(const char *path, unsigned long long *sum, uint32_t *count_out) {
    int fd = open(path, O_RDONLY);
    if (fd < 0)
        return -1;
    struct stat st;
    if (fstat(fd, &st) < 0) {
        close(fd);
        return -1;
    }
    /* ① 长度先校验：空文件/超小文件不能 mmap 也没有头部可读 */
    if (st.st_size < 8) {
        printf("  %s: 长度 %lld 不足头部（8 字节）, 拒绝\n",
               path, (long long)st.st_size);
        close(fd);
        return 1;
    }
    size_t len = (size_t)st.st_size;
    const uint8_t *p = mmap(NULL, len, PROT_READ, MAP_SHARED, fd, 0);
    if (p == MAP_FAILED) {
        close(fd);
        return -1;
    }
    close(fd);                            /* 映射建立后 fd 可关 */

    if (memcmp(p, "IDX1", 4) != 0) {      /* ② magic 校验 */
        munmap((void *)p, len);
        return 1;
    }
    uint32_t count = read_be32(p + 4);
    /* ③ count 与文件实际长度必须吻合：不信任文件里的长度声明 */
    if ((uint64_t)8 + (uint64_t)count * 4 != (uint64_t)len) {
        printf("  count=%u 与文件长度 %zu 不符, 拒绝\n", count, len);
        munmap((void *)p, len);
        return 1;
    }
    *sum = 0;
    for (uint32_t i = 0; i < count; i++)
        *sum += read_be32(p + 8 + (size_t)i * 4);
    *count_out = count;
    munmap((void *)p, len);
    return 0;
}

int main(void) {
    const char *path = "/tmp/ph13-sol03.bin";
    const uint32_t n = 100000;

    /* 生成数据文件: 值 = 1..n */
    int fd = open(path, O_CREAT | O_TRUNC | O_WRONLY, 0644);
    if (fd < 0) {
        perror("open");
        return 1;
    }
    uint8_t hdr[8];
    memcpy(hdr, "IDX1", 4);
    write_be32(hdr + 4, n);
    if (write(fd, hdr, 8) != 8) {
        perror("write hdr");
        return 1;
    }
    for (uint32_t i = 1; i <= n; i++) {
        uint8_t b[4];
        write_be32(b, i);
        if (write(fd, b, 4) != 4) {
            perror("write val");
            return 1;
        }
    }
    close(fd);

    printf("== mmap 只读扫描 ==\n");
    unsigned long long sum = 0;
    uint32_t count = 0;
    int rc = mmap_sum(path, &sum, &count);
    if (rc != 0) {
        printf("解析失败 rc=%d\n", rc);
        return 1;
    }
    printf("count=%u, sum=%llu（公式核对 n(n+1)/2=%llu: %s）\n",
           count, sum, (unsigned long long)n * (n + 1) / 2,
           sum == (unsigned long long)n * (n + 1) / 2 ? "一致" : "不一致");
    unlink(path);

    /* 空文件也必须安全拒绝（mmap 长度 0 会失败, 先查长度就不会走到 mmap） */
    const char *empty = "/tmp/ph13-sol03-empty.bin";
    fd = open(empty, O_CREAT | O_TRUNC | O_WRONLY, 0644);
    if (fd < 0) {
        perror("open empty");
        return 1;
    }
    close(fd);
    printf("== 空文件边界 ==\n");
    rc = mmap_sum(empty, &sum, &count);
    printf("空文件: rc=%d（安全拒绝, 未崩溃）\n", rc);
    unlink(empty);
    return 0;
}

/* 实测输出（本机一次运行）：
 * == mmap 只读扫描 ==
 * count=100000, sum=5000050000（公式核对 n(n+1)/2=5000050000: 一致）
 * == 空文件边界 ==
 *   /tmp/ph13-sol03-empty.bin: 长度 0 不足头部（8 字节）, 拒绝
 * 空文件: rc=1（安全拒绝, 未崩溃）
 */
