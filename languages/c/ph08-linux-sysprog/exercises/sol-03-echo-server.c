/* sol-03-echo-server.c —— 多客户端 TCP echo server：fork 每连接 + SIGCHLD 回收僵尸
 * 运行: ./sol-03 后另开多个终端 nc 127.0.0.1 8888 同时连接
 */
#define _POSIX_C_SOURCE 200809L

#include <arpa/inet.h>
#include <netinet/in.h>
#include <signal.h>
#include <stdio.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <unistd.h>

#define PORT 8888
#define BUF_SIZE 4096

/* 回收所有已退出的子进程; waitpid 是 async-signal-safe 的 */
static void reap_children(int sig) {
    (void)sig;
    while (waitpid(-1, NULL, WNOHANG) > 0)
        ;
}

static void echo_loop(int cfd) {
    char buf[BUF_SIZE];
    ssize_t n;
    while ((n = recv(cfd, buf, sizeof buf, 0)) > 0) {
        ssize_t off = 0;
        while (off < n) { /* 短写处理 */
            ssize_t w = send(cfd, buf + off, (size_t)(n - off), 0);
            if (w < 0)
                return;
            off += w;
        }
    }
}

int main(void) {
    struct sigaction sa = {0};
    sa.sa_handler = reap_children;
    sa.sa_flags = SA_RESTART; /* 被打断的 accept 自动重试 */
    sigaction(SIGCHLD, &sa, NULL);

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
    printf("fork echo server 监听 %d 端口\n", PORT);
    for (;;) {
        struct sockaddr_in peer;
        socklen_t plen = sizeof peer;
        int cfd = accept(lfd, (struct sockaddr *)&peer, &plen);
        if (cfd < 0) {
            perror("accept");
            continue;
        }
        pid_t pid = fork();
        if (pid < 0) {
            perror("fork");
            close(cfd);
            continue;
        }
        if (pid == 0) {
            close(lfd); /* 子进程不需要监听 fd */
            echo_loop(cfd);
            close(cfd);
            _exit(0); /* _exit: 避免冲刷父进程继承的 stdio 缓冲 */
        }
        close(cfd); /* 父进程不需要连接 fd, 不关会泄漏 */
    }
    close(lfd);
    return 0;
}
