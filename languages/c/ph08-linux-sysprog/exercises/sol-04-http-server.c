/* sol-04-http-server.c —— 简单 HTTP server：累积缓冲解析 GET 请求（处理半包），返回文件或固定 404
 * 用法: ./sol-04 [docroot]   默认服务当前目录; 端口 8080
 * 每次连接处理一个请求后关闭（Connection: close）
 */
#define _POSIX_C_SOURCE 200809L

#include <arpa/inet.h>
#include <netinet/in.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#define PORT 8080
#define BUF_SIZE 8192
#define PATH_SIZE 1024

/* 读请求直到出现 "\r\n\r\n"（请求头结束）; 返回读到的总字节数, 处理半包 */
static ssize_t read_request(int cfd, char *buf, size_t cap) {
    size_t used = 0;
    while (used < cap - 1) {
        ssize_t n = recv(cfd, buf + used, cap - 1 - used, 0);
        if (n <= 0)
            break;
        used += (size_t)n;
        buf[used] = '\0';
        if (strstr(buf, "\r\n\r\n") != NULL)
            break;
    }
    return (ssize_t)used;
}

static void send_all(int cfd, const char *data, size_t len) {
    size_t off = 0;
    while (off < len) {
        ssize_t w = send(cfd, data + off, len - off, 0);
        if (w < 0)
            return;
        off += (size_t)w;
    }
}

static void handle_client(int cfd, const char *docroot) {
    char buf[BUF_SIZE];
    if (read_request(cfd, buf, sizeof buf) <= 0)
        return;

    char method[16], path[PATH_SIZE];
    if (sscanf(buf, "%15s %1023s", method, path) != 2 || strcmp(method, "GET") != 0) {
        const char *resp = "HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n";
        send_all(cfd, resp, strlen(resp));
        return;
    }
    if (strstr(path, "..") != NULL) { /* 防目录穿越 */
        const char *resp = "HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n";
        send_all(cfd, resp, strlen(resp));
        return;
    }

    char full[PATH_SIZE + 256];
    snprintf(full, sizeof full, "%s%s", docroot, path);
    FILE *f = fopen(full, "rb");
    if (f == NULL) {
        const char *body = "<h1>404 Not Found</h1>\n";
        char head[256];
        int hlen = snprintf(head, sizeof head,
                            "HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\n"
                            "Content-Length: %zu\r\nConnection: close\r\n\r\n",
                            strlen(body));
        send_all(cfd, head, (size_t)hlen);
        send_all(cfd, body, strlen(body));
        return;
    }
    /* 200: 先发头再发文件内容 */
    char head[128];
    int hlen = snprintf(head, sizeof head,
                        "HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\n"
                        "Connection: close\r\n\r\n");
    send_all(cfd, head, (size_t)hlen);
    size_t n;
    while ((n = fread(buf, 1, sizeof buf, f)) > 0)
        send_all(cfd, buf, n);
    fclose(f);
}

int main(int argc, char *argv[]) {
    const char *docroot = argc > 1 ? argv[1] : ".";
    int lfd = socket(AF_INET, SOCK_STREAM, 0);
    if (lfd < 0) {
        perror("socket");
        return 1;
    }
    int opt = 1;
    setsockopt(lfd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof opt);
    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(PORT);
    if (bind(lfd, (struct sockaddr *)&addr, sizeof addr) < 0) {
        perror("bind");
        close(lfd);
        return 1;
    }
    if (listen(lfd, 16) < 0) {
        perror("listen");
        close(lfd);
        return 1;
    }
    printf("http server 监听 %d 端口, docroot=%s\n", PORT, docroot);
    for (;;) {
        int cfd = accept(lfd, NULL, NULL);
        if (cfd < 0) {
            perror("accept");
            continue;
        }
        handle_client(cfd, docroot); /* 简单版: 串行处理 */
        close(cfd);
    }
    close(lfd);
    return 0;
}
