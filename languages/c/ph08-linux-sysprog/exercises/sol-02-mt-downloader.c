/* sol-02-mt-downloader.c —— 多线程下载器：每个 URL 一个线程发 HTTP GET 落盘，
 * 主线程 join 汇总；共享的"已完成计数"用 mutex 保护
 * 用法: ./sol-02 <host> <port> <path1> [path2 ...]   结果存为 download-1, download-2, ...
 */
#define _POSIX_C_SOURCE 200809L

#include <arpa/inet.h>
#include <netinet/in.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#define BUF_SIZE 4096

typedef struct {
    const char *host;
    int port;
    const char *path;
    int index; /* 任务编号, 决定输出文件名 */
} Task;

static int completed = 0;                  /* 共享计数: 必须用 mutex 保护 */
static pthread_mutex_t count_lock = PTHREAD_MUTEX_INITIALIZER;

/* 把整个响应（含响应头）写入本地文件; 返回 0 成功 */
static int download_one(const Task *t) {
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) {
        perror("socket");
        return -1;
    }
    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET;
    addr.sin_port = htons((uint16_t)t->port);
    if (inet_pton(AF_INET, t->host, &addr.sin_addr) != 1) {
        fprintf(stderr, "任务 %d: 仅支持 IPv4 点分十进制地址, 收到 %s\n", t->index, t->host);
        close(fd);
        return -1;
    }
    if (connect(fd, (struct sockaddr *)&addr, sizeof addr) < 0) {
        perror("connect");
        close(fd);
        return -1;
    }
    char req[512];
    int len = snprintf(req, sizeof req, "GET %s HTTP/1.0\r\nHost: %s\r\n\r\n", t->path, t->host);
    ssize_t off = 0;
    while (off < len) { /* 短写处理 */
        ssize_t w = send(fd, req + off, (size_t)(len - off), 0);
        if (w < 0) {
            perror("send");
            close(fd);
            return -1;
        }
        off += w;
    }
    char outname[64];
    snprintf(outname, sizeof outname, "download-%d", t->index);
    FILE *out = fopen(outname, "wb");
    if (out == NULL) {
        perror("fopen");
        close(fd);
        return -1;
    }
    char buf[BUF_SIZE];
    ssize_t n;
    while ((n = recv(fd, buf, sizeof buf, 0)) > 0) /* 短读处理: 循环到 EOF */
        fwrite(buf, 1, (size_t)n, out);
    fclose(out);
    close(fd);
    if (n < 0) {
        perror("recv");
        return -1;
    }
    return 0;
}

static void *worker(void *arg) {
    Task *t = arg;
    if (download_one(t) == 0) {
        pthread_mutex_lock(&count_lock);
        completed++;
        int done = completed;
        pthread_mutex_unlock(&count_lock);
        printf("任务 %d 完成 (%s -> download-%d), 累计 %d 个\n", t->index, t->path, t->index, done);
    } else {
        printf("任务 %d 失败 (%s)\n", t->index, t->path);
    }
    return NULL;
}

int main(int argc, char *argv[]) {
    if (argc < 4) {
        fprintf(stderr, "用法: %s <host> <port> <path1> [path2 ...]\n", argv[0]);
        return 1;
    }
    int ntask = argc - 3;
    Task *tasks = malloc((size_t)ntask * sizeof(Task)); /* 堆分配, 保证线程运行期存活 */
    pthread_t *tids = malloc((size_t)ntask * sizeof(pthread_t));
    if (tasks == NULL || tids == NULL) {
        fprintf(stderr, "内存不足\n");
        free(tasks);
        free(tids);
        return 1;
    }
    for (int i = 0; i < ntask; i++) {
        tasks[i].host = argv[1];
        tasks[i].port = atoi(argv[2]);
        tasks[i].path = argv[3 + i];
        tasks[i].index = i + 1;
        if (pthread_create(&tids[i], NULL, worker, &tasks[i]) != 0) {
            perror("pthread_create");
            free(tasks);
            free(tids);
            return 1;
        }
    }
    for (int i = 0; i < ntask; i++)
        pthread_join(tids[i], NULL); /* 主线程 join 汇总 */
    printf("汇总: 共 %d 个任务, 成功 %d 个\n", ntask, completed);
    free(tasks);
    free(tids);
    return 0;
}
