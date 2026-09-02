// examples/ex04-error-code.c —— 错误码设计：稳定、可追踪（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
// 编译：mkdir -p /tmp/ph15c-ex && cc -Wall -Wextra -std=c11 ex04-error-code.c -o /tmp/ph15c-ex/ex04
// 运行：/tmp/ph15c-ex/ex04（无外部产物，退出码 0；实测输出见文件尾注释）
#include <stdio.h>
#include <string.h>

/* ============ 错误码定义（稳定: 显式数值 + 历史锁定注释） ============ */

enum cfg_err {
    CFG_OK = 0,
    /* 历史错误码：一经发布不得改值。新增错误只追加新项 */
    CFG_ERR_OPEN = -1,     /* 配置文件打不开           （历史, 勿改） */
    CFG_ERR_BADLINE = -2,  /* 某一行格式非法           （历史, 勿改） */
    CFG_ERR_UNKNOWNKEY = -3, /* 未知配置键             （历史, 勿改） */
    CFG_ERR_OOM = -4,      /* 内存不足                 （历史, 勿改） */
    /* 下面是从 2.x 版本新增的错误（继续向下追加, 不复用历史值） */
    CFG_ERR_VALUE = -5,    /* 值域非法（新增于 2.1）   */
};

/* 错误消息: 数值 → 一句话（供人读; 机器判断只用数值） */
static const char *cfg_strerror(int code) {
    switch (code) {
    case CFG_OK:           return "ok";
    case CFG_ERR_OPEN:     return "cannot open config file";
    case CFG_ERR_BADLINE:  return "malformed config line";
    case CFG_ERR_UNKNOWNKEY: return "unknown config key";
    case CFG_ERR_OOM:      return "out of memory";
    case CFG_ERR_VALUE:    return "config value out of range";
    default:               return "unknown error";
    }
}

/* ============ 可追踪错误详情（出参） ============ */

typedef struct {
    int code;              /* 错误码: 0 成功 / 负数为错 */
    int line;              /* 出错行号(配置文件内) */
    char detail[96];       /* 出错内容快照(该行原文) */
} errinfo_t;

static void errinfo_set(errinfo_t *e, int code, int line, const char *detail) {
    e->code = code;
    e->line = line;
    snprintf(e->detail, sizeof e->detail, "%s", detail);
}

/* ============ mini 配置加载器 ============ */

/* 模拟配置内容：第 2 行键合法, 第 3 行值域非法, 第 4 行未知键 */
static const char *g_lines[] = {
    "port=8080",
    "workers=4",
    "timeout=abc",     /* 值不是整数 → CFG_ERR_VALUE */
    "colormode=1",     /* 未知键    → CFG_ERR_UNKNOWNKEY */
};
static const int g_line_n = 4;

/* 解析第 idx 行（从 0 计）。成功返回 0；失败填 err 出参（含行号与原文快照） */
static int parse_line(int idx, errinfo_t *err) {
    const char *line = g_lines[idx];
    const char *eq = strchr(line, '=');
    int lineno = idx + 1;

    if (eq == NULL) {                              /* 没有 '=': 格式非法 */
        errinfo_set(err, CFG_ERR_BADLINE, lineno, line);
        return CFG_ERR_BADLINE;
    }

    if (strncmp(line, "port", (size_t)(eq - line)) == 0 ||
        strncmp(line, "workers", (size_t)(eq - line)) == 0) {
        /* 这两个键合法, 本示例不再深究整数值解析 */
        errinfo_set(err, CFG_OK, lineno, line);
        return CFG_OK;
    }

    if (strncmp(line, "timeout", (size_t)(eq - line)) == 0) {
        /* 值必须是纯数字, 这里模拟"值非法"分支（演示值域校验） */
        const char *v = eq + 1;
        for (; *v; v++) {
            if (*v < '0' || *v > '9') {
                errinfo_set(err, CFG_ERR_VALUE, lineno, line);
                return CFG_ERR_VALUE;
            }
        }
        errinfo_set(err, CFG_OK, lineno, line);
        return CFG_OK;
    }

    errinfo_set(err, CFG_ERR_UNKNOWNKEY, lineno, line);
    return CFG_ERR_UNKNOWNKEY;
}

int main(void) {
    printf("=== ex04 错误码设计 ===\n");
    printf("错误码(稳定, 发布后不改值): %s\n", cfg_strerror(CFG_ERR_UNKNOWNKEY));

    /* 逐行解析, 打印每行的可追踪错误详情 */
    for (int i = 0; i < g_line_n; i++) {
        errinfo_t err = {0};
        int rc = parse_line(i, &err);
        if (rc == CFG_OK) {
            printf("第 %d 行  OK    : %s\n", i + 1, err.detail);
        } else {
            printf("第 %d 行  错误码=%d (%s)\n", i + 1, rc, cfg_strerror(rc));
            printf("          出错行 %d, 原文 \"%s\"\n", err.line, err.detail);
        }
    }

    printf("\n可追踪 = 错误码(%d) + 行号(%d) + 原文快照(\"%s\") 三者一起上报\n",
           CFG_ERR_VALUE, 3, g_lines[2]);
    printf("稳定   = 数值发布后不改; 新增错误只追加不复用 (见 cfg_err 注释)\n");
    return 0;
}

/* 实测输出（本机一次运行, Apple clang 21.0.0, macOS arm64）：
 * === ex04 错误码设计 ===
 * 错误码(稳定, 发布后不改值): unknown config key
 * 第 1 行  OK    : port=8080
 * 第 2 行  OK    : workers=4
 * 第 3 行  错误码=-5 (config value out of range)
 *           出错行 3, 原文 "timeout=abc"
 * 第 4 行  错误码=-3 (unknown config key)
 *           出错行 4, 原文 "colormode=1"
 * 
 * 可追踪 = 错误码(-5) + 行号(3) + 原文快照("timeout=abc") 三者一起上报
 * 稳定   = 数值发布后不改; 新增错误只追加不复用 (见 cfg_err 注释)
 */
