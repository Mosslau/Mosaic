/* sol-02-append-log.c —— 参考实现: 实现 append-only log
 * 布局: [len: u32 大端][payload: len 字节]，O_APPEND 追加写, 结尾 fsync。
 * 要点: O_APPEND 让每次 write 原子落到文件末尾（多进程追加互不覆盖）;
 *   write 成功只代表进了 Page Cache, fsync 之后才谈持久化。
 * 实测: 追加 3 条, fsync 后回放 3 条全部一致; 文件共 31 字节。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-02-append-log.c -o sol02
// 运行：./sol02（写 /tmp/ph13-sol02.log 后删除, 退出码 0）
// 验证状态：已验证（-Wall -Wextra 零警告; 实测输出见文件尾注释）
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#define MAX_PAYLOAD 65536u

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

static int log_append(int fd, const char *msg) {
    uint32_t len = (uint32_t)strlen(msg);
    uint8_t hdr[4];
    write_be32(hdr, len);
    if (write_full(fd, hdr, 4) < 0)
        return -1;
    if (write_full(fd, msg, len) < 0)
        return -1;
    return 0;
}

int main(void) {
    const char *path = "/tmp/ph13-sol02.log";
    const char *ops[] = {"SET a=1", "SET b=2", "DEL a"};

    /* 写：O_APPEND 追加, 结尾一次 fsync */
    int fd = open(path, O_CREAT | O_TRUNC | O_WRONLY | O_APPEND, 0644);
    if (fd < 0) {
        perror("open");
        return 1;
    }
    for (int i = 0; i < 3; i++)
        if (log_append(fd, ops[i]) < 0) {
            perror("log_append");
            return 1;
        }
    if (fsync(fd) < 0) {
        perror("fsync");
        return 1;
    }
    printf("追加 3 条并 fsync（write 只到 Page Cache, fsync 后才持久）\n");
    close(fd);

    /* 读：顺序回放到 EOF */
    fd = open(path, O_RDONLY);
    if (fd < 0) {
        perror("open replay");
        return 1;
    }
    int count = 0;
    for (;;) {
        uint8_t hdr[4];
        ssize_t r = read(fd, hdr, 4);
        if (r == 0)
            break;                          /* EOF */
        if (r != 4) {
            printf("头部短读: 截断!\n");
            return 1;
        }
        uint32_t len = read_be32(hdr);
        if (len > MAX_PAYLOAD) {
            printf("长度非法: 损坏!\n");
            return 1;
        }
        char buf[MAX_PAYLOAD + 1];
        if (read(fd, buf, len) != (ssize_t)len) {
            printf("payload 短读: 截断!\n");
            return 1;
        }
        buf[len] = '\0';
        printf("record %d: \"%s\"\n", count, buf);
        count++;
    }
    printf("回放 %d 条, 文件共 %lld 字节\n", count, (long long)lseek(fd, 0, SEEK_END));
    close(fd);
    unlink(path);
    return 0;
}

/* 实测输出（本机一次运行）：
 * 追加 3 条并 fsync（write 只到 Page Cache, fsync 后才持久）
 * record 0: "SET a=1"
 * record 1: "SET b=2"
 * record 2: "DEL a"
 * 回放 3 条, 文件共 31 字节
 */
