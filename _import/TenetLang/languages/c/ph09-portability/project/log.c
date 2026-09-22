/* log.c —— 跨平台日志库实现
 * 四个可移植性要点, 与主文档 3.4/3.5/3.6 一一对应:
 * 1. 文件头字段全部用 stdint.h 固定宽度类型, _Static_assert 固化尺寸契约;
 * 2. 锁的差异(pthread_mutex_t vs CRITICAL_SECTION)用 #ifdef 收敛成 lock_t,
 *    业务代码(包括本文件其余部分)零 #ifdef;
 * 3. getpid 的差异(POSIX vs _getpid)同样用 #ifdef 收进小封装;
 * 4. 时间/文件/可变参数(ISO C)与轮转(remove/rename, ISO C)天然跨平台
 *
 * 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64），-Wall -Wextra -std=c11 -pthread
 * 编译：make（或 cc -Wall -Wextra -std=c11 -pthread -c log.c -o log.o）
 * 运行/测试：make test
 * 验证状态：已验证（POSIX 分支构建零警告, make test 自检通过, 连续运行 20 次
 *           (不清除旧日志)自检均通过; _WIN32 分支(CRITICAL_SECTION/_getpid)
 *           未在本环境验证——需 Windows）
 */
#define _POSIX_C_SOURCE 200809L /* 保证 glibc 下 getpid 等 POSIX 声明可见 */

#include "log.h"

#include <inttypes.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#ifdef _WIN32
#  include <process.h>
#  include <windows.h>
#  define getpid _getpid
typedef CRITICAL_SECTION lock_t; /* Windows: 临界区 */
#  define LOCK_INIT(l)    InitializeCriticalSection(l)
#  define LOCK_DESTROY(l) DeleteCriticalSection(l)
#  define LOCK_ACQUIRE(l) EnterCriticalSection(l)
#  define LOCK_RELEASE(l) LeaveCriticalSection(l)
#else
#  include <pthread.h>
#  include <unistd.h>
typedef pthread_mutex_t lock_t; /* POSIX: mutex */
#  define LOCK_INIT(l)    pthread_mutex_init(l, NULL)
#  define LOCK_DESTROY(l) pthread_mutex_destroy(l)
#  define LOCK_ACQUIRE(l) pthread_mutex_lock(l)
#  define LOCK_RELEASE(l) pthread_mutex_unlock(l)
#endif

#define MAX_LOG_SIZE  1024 /* 超过即轮转: 演示用小值便于观察, 生产按需调大 */

/* 文件头: 固定宽度字段, 尺寸契约写进编译期 */
typedef struct {
    uint32_t magic;       /* 0x4C4F4731u, 本机读写一致(跨机器交换需处理字节序, 属 ph12) */
    uint8_t  version;     /* 格式版本 */
    uint8_t  flags;       /* 预留标志位 */
    uint16_t header_size; /* 文件头字节数 */
    uint32_t reserved;    /* 预留 */
} log_file_header_t;

_Static_assert(sizeof(log_file_header_t) == 12, "日志文件头必须是 12 字节");

static FILE *g_fp = NULL;
static char g_path[512];
static lock_t g_lock;
static int g_lock_init = 0;
static unsigned g_next = 1;      /* 下一个轮转备份序号(跨运行单调) */
static unsigned g_rotations = 0; /* 本次运行轮转次数 */
static log_level_t g_level = LOG_INFO;
static size_t g_size = 0;
static const char *g_names[] = {"DEBUG", "INFO", "WARN", "ERROR"};

/* 当前是否有真实文件可写(否则在写 stderr) */
static int have_file(void) {
    return g_fp != NULL && g_fp != stderr;
}

/* 写文件头; 追加模式重开已有日志时文件非空, 不再重复写头, 只记当前大小 */
static void write_header(void) {
    if (fseek(g_fp, 0, SEEK_END) != 0)
        return;
    long sz = ftell(g_fp);
    if (sz > 0) {
        g_size = (size_t)sz;
        return;
    }
    log_file_header_t hdr;
    memset(&hdr, 0, sizeof hdr);
    hdr.magic = 0x4C4F4731u;
    hdr.version = 1;
    hdr.header_size = (uint16_t)sizeof hdr;
    size_t w = fwrite(&hdr, 1, sizeof hdr, g_fp); /* 失败仅影响自检, 不阻塞写日志 */
    (void)w;
    g_size = sizeof hdr;
}

