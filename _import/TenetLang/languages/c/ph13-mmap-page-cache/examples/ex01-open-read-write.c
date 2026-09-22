// examples/ex01-open-read-write.c —— open/read/write/pread/pwrite 与文件 offset（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
// 编译：cc -Wall -Wextra -std=c11 ex01-open-read-write.c -o ex01
// 运行：./ex01（演示文件写 /tmp/ph13-ex01.bin，运行后删除，退出码 0）
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static void die(const char *msg) {
    perror(msg);          /* perror 把 errno 翻译成可读信息 */
    _exit(1);
}

int main(void) {
    const char *path = "/tmp/ph13-ex01.bin";

    /* ① open：O_CREAT 不存在则创建, O_TRUNC 清空, O_RDWR 可读可写
     * 第三个参数 0644 只在 O_CREAT 生效时有用（受 umask 影响） */
    int fd = open(path, O_CREAT | O_TRUNC | O_RDWR, 0644);
    if (fd < 0)
        die("open");

    /* ② write：返回值是实际写入的字节数，可能 < 请求值（短写，见 ex02） */
    const char *msg = "hello";
    ssize_t w = write(fd, msg, 5);
    if (w < 0)
        die("write");
    printf("write(%zu) 返回 %zd 字节\n", strlen(msg), w);

    /* ③ 每个 fd 维护一个文件 offset，read/write 都会推进它 */
    off_t cur = lseek(fd, 0, SEEK_CUR);
    printf("write 后 offset = %lld\n", (long long)cur);

    /* ④ pread：从指定 offset 读，但【不推进】fd 的 offset */
    char buf[6] = {0};
    ssize_t r = pread(fd, buf, 5, 0);
    if (r < 0)
        die("pread");
    printf("pread(0) 读到 \"%s\"，read 后 offset = %lld（未变）\n",
           buf, (long long)lseek(fd, 0, SEEK_CUR));

    /* ⑤ pwrite：向指定 offset 写，同样不动 fd 的 offset —— 覆盖前 5 字节 */
    if (pwrite(fd, "HELLO", 5, 0) != 5)
        die("pwrite");
    printf("pwrite(0) 覆盖后 offset = %lld（仍未变）\n",
           (long long)lseek(fd, 0, SEEK_CUR));

    /* ⑥ 普通 read 从 fd 的当前 offset（5）继续读 → EOF 返回 0 */
    if (lseek(fd, 0, SEEK_SET) < 0)
        die("lseek");
    char all[16] = {0};
    r = read(fd, all, sizeof all - 1);
    if (r < 0)
        die("read");
    printf("lseek(0) 后 read 全文件: \"%s\"（%zd 字节）\n", all, r);
    r = read(fd, all, sizeof all - 1);
    printf("再 read 一次: 返回 %zd（EOF 返回 0，不是错误）\n", r);

    /* ⑦ 错误返回：对 O_WRONLY 的 fd 读 → -1 且 errno=EBADF */
    int wfd = open(path, O_WRONLY);
    if (wfd < 0)
        die("open O_WRONLY");
    r = read(wfd, all, 1);
    printf("对 O_WRONLY fd 调用 read: 返回 %zd, errno = %d（%s）\n",
           r, errno, strerror(errno));

    /* lseek 到末尾即文件大小（等效 fstat 的 st_size 的常用取法之一） */
    printf("文件大小 = %lld 字节\n", (long long)lseek(fd, 0, SEEK_END));

    close(wfd);
    close(fd);
    unlink(path);
    return 0;
}
