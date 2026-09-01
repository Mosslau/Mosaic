// examples/ex02-short-io.c —— 短读短写与 read_full / write_full 循环（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
// 编译：cc -Wall -Wextra -std=c11 ex02-short-io.c -o ex02
// 运行：./ex02（用 pipe 演示真实短读，退出码 0）
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

/* write_full：循环 write 直到写够 n 字节 —— 写文件/写 socket 的固定姿势。
 * 返回 0 成功，-1 失败（errno 保留）。短写不是错误：继续写剩下的即可。 */
static int write_full(int fd, const void *buf, size_t n) {
    const char *p = buf;
    size_t left = n;
    while (left > 0) {
        ssize_t w = write(fd, p, left);
        if (w < 0) {
            if (errno == EINTR)
                continue;            /* 被信号打断：重试，不算失败 */
            return -1;
        }
        p += w;
        left -= (size_t)w;           /* 短写：只推进实际写出的部分 */
    }
    return 0;
}

/* read_full：循环 read 直到读够 n 字节或对端关闭。
 * 返回实际读到的字节数（< n 表示提前 EOF），-1 失败。 */
static ssize_t read_full(int fd, void *buf, size_t n) {
    char *p = buf;
    size_t left = n;
    size_t got = 0;
    while (left > 0) {
        ssize_t r = read(fd, p, left);
        if (r < 0) {
            if (errno == EINTR)
                continue;
            return -1;
        }
        if (r == 0)
            break;                   /* EOF：对端关闭，返回已读到的部分 */
        p += r;
        left -= (size_t)r;
        got += (size_t)r;
    }
    return (ssize_t)got;
}

int main(void) {
    /* 用 pipe 制造【真实的短读】：父进程分 3 批发数据，
     * 子进程第一次 read 只能拿到已到达的第 1 批。 */
    int fds[2];
    if (pipe(fds) < 0) {
        perror("pipe");
        return 1;
    }

    const char *part1 = "AAA";      /* 第 1 批：3 字节 */
    const char *part2 = "BBBBB";    /* 第 2 批：5 字节 */
    const char *part3 = "CC";       /* 第 3 批：2 字节，合计 10 字节 */

    pid_t pid = fork();
    if (pid < 0) {
        perror("fork");
        return 1;
    }

    if (pid == 0) {
        /* ---- 子进程：读端 ---- */
        close(fds[1]);
        char buf[16] = {0};

        /* 只 read 一次：此时 pipe 里只有第 1 批 → 短读 */
        ssize_t r = read(fds[0], buf, sizeof buf - 1);
        printf("单次 read 请求 %zu 字节，实际返回 %zd 字节（\"%s\"）—— 短读\n",
               sizeof buf - 1, r, buf);

        /* 用 read_full 把剩余部分读齐（第 1 批已消费 3 字节，还差 7 字节） */
        memset(buf, 0, sizeof buf);
        ssize_t got = read_full(fds[0], buf, 7);
        printf("read_full(7) 返回 %zd 字节（\"%s\"）—— 循环读齐了\n", got, buf);

        /* 再读：对端已关闭 → EOF */
        got = read_full(fds[0], buf, 1);
        printf("对端关闭后 read_full(1) 返回 %zd（0 = EOF）\n", got);
        close(fds[0]);
        fflush(stdout);              /* _exit 不刷新 stdio 缓冲，必须手动 flush */
        _exit(0);
    }

    /* ---- 父进程：写端，分 3 批写，批与批之间留 50ms ---- */
    close(fds[0]);
    if (write_full(fds[1], part1, strlen(part1)) < 0)
        perror("write_full");
    usleep(50000);
    if (write_full(fds[1], part2, strlen(part2)) < 0)
        perror("write_full");
    usleep(50000);
    if (write_full(fds[1], part3, strlen(part3)) < 0)
        perror("write_full");
    close(fds[1]);                   /* 关闭写端 → 子进程读到 EOF */
    waitpid(pid, NULL, 0);

    /* 短读/短写的三条纪律 */
    printf("\n纪律 1: read/write 的返回值是【实际】字节数，可能 < 请求值\n");
    printf("纪律 2: 返回 -1 且 errno == EINTR 是被信号打断，重试即可\n");
    printf("纪律 3: read 返回 0 是 EOF（对端关闭/文件读完），不是错误\n");
    return 0;
}
