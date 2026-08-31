/* ex04-echo-server.c —— TCP echo server（阻塞版）：socket/bind/listen/accept 循环 + 完整错误处理 */
#define _POSIX_C_SOURCE 200809L

#include <arpa/inet.h>
#include <netinet/in.h>
#include <stdio.h>
#include <sys/socket.h>
#include <unistd.h>

#define PORT 8888
#define BUF_SIZE 4096

int main(void) {
    int lfd = socket(AF_INET, SOCK_STREAM, 0);
    if (lfd < 0) {
        perror("socket");
        return 1;
    }
    int opt = 1;
    setsockopt(lfd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof opt); /* 防 TIME_WAIT */
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
    printf("echo server 监听 %d 端口\n", PORT);
    for (;;) {
        struct sockaddr_in peer;
        socklen_t plen = sizeof peer;
        int cfd = accept(lfd, (struct sockaddr *)&peer, &plen);
        if (cfd < 0) {
            perror("accept");
            continue; /* accept 失败不退出 */
        }
        char ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &peer.sin_addr, ip, sizeof ip);
        printf("新连接: %s:%d\n", ip, ntohs(peer.sin_port));
        char buf[BUF_SIZE];
        ssize_t n;
        while ((n = recv(cfd, buf, sizeof buf, 0)) > 0) {
            ssize_t off = 0;
            while (off < n) { /* send 也要处理短写 */
                ssize_t w = send(cfd, buf + off, (size_t)(n - off), 0);
                if (w < 0) {
                    perror("send");
                    goto out;
                }
                off += w;
            }
        }
        if (n < 0)
            perror("recv"); /* EINTR 时按 3.1 的规则重试 */
    out:
        close(cfd); /* 连接 fd 用完即关 */
    }
    close(lfd);
    return 0;
}
