// examples/ex05-logging.c —— 日志系统：级别/阈值过滤/trace id/诊断（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
// 编译：cc -Wall -Wextra -std=c11 ex05-logging.c -o ex05
// 运行：./ex05（无外部产物，退出码 0；实测输出见文件尾注释）
#include <stdio.h>
#include <time.h>

/* ---- 级别 ---- */
enum level { LVL_DEBUG = 0, LVL_INFO = 1, LVL_WARN = 2, LVL_ERROR = 3 };

static const char *lvl_tag(enum level l) {
    static const char *const tags[4] = {"DEBUG", "INFO", "WARN", "ERROR"};
    return tags[l];
}

/* ---- mini logger 状态（简化：全局阈值; 工程版做成 handle 对象, 见 ex06 句柄模式） ---- */
static enum level g_min_level = LVL_DEBUG;
static long g_emitted = 0;   /* 实际输出条数 —— 诊断统计 */
static long g_dropped = 0;   /* 被级别过滤掉的条数 */

static void log_set_level(enum level l) { g_min_level = l; }

/* 核心输出函数：带 trace id + 文件:行。低于阈值不输出（计入 dropped）。 */
static void log_emit(enum level lvl, long trace_id,
                     const char *file, int line, const char *msg) {
    if (lvl < g_min_level) {   /* 级别过滤 */
        g_dropped++;
        return;
    }
    g_emitted++;

    /* 时间（秒级; 精确到毫秒需要 clock_gettime, 见 ph09 project 的跨平台日志库） */
    time_t now = time(NULL);
    struct tm tmv;
    localtime_r(&now, &tmv);

    char hdr[32];
    snprintf(hdr, sizeof hdr, "%02d:%02d:%02d",
             tmv.tm_hour, tmv.tm_min, tmv.tm_sec);

    printf("[%s][%-5s][trace=%04lx][%s:%d] %s\n",
           hdr, lvl_tag(lvl), trace_id, file, line, msg);
}

/* ---- 日志宏: 自动带 __FILE__/__LINE__（衔接 ex01 宏技巧） ---- */
#define LOG(lvl, tid, ...) \
    log_emit((lvl), (tid), __FILE__, __LINE__, ##__VA_ARGS__)

int main(void) {
    const long TRACE = 0x1a2b;    /* 模拟一次请求的 trace id */

    printf("=== ex05 日志系统 ===\n");

    printf("-- 场景 1: 阈值=DEBUG, 四级全输出 --\n");
    log_set_level(LVL_DEBUG);
    LOG(LVL_DEBUG, TRACE, "收到请求, 开始解析");
    LOG(LVL_INFO,  TRACE, "路由到 handler");
    LOG(LVL_WARN,  TRACE, "参数过期, 使用默认值");
    LOG(LVL_ERROR, TRACE, "写回失败, 已重试");

    printf("-- 场景 2: 阈值调到 WARN, DEBUG/INFO 被过滤 --\n");
    log_set_level(LVL_WARN);
    LOG(LVL_DEBUG, TRACE, "这条 DEBUG 不应出现");
    LOG(LVL_INFO,  TRACE, "这条 INFO 不应出现");
    LOG(LVL_WARN,  TRACE, "WARN 仍输出");
    LOG(LVL_ERROR, TRACE, "ERROR 仍输出");

    /* 诊断统计：输出/被过滤条数（对比场景 1/2 可复核过滤逻辑） */
    printf("-- 诊断统计 --\n");
    printf("emitted=%ld dropped=%ld (场景1 输出 4 条; 场景2 输出 2 条、过滤 2 条)\n",
           g_emitted, g_dropped);

    printf("-- trace id 的诊断价值 --\n");
    printf("同一请求所有日志行带同一 trace=1a2b, 按 id grep 即可还原一次请求全过程\n");
    return 0;
}

/* 实测输出（本机一次运行, Apple clang 21.0.0, macOS arm64）：
 * === ex05 日志系统 ===
 * -- 场景 1: 阈值=DEBUG, 四级全输出 --
 * [13:29:22][DEBUG][trace=1a2b][ex05-logging.c:56] 收到请求, 开始解析
 * [13:29:22][INFO ][trace=1a2b][ex05-logging.c:57] 路由到 handler
 * [13:29:22][WARN ][trace=1a2b][ex05-logging.c:58] 参数过期, 使用默认值
 * [13:29:22][ERROR][trace=1a2b][ex05-logging.c:59] 写回失败, 已重试
 * -- 场景 2: 阈值调到 WARN, DEBUG/INFO 被过滤 --
 * [13:29:22][WARN ][trace=1a2b][ex05-logging.c:65] WARN 仍输出
 * [13:29:22][ERROR][trace=1a2b][ex05-logging.c:66] ERROR 仍输出
 * -- 诊断统计 --
 * emitted=6 dropped=2 (场景1 输出 4 条; 场景2 输出 2 条、过滤 2 条)
 * -- trace id 的诊断价值 --
 * 同一请求所有日志行带同一 trace=1a2b, 按 id grep 即可还原一次请求全过程
 */
