/* ex05-epoll-server.c —— epoll 版简易事件循环：单线程同时服务多个连接
 * 注意: epoll 是 Linux 专有 API, 本文件未在 macOS 环境验证（需 Linux 2.6+）
 */
#define _POSIX_C_SOURCE 200809L

#include <arpa/inet.h>
#include <netinet/in.h>
#include <stdio.h>
#include <sys/epoll.h>
#include <sys/socket.h>
#include <unistd.h>

#define PORT 9999
#define MAX_EVENTS 64
#define BUF_SIZE 4096

int main(void) {
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
    int epfd = epoll_create1(0);
    if (epfd < 0) {
        perror("epoll_create1");
        close(lfd);
        return 1;
    }
    struct epoll_event ev = {0};
    ev.events = EPOLLIN;
    ev.data.fd = lfd;
    epoll_ctl(epfd, EPOLL_CTL_ADD, lfd, &ev); /* 注册监听 fd */
    printf("epoll server 监听 %d 端口\n", PORT);
    struct epoll_event ready[MAX_EVENTS];
    for (;;) {
        int n = epoll_wait(epfd, ready, MAX_EVENTS, -1);
        if (n < 0) {
            perror("epoll_wait");
            break;
        }
        for (int i = 0; i < n; i++) {
            if (ready[i].data.fd == lfd) { /* 新连接 */
                struct sockaddr_in peer;
                socklen_t plen = sizeof peer;
                int cfd = accept(lfd, (struct sockaddr *)&peer, &plen);
                if (cfd < 0)
                    continue;
                struct epoll_event cev = {0};
                cev.events = EPOLLIN;
                cev.data.fd = cfd;
                epoll_ctl(epfd, EPOLL_CTL_ADD, cfd, &cev); /* 新 fd 注册进 epoll */
            } else { /* 已有连接可读 */
                int cfd = ready[i].data.fd;
                char buf[BUF_SIZE];
                ssize_t r = read(cfd, buf, sizeof buf);
                if (r <= 0) { /* 0=对端关闭, <0=错误 */
                    epoll_ctl(epfd, EPOLL_CTL_DEL, cfd, NULL);
                    close(cfd); /* fd 泄漏高发点 */
                } else {
                    /* 简化: 半包/短写见主文档 3.6 要点 */
                    ssize_t off = 0;
                    while (off < r) {
                        ssize_t w = write(cfd, buf + off, (size_t)(r - off));
                        if (w < 0)
                            break;
                        off += w;
                    }
                }
            }
        }
    }
    close(epfd);
    close(lfd);
    return 0;
}
