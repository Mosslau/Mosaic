/* sol-01-mini-shell.c —— 简单 shell：循环读命令 → fork + execvp 执行 → waitpid 回收
 * 内置命令 cd/exit 不 fork；其余命令经 PATH 查找执行
 */
#define _POSIX_C_SOURCE 200809L

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

#define MAX_LINE 1024
#define MAX_ARGS 64

/* 把一行按空白切成 argv, 返回参数个数 */
static int split_args(char *line, char *argv[], int max) {
    int argc = 0;
    char *tok = strtok(line, " \t\n");
    while (tok != NULL && argc < max - 1) {
        argv[argc++] = tok;
        tok = strtok(NULL, " \t\n");
    }
    argv[argc] = NULL;
    return argc;
}

int main(void) {
    char line[MAX_LINE];
    char *argv[MAX_ARGS];
    for (;;) {
        printf("mini-sh$ ");
        fflush(stdout); /* 无换行的提示符需要手动刷新 */
        if (fgets(line, sizeof line, stdin) == NULL) { /* EOF (Ctrl+D) */
            printf("\n");
            break;
        }
        int argc = split_args(line, argv, MAX_ARGS);
        if (argc == 0)
            continue;
        if (strcmp(argv[0], "exit") == 0)
            break;
        if (strcmp(argv[0], "cd") == 0) { /* 内置命令: 必须改父进程自己, 不能 fork */
            const char *dir = argc > 1 ? argv[1] : getenv("HOME");
            if (chdir(dir) < 0)
                perror("cd");
            continue;
        }
        pid_t pid = fork();
        if (pid < 0) {
            perror("fork");
            continue;
        }
        if (pid == 0) {
            execvp(argv[0], argv); /* 依赖 PATH 查找 */
            perror("execvp");      /* 只有失败才走到这里 */
            _exit(127);
        }
        int status;
        waitpid(pid, &status, 0); /* 回收子进程, 防僵尸 */
        if (WIFEXITED(status) && WEXITSTATUS(status) != 0)
            printf("[退出码 %d]\n", WEXITSTATUS(status));
    }
    return 0;
}
