/* ex05-portable-log.c —— 可移植日志库骨架:
 * 时间(time/localtime/strftime)、文件(fopen/fprintf)、可变参数(va_*)全是 ISO C,
 * 天然跨平台; 唯一需要抽象的差异(getpid)用 #ifdef 收进小封装;
 * "pid=%" PRId64 是字符串字面量拼接, 拼出平台无关的 64 位格式串
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 ex05-portable-log.c -o ex05
// 运行：cd /tmp && /path/to/ex05 && cat app.log（日志文件写当前目录, 请到 /tmp 下运行）
// 验证状态：已验证（POSIX 分支编译运行通过; _WIN32 分支(_getpid)未在本环境验证——需 Windows）
#include <inttypes.h>
#include <stdarg.h>
#include <stdio.h>
#include <time.h>
#ifdef _WIN32
#  include <process.h>
#  define getpid _getpid
#else
#  include <unistd.h>
#endif

typedef enum { LOG_DEBUG, LOG_INFO, LOG_WARN, LOG_ERROR } log_level_t;
static const char *level_names[] = {"DEBUG", "INFO", "WARN", "ERROR"};
static FILE *g_log = NULL;

void log_open(const char *path) {
    g_log = fopen(path, "a"); /* ISO C: 追加模式, 跨平台 */
    if (!g_log) g_log = stderr;
}

void log_msg(log_level_t level, const char *fmt, ...) {
    if (!g_log) g_log = stderr;
    char ts[32];
    time_t now = time(NULL);
    struct tm *t = localtime(&now); /* ISO C: 本地时间 */
    strftime(ts, sizeof ts, "%Y-%m-%d %H:%M:%S", t);
    fprintf(g_log, "[%s][%s][pid=%" PRId64 "] ", ts, level_names[level],
            (int64_t)getpid()); /* getpid 经封装: POSIX/Windows 通用 */
    va_list ap;
    va_start(ap, fmt);
    vfprintf(g_log, fmt, ap);
    va_end(ap);
    fputc('\n', g_log);
    fflush(g_log); /* 及时落盘, 崩溃不丢尾部日志 */
}

int main(void) {
    log_open("app.log");
    log_msg(LOG_INFO, "日志库启动, pid=%" PRId64, (int64_t)getpid());
    log_msg(LOG_WARN, "磁盘剩余空间不足: %d%%", 5);
    log_msg(LOG_ERROR, "写盘失败: %s", "EIO");
    return 0;
}
