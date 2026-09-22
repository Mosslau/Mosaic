/* sol-04-crash-replay.c —— 参考实现: 模拟进程崩溃后的 log replay
 * 布局（大端）: [len: u32][crc32: u32][payload]，与 examples/ex06 相同。
 * 崩溃模拟（真实 kill, 非演戏）:
 *   子进程追加 500 条记录（每 100 条 fsync 一次, 最后一次 fsync 在第 500 条）,
 *   再写半条记录（只有 6 字节头部）, 然后 kill(getpid(), SIGKILL) 自杀。
 *   父进程 waitpid 确认 SIGKILL, 再回放。
 * 要点（实测验证的两条真理）:
 *   ① 进程崩溃 ≠ 数据丢失: 已 write 的数据在内核 Page Cache 里,
 *     kill -9 之后 500 条全部完好（真正会丢数据的是断电/内核崩溃,
 *     那才是 fsync 要防的场景）;
 *   ② 半写入残尾被 长度/CRC 识别, ftruncate 截掉即恢复。
 * 实测: 500 条全部恢复, 残尾停在偏移 16284, 修复后文件恢复可追加。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-04-crash-replay.c -o sol04
// 运行：./sol04（写 /tmp/ph13-sol04.log 后删除, 退出码 0）
// 验证状态：已验证（-Wall -Wextra 零警告; 实测输出见文件尾注释）
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

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

static int log_append(int fd, const void *payload, uint32_t len) {
    uint8_t hdr[HDR_SIZE];
    write_be32(hdr, len);
    write_be32(hdr + 4, crc32(payload, len));
    if (write_full(fd, hdr, sizeof hdr) < 0)
        return -1;
    if (write_full(fd, payload, len) < 0)
        return -1;
    return 0;
}

/* 回放：返回完整记录数, *torn_at = 损坏点偏移（无损坏则 = 文件大小） */
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
            break;
        if (r < (ssize_t)HDR_SIZE)
            goto torn;
        uint32_t len = read_be32(hdr);
        uint32_t crc = read_be32(hdr + 4);
        if (len > MAX_PAYLOAD)
            goto torn;
        r = pread(fd, payload, len, off + HDR_SIZE);
        if (r < 0)
            return -1;
        if (r < (ssize_t)len)
            goto torn;
        if (crc32(payload, len) != crc)
            goto torn;
        count++;
        off += (off_t)HDR_SIZE + len;
    }
    *torn_at = off;
    return count;
torn:
    *torn_at = off;
    return count;
}

int main(void) {
    const char *path = "/tmp/ph13-sol04.log";
    const int total = 500;

    /* 父进程先建空文件, 子进程负责写 */
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
        /* ---- 子进程：模拟一个写日志写到一半被 kill -9 的服务 ---- */
        int wfd = open(path, O_WRONLY | O_APPEND);
        if (wfd < 0)
            _exit(2);
        for (int i = 1; i <= total; i++) {
            char payload[50];
            int plen = snprintf(payload, sizeof payload, "op-%04d SET key%d=val%d", i, i, i);
            if (log_append(wfd, payload, (uint32_t)plen) < 0)
                _exit(2);
            if (i % 100 == 0)
                fsync(wfd);               /* 每 100 条刷一次盘 */
        }
        /* 写第 501 条, 但只写 6 字节头部就"崩溃"（半写入） */
        uint8_t half[6] = {0, 0, 0, 20, 0, 0};
        if (write_full(wfd, half, sizeof half) < 0)
            _exit(2);
        /* 真实 kill：不等 flush、不走退出流程 */
        kill(getpid(), SIGKILL);
        _exit(0);                          /* 到不了 */
    }

    /* ---- 父进程：确认死因, 然后像存储引擎一样恢复 ---- */
    int status = 0;
    waitpid(pid, &status, 0);
    printf("① 子进程 %s（写入 500 条 + 半条残记录后被 kill -9）\n",
           WIFSIGNALED(status) && WTERMSIG(status) == SIGKILL
               ? "确被 SIGKILL 杀死" : "死因异常!");

    fd = open(path, O_RDONLY);
    if (fd < 0) {
        perror("open replay");
        return 1;
    }
    off_t torn_at = 0;
    int ok = log_replay(fd, &torn_at);
    printf("② 崩溃后回放: 恢复 %d/%d 条完整记录, 残尾在偏移 %lld\n",
           ok, total, (long long)torn_at);
    printf("   注意: 进程崩溃【没有】丢数据 —— write 过的字节在内核 Page Cache 里,\n");
    printf("   kill -9 杀的是进程, 不是内核缓存（断电/内核崩溃才丢, 那要靠 fsync）。\n");
    close(fd);

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
    printf("③ ftruncate 到 %lld 砍掉残尾, 日志恢复可追加状态\n", (long long)torn_at);

    unlink(path);
    return ok == total ? 0 : 1;
}

/* 实测输出（本机一次运行）：
 * ① 子进程 确被 SIGKILL 杀死（写入 500 条 + 半条残记录后被 kill -9）
 * ② 崩溃后回放: 恢复 500/500 条完整记录, 残尾在偏移 16284
 *    注意: 进程崩溃【没有】丢数据 —— write 过的字节在内核 Page Cache 里,
 *    kill -9 杀的是进程, 不是内核缓存（断电/内核崩溃才丢, 那要靠 fsync）。
 * ③ ftruncate 到 16284 砍掉残尾, 日志恢复可追加状态
 */
