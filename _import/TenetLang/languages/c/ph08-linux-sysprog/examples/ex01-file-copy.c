/* ex01-file-copy.c —— 文件复制：open/read/write/close，完整处理短读短写与错误 */
#define _POSIX_C_SOURCE 200809L

#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>

#define BUF_SIZE 4096

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "用法: %s <源文件> <目标文件>\n", argv[0]);
        return 1;
    }
    int in = open(argv[1], O_RDONLY);
    if (in < 0) {
        perror("open 源文件");
        return 1;
    }
    int out = open(argv[2], O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (out < 0) {
        perror("open 目标文件");
        close(in);
        return 1;
    }
    char buf[BUF_SIZE];
    ssize_t n;
    while ((n = read(in, buf, sizeof buf)) > 0) {
        ssize_t off = 0;
        while (off < n) { /* 循环写, 处理短写 */
            ssize_t w = write(out, buf + off, (size_t)(n - off));
            if (w < 0) {
                perror("write");
                close(in);
                close(out);
                return 1;
            }
            off += w;
        }
    }
    if (n < 0) {
        perror("read");
        close(in);
        close(out);
        return 1;
    }
    close(in);
    close(out);
    printf("复制完成\n");
    return 0;
}
