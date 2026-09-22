/* log.h —— 跨平台日志库 API
 * 平台差异(锁、getpid)全部收进 log.c 内部用 #ifdef 处理, 头文件零 #ifdef;
 * 使用方只需包含本头文件, 在任意支持 C11 的平台上用同一套 API
 */
#ifndef LOG_H
#define LOG_H

typedef enum { LOG_DEBUG, LOG_INFO, LOG_WARN, LOG_ERROR } log_level_t;

/* 打开日志文件(追加模式), 写入 12 字节固定宽度文件头; 失败返回 -1 */
int log_open(const char *path);

/* 设置日志级别: 低于该级别的消息被丢弃(默认 LOG_INFO) */
void log_set_level(log_level_t level);

/* 写一条日志, 线程安全; 行首带 [时间戳][级别][pid], 格式串同 printf
 * 打印固定宽度整数请用 <inttypes.h> 的格式宏(如 PRId64) */
void log_msg(log_level_t level, const char *fmt, ...);

/* 关闭日志文件; 之后再次 log_msg 自动落到 stderr */
void log_close(void);

/* 返回本次运行发生轮转的次数(自检/统计用) */
unsigned log_rotations(void);

#endif
