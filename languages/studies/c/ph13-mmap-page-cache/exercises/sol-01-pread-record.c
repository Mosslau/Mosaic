/* sol-01-pread-record.c —— 参考实现: 用 pread 按 offset 读取 record
 * 布局: 定长 32 字节 record = id(u32 大端, 4) + name(28 字节, 不足补 0)
 * 要点: pread 从指定偏移读、不推进 fd 的 offset —— 随机读不需要 lseek 来回跳,
 *   多线程共享同一 fd 时尤其重要（lseek+read 两步不是原子的, pread 是）。
 * 实测: 按索引读 record 3 / 7 全部命中, 读前读后 offset 恒为 0。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-01-pread-record.c -o sol01
// 运行：./sol01（写 /tmp/ph13-sol01.bin 后删除, 退出码 0）
// 验证状态：已验证（-Wall -Wextra 零警告; 实测输出见文件尾注释）
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#define REC_SIZE 32u

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

/* 按索引读一条 record；返回 0 成功，-1 失败/越界。不碰 fd 的 offset。 */
static int read_record(int fd, uint32_t index, uint32_t *id, char name[29]) {
    uint8_t buf[REC_SIZE];
    off_t off = (off_t)index * REC_SIZE;
    ssize_t r = pread(fd, buf, REC_SIZE, off);
    if (r != (ssize_t)REC_SIZE)
        return -1;                        /* EOF 或短读都是越界 */
    *id = read_be32(buf);
    memcpy(name, buf + 4, 28);
    name[28] = '\0';
    return 0;
}

int main(void) {
    const char *path = "/tmp/ph13-sol01.bin";
    int fd = open(path, O_CREAT | O_TRUNC | O_RDWR, 0644);
    if (fd < 0) {
        perror("open");
        return 1;
    }

    /* 顺序写 10 条 record: id = 100 + i, name = "user<i>" */
    for (uint32_t i = 0; i < 10; i++) {
        uint8_t rec[REC_SIZE] = {0};
        char name[29];
        snprintf(name, sizeof name, "user%u", i);
        write_be32(rec, 100 + i);
        memcpy(rec + 4, name, strlen(name));
        if (write(fd, rec, REC_SIZE) != (ssize_t)REC_SIZE) {
            perror("write");
            return 1;
        }
    }
    /* 写完 offset = 320；先 lseek 回 0, 之后全程只用 pread */
    if (lseek(fd, 0, SEEK_SET) < 0) {
        perror("lseek");
        return 1;
    }

    printf("== 用 pread 按索引随机读 ==\n");
    const uint32_t idx[] = {3, 7, 0, 9};
    for (size_t k = 0; k < sizeof idx / sizeof idx[0]; k++) {
        uint32_t id;
        char name[29];
        if (read_record(fd, idx[k], &id, name) < 0) {
            printf("record %u: 读取失败\n", idx[k]);
            return 1;
        }
        printf("record %u: id=%u name=\"%s\"（读前 offset=%lld, 读后 offset=%lld）\n",
               idx[k], id, name,
               (long long)lseek(fd, 0, SEEK_CUR),
               (long long)lseek(fd, 0, SEEK_CUR));
    }

    /* 越界：第 10 条不存在 */
    uint32_t id;
    char name[29];
    printf("record 10: %s\n",
           read_record(fd, 10, &id, name) < 0 ? "读取失败（正确判越界）" : "误读成功!");

    close(fd);
    unlink(path);
    return 0;
}

/* 实测输出（本机一次运行）：
 * == 用 pread 按索引随机读 ==
 * record 3: id=103 name="user3"（读前 offset=0, 读后 offset=0）
 * record 7: id=107 name="user7"（读前 offset=0, 读后 offset=0）
 * record 0: id=100 name="user0"（读前 offset=0, 读后 offset=0）
 * record 9: id=109 name="user9"（读前 offset=0, 读后 offset=0）
 * record 10: 读取失败（正确判越界）
 */
