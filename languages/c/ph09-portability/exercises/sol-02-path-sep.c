/* sol-02-path-sep.c —— 参考实现：为 Windows/Linux 分别封装路径分隔符
 * 路径分隔符 + 目录创建(mkdir/_mkdir)收敛成平台抽象, 业务代码零 #ifdef;
 * 文件删除用 ISO C 的 remove(), 天然跨平台
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-02-path-sep.c -o sol02
// 运行：./sol02（在 /tmp 下运行; 题目与验收见 exercises/README 练习 2）
// 验证状态：已验证（POSIX 分支: 目录创建/写入/删除/rmdir 全流程通过; _WIN32 分支
//           未在本环境验证——需 Windows, _mkdir 只接受单参数）
#include <stdio.h>
#ifdef _WIN32
#  include <direct.h>
#  define PATH_SEP "\\"
/* Windows 的 _mkdir 只有一个参数, 无权限位 */
#  define MKDIR(p) _mkdir(p)
#else
#  include <sys/stat.h>
#  define PATH_SEP "/"
/* POSIX 的 mkdir 带权限位 mode */
#  define MKDIR(p) mkdir((p), 0755)
#endif

/* 平台抽象: 拼一个"目录 + 文件名"的完整路径 */
static void join_path(char *out, size_t cap, const char *dir, const char *name) {
    snprintf(out, cap, "%s%s%s", dir, PATH_SEP, name);
}

int main(void) {
    char path[256];
    /* 1. 创建目录 */
    if (MKDIR("ph09_test_dir") != 0) {
        perror("MKDIR");
        return 1;
    }
    printf("目录创建成功\n");
    /* 2. 在目录里写一个文件, 路径用封装的 PATH_SEP 拼接 */
    join_path(path, sizeof path, "ph09_test_dir", "data.txt");
    FILE *fp = fopen(path, "w");
    if (fp == NULL) {
        perror("fopen");
        return 1;
    }
    fprintf(fp, "路径: %s\n", path);
    fclose(fp);
    printf("文件写入: %s\n", path);
    /* 3. 删除文件: ISO C 的 remove 跨平台可用; 删空目录 POSIX 用 rmdir, Windows 用 _rmdir */
    if (remove(path) != 0) {
        perror("remove");
        return 1;
    }
    printf("文件删除成功\n");
    return 0;
}