/* 轮转: 当前文件改名为带序号的备份(app.log.1, app.log.2, ...), 重开新文件并写
 * 文件头; 序号跨运行单调递增(g_next 在 log_open 时从已有备份继续), 不覆盖旧备份,
 * 保证"轮转不丢行"(保留上限属扩展方向); 失败则继续写原文件 */
static void rotate(void) {
    if (!have_file())
        return;
    char backup[sizeof g_path + 16];
    snprintf(backup, sizeof backup, "%s.%u", g_path, g_next++);
    fclose(g_fp);
    g_fp = NULL;
    if (rename(g_path, backup) != 0) {
        g_fp = fopen(g_path, "ab"); /* 轮转失败: 继续写原文件 */
        return;
    }
    g_fp = fopen(g_path, "ab");
    if (g_fp != NULL) {
        write_header();
        g_rotations++;
    }
}

int log_open(const char *path) {
    if (!g_lock_init) {
        LOCK_INIT(&g_lock);
        g_lock_init = 1;
    }
    snprintf(g_path, sizeof g_path, "%s", path);
    /* 轮转序号跨运行单调: 从"已存在备份的最大序号 + 1"起算, 不覆盖上次运行的
     * 备份(否则连续运行时旧日志被改名覆盖, "轮转不丢行"只在单次运行内成立);
     * 用 fopen 探测, ISO C 可移植(Windows 同样可用) */
    unsigned max_backup = 0;
    char probe[sizeof g_path + 16];
    for (unsigned i = 1; i < 1000000; i++) {
        snprintf(probe, sizeof probe, "%s.%u", g_path, i);
        FILE *p = fopen(probe, "rb");
        if (p != NULL) {
            fclose(p);
            max_backup = i;
        } else if (i > max_backup + 1) {
            break; /* 备份序号连续, 遇到空缺即可停止探测 */
        }
    }
    g_next = max_backup + 1;
    g_rotations = 0;
    g_fp = fopen(path, "ab"); /* ISO C: 追加模式, 跨平台 */
    if (g_fp == NULL)
        return -1;
    write_header();
    return 0;
}

void log_set_level(log_level_t level) {
    g_level = level; /* 演示中在开线程前调用, 无并发写 */
}

void log_msg(log_level_t level, const char *fmt, ...) {
    LOCK_ACQUIRE(&g_lock);
    if (level < g_level) /* 级别过滤: 低于阈值直接丢弃, 不落盘 */
        goto out;
    if (g_fp == NULL)
        g_fp = stderr; /* 未 open 或已 close: 落到 stderr, 不崩溃 */
    char ts[32];
    time_t now = time(NULL);
    struct tm *t = localtime(&now); /* ISO C: 本地时间 */
    strftime(ts, sizeof ts, "%Y-%m-%d %H:%M:%S", t);
    int n = fprintf(g_fp, "[%s][%s][pid=%" PRId64 "] ", ts, g_names[level],
                    (int64_t)getpid()); /* getpid 经封装: POSIX/Windows 通用 */
    va_list ap;
    va_start(ap, fmt);
    n += vfprintf(g_fp, fmt, ap);
    va_end(ap);
    n += fputc('\n', g_fp);
    fflush(g_fp); /* 及时落盘, 崩溃不丢尾部日志 */
    if (have_file()) {
        g_size += (size_t)n;
        if (g_size > MAX_LOG_SIZE)
            rotate();
    }
out:
    LOCK_RELEASE(&g_lock);
}

void log_close(void) {
    LOCK_ACQUIRE(&g_lock);
    if (have_file())
        fclose(g_fp);
    g_fp = NULL;
    LOCK_RELEASE(&g_lock);
}

unsigned log_rotations(void) {
    return g_rotations;
}
