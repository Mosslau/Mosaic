// examples/ex06-append-only.c —— append-only 日志：O_APPEND 追加 + 截断尾检测回放（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
// 编译：cc -Wall -Wextra -std=c11 ex06-append-only.c -o ex06
// 运行：./ex06（演示文件写 /tmp/ph13-ex06.log，运行后删除，退出码 0）
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

/* ---- 记录格式（多字节字段显式大端, 衔接 ph12）----
 * [len: u32][crc32: u32][payload: len 字节]，头部 8 字节。
 * crc 覆盖 payload；len 超上限 / 字节不够 / crc 不符 = 损坏或截断。 */
#define HDR_SIZE 8u
#define MAX_PAYLOAD (1024u * 1024u)

static uint32_t crc32(const uint8_t *data, size_t len) {
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int b = 0; b < 8; b++)
            crc = (crc >> 1) ^ ((crc & 1u) ? 0xEDB88320u : 0u);
    }
    return ~crc;
}

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

/* 追加一条记录。fd 以 O_APPEND 打开：每次 write 原子地落到文件末尾,
 * 不受其他写者影响（这是 append-only 多进程安全的根基）。 */
static int log_append(int fd, const void *payload, uint32_t len) {
    if (len > MAX_PAYLOAD)
        return -1;
    uint8_t hdr[HDR_SIZE];
    write_be32(hdr, len);
    write_be32(hdr + 4, crc32(payload, len));
    if (write_full(fd, hdr, sizeof hdr) < 0)
        return -1;
    if (write_full(fd, payload, len) < 0)
        return -1;
    return 0;
}

/* 回放：顺序解析，遇到损坏/截断即停（append-only 的恢复点 =
 * 最后一个完整记录的末尾）。返回完整记录数，*torn_at 输出损坏点偏移
 * （无损坏则 = 文件大小）。 */
static int log_replay(int fd, off_t *torn_at) {
    uint8_t hdr[HDR_SIZE];
    static uint8_t payload[MAX_PAYLOAD];
    int count = 0;
    off_t off = 0;
    for (;;) {
        ssize_t r = pread(fd, hdr, HDR_SIZE, off);
        if (r < 0)
            return -1;
        if (r == 0)
            break;                       /* 干净 EOF */
        if (r < (ssize_t)HDR_SIZE)
            goto torn;                   /* 头部没写全 = 截断 */
        uint32_t len = read_be32(hdr);
        uint32_t crc = read_be32(hdr + 4);
        if (len > MAX_PAYLOAD)
            goto torn;                   /* 长度非法 = 损坏 */
        r = pread(fd, payload, len, off + HDR_SIZE);
        if (r < 0)
            return -1;
        if (r < (ssize_t)len)
            goto torn;                   /* payload 没写全 = 截断 */
        if (crc32(payload, len) != crc)
            goto torn;                   /* 半写入/位翻转 = 损坏 */
        count++;
        off += (off_t)HDR_SIZE + len;
    }
    *torn_at = off;
    return count;
torn:
    *torn_at = off;
    printf("  回放停在偏移 %lld（损坏/截断记录被安全跳过）\n", (long long)off);
    return count;
}

int main(void) {
    const char *path = "/tmp/ph13-ex06.log";
    const char *msgs[] = {
        "PUT name=mosslau", "PUT lang=c", "DEL name",
        "PUT lang=tenet", "PUT ver=13"
    };
    const int n = 5;

    /* ① 追加写 5 条 + 结尾 fsync */
    int fd = open(path, O_CREAT | O_TRUNC | O_WRONLY | O_APPEND, 0644);
    if (fd < 0) {
        perror("open");
        return 1;
    }
    for (int i = 0; i < n; i++)
        if (log_append(fd, msgs[i], (uint32_t)strlen(msgs[i])) < 0) {
            perror("log_append");
            return 1;
        }
    if (fsync(fd) < 0) {                 /* 刷盘边界：这 5 条承诺持久 */
        perror("fsync");
        return 1;
    }
    close(fd);
    printf("① 追加 %d 条记录并 fsync\n", n);

    /* ② 模拟崩溃造成的半写入：只写一条记录的前 3 个字节就"断电" */
    fd = open(path, O_WRONLY | O_APPEND);
    if (fd < 0) {
        perror("open torn");
        return 1;
    }
    uint8_t partial[3] = {0, 0, 0};      /* len 字段的前 3 字节 */
    if (write_full(fd, partial, sizeof partial) < 0) {
        perror("write torn");
        return 1;
    }
    close(fd);
    printf("② 模拟半写入：追加一条只写了 3 字节头部的残记录\n");

    /* ③ 回放：完整记录全部恢复，残尾被安全识别 */
    fd = open(path, O_RDONLY);
    if (fd < 0) {
        perror("open replay");
        return 1;
    }
    off_t torn_at = 0;
    int ok = log_replay(fd, &torn_at);
    printf("③ 回放结果：恢复 %d 条完整记录\n", ok);

    /* ④ 修复：ftruncate 砍掉残尾，文件回到可继续追加的状态 */
    close(fd);                           /* 回放 fd 是 O_RDONLY，修复要换可写 fd */
    fd = open(path, O_WRONLY);
    if (fd < 0) {
        perror("open repair");
        return 1;
    }
    if (ftruncate(fd, torn_at) < 0) {
        perror("ftruncate");
        return 1;
    }
    close(fd);
    printf("④ ftruncate 到 %lld 修复残尾，文件可继续安全追加\n", (long long)torn_at);

    unlink(path);
    printf("\n要点: append-only + 尾部校验, 让「崩溃只留下最后一条残记录」;\n");
    printf("      残记录被长度/CRC 识别, 截掉即恢复 —— 这就是 WAL 的恢复原理。\n");
    return 0;
}
