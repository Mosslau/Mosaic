/* ex02-fork-wait.c —— 多进程协作：fork 出多个子进程，父进程 wait 依次回收（防僵尸） */
#define _POSIX_C_SOURCE 200809L

#include <stdio.h>
#include <sys/wait.h>
#include <unistd.h>

#define CHILDREN 3

int main(void) {
    for (int i = 0; i < CHILDREN; i++) {
        pid_t pid = fork();
        if (pid < 0) {
            perror("fork");
            return 1;
        }
        if (pid == 0) {
            printf("子进程 %d: 我是第 %d 个孩子\n", getpid(), i + 1);
            return (i + 1) * 10; /* 用退出码回传结果 */
        }
    }
    int status;
    pid_t child;
    while ((child = wait(&status)) > 0) /* 父进程: 依次回收全部子进程 */
        printf("父进程: 子进程 %d 退出, 退出码 %d\n", child,
               WIFEXITED(status) ? WEXITSTATUS(status) : -1);
    return 0;
}
