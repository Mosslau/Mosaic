/* ex02-platform-abstraction.c —— 条件编译平台抽象:
 * 把"路径分隔符、sleep"这类平台差异收敛成一组宏, 业务代码零 #ifdef;
 * _WIN32 在 32/64 位 Windows 上都定义, 判断平台用它
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 ex02-platform-abstraction.c -o ex02
// 运行：./ex02
// 验证状态：已验证（POSIX 分支编译运行通过; _WIN32 分支代码存在但未在本环境验证——需 Windows）
#include <stdio.h>
#ifdef _WIN32
#  include <windows.h>
#  define PATH_SEP "\\"
#  define SLEEP_MS(ms) Sleep(ms)
#else
#  include <unistd.h>
#  define PATH_SEP "/"
#  define SLEEP_MS(ms) usleep((ms) * 1000)
#endif

int main(void) {
    printf("路径分隔符: %s\n", PATH_SEP);
    printf("数据文件: data%slog.txt\n", PATH_SEP);
    printf("等待 300ms...\n");
    SLEEP_MS(300);
    printf("done\n");
    return 0;
}
