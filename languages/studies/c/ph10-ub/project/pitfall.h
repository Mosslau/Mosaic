#ifndef PITFALL_H
#define PITFALL_H

#include <stddef.h>

/* 一个"坑" = 名字 + 说明 + 坏版本(bad) + 好版本(good) */
typedef struct {
    const char *name;   /* 命令行标识(如 "oob") */
    const char *title;  /* 中文名 */
    const char *tool;   /* 检测工具: ASan/UBSan/编译期警告/评审 */
    const char *desc;   /* 一句话识别要点 */
    void (*bad)(void);  /* 坏版本: 故意触发的 UB(被 Sanitizer 中止) */
    void (*good)(void); /* 好版本: 修复后的安全写法 */
} pitfall_t;

extern const pitfall_t g_pitfalls[];
extern const size_t g_pitfall_count;

/* 10 个坏版本, 由 bad_demos.c 实现 */
void bad_oob(void);      /* 数组越界 */
void bad_null(void);     /* 空指针解引用 */
void bad_uaf(void);      /* use-after-free / double free */
void bad_overflow(void); /* 有符号整数溢出 */
void bad_uninit(void);   /* 未初始化变量 */
void bad_alias(void);    /* 类型双关/严格别名 */
void bad_align(void);    /* 未对齐访问 */
void bad_divzero(void);  /* 整数除零 */
void bad_shift(void);    /* 非法移位 */
void bad_strbuf(void);   /* 字符串缓冲区溢出 */

#endif /* PITFALL_H */
