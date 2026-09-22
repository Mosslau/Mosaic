// examples/ex06-handle-api.c —— handle-based API/opaque pointer：承接 ph14（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
// 编译：mkdir -p /tmp/ph15c-ex && cc -Wall -Wextra -std=c11 ex06-handle-api.c -o /tmp/ph15c-ex/ex06
// 运行：/tmp/ph15c-ex/ex06（无外部产物，退出码 0；实测输出见文件尾注释）
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#include <windows.h>      /* Sleep 等平台 API —— Windows 分支, 未在本环境验证 */
#endif

/* ============ 错误码（稳定数值, 头文件级契约） ============ */

enum {
    CFG_OK = 0,
    CFG_ERR_BADARG = -1,    /* 参数非法: NULL / 空 name / 超长 */
    CFG_ERR_NOMEM = -2,     /* 内存不足 */
    CFG_ERR_BADOP = -3,     /* 操作不被当前状态允许 */
};

/* ============ 公开 API（仿头文件; 教学上放同一文件, 工程上拆 .h/.c） ============ */

typedef struct cfg cfg_t;   /* opaque 句柄 */

cfg_t *cfg_create(const char *name, int32_t *err);   /* create: 失败返回 NULL */
int32_t cfg_set(cfg_t *c, const char *key, int64_t val);   /* 写入一个键值 */
int32_t cfg_get(const cfg_t *c, const char *key, int64_t *out); /* 读键值 */
const char *cfg_name(const cfg_t *c);   /* 借用内部 name, 不得 free */
int32_t cfg_destroy(cfg_t *c);          /* 谁 create 谁 destroy */
const char *cfg_strerror(int32_t err);  /* 错误消息(静态串, 借用) */

/* 跨平台探测宏: 输出编译目标平台（供诊断与演示条件编译） */
#if defined(__APPLE__)
#define CFG_PLATFORM "macOS (Apple)"
#elif defined(__linux__)
#define CFG_PLATFORM "Linux"
#elif defined(_WIN32)
#define CFG_PLATFORM "Windows"
#else
#define CFG_PLATFORM "unknown POSIX"
#endif

/* ============ 实现（opaque 结构体只在这里出现） ============ */

#define CFG_MAX_NAME 32
#define CFG_MAX_KEYS 8

typedef struct {
    char key[16];
    int64_t val;
} kv_t;

struct cfg {
    char name[CFG_MAX_NAME];
    kv_t kvs[CFG_MAX_KEYS];
    int nkvs;
};

cfg_t *cfg_create(const char *name, int32_t *err) {
    if (err) *err = CFG_OK;
    if (name == NULL || name[0] == '\0') {
        if (err) *err = CFG_ERR_BADARG;
        return NULL;
    }
    if (strlen(name) >= CFG_MAX_NAME) {
        if (err) *err = CFG_ERR_BADARG;
        return NULL;
    }
    cfg_t *c = (cfg_t *)calloc(1, sizeof *c);   /* calloc: 自动清零字段 */
    if (c == NULL) {
        if (err) *err = CFG_ERR_NOMEM;
        return NULL;
    }
    snprintf(c->name, sizeof c->name, "%s", name);
    c->nkvs = 0;
    return c;
}

int32_t cfg_set(cfg_t *c, const char *key, int64_t val) {
    if (c == NULL || key == NULL || key[0] == '\0')
        return CFG_ERR_BADARG;
    for (int i = 0; i < c->nkvs; i++) {           /* 已存在: 覆盖 */
        if (strcmp(c->kvs[i].key, key) == 0) {
            c->kvs[i].val = val;
            return CFG_OK;
        }
    }
    if (c->nkvs >= CFG_MAX_KEYS)
        return CFG_ERR_BADOP;                     /* 满了: 操作不被允许 */
    snprintf(c->kvs[c->nkvs].key, sizeof c->kvs[c->nkvs].key, "%s", key);
    c->kvs[c->nkvs].val = val;
    c->nkvs++;
    return CFG_OK;
}

int32_t cfg_get(const cfg_t *c, const char *key, int64_t *out) {
    if (c == NULL || key == NULL || out == NULL)
        return CFG_ERR_BADARG;
    for (int i = 0; i < c->nkvs; i++) {
        if (strcmp(c->kvs[i].key, key) == 0) {
            *out = c->kvs[i].val;
            return CFG_OK;
        }
    }
    return CFG_ERR_BADOP;   /* 键不存在（本示例 BADOP 兼作 not-found, 见文档） */
}

const char *cfg_name(const cfg_t *c) {
    return c == NULL ? "" : c->name;   /* 借用内部缓冲区, 调用方不得 free */
}

int32_t cfg_destroy(cfg_t *c) {
    if (c == NULL)
        return CFG_ERR_BADARG;
    free(c);                             /* 谁 create 谁 destroy */
    return CFG_OK;
}

const char *cfg_strerror(int32_t err) {
    switch (err) {
    case CFG_OK:         return "ok";
    case CFG_ERR_BADARG: return "bad argument";
    case CFG_ERR_NOMEM:  return "out of memory";
    case CFG_ERR_BADOP:  return "operation not allowed / key not found";
    default:             return "unknown error";
    }
}

/* ============ 演示 ============ */

int main(void) {
    printf("=== ex06 handle-based API (opaque pointer) ===\n");
    printf("编译平台: %s (条件编译宏 __APPLE__/__linux__/_WIN32 决定)\n",
           CFG_PLATFORM);

    int32_t err = CFG_OK;
    cfg_t *c = cfg_create("demo-config", &err);
    if (c == NULL) {
        printf("create 失败: %s\n", cfg_strerror(err));
        return 1;
    }

    printf("create 成功: name=%s (借用指针)\n", cfg_name(c));

    int64_t v = 0;
    printf("cfg_set(port, 8080) = %d\n", cfg_set(c, "port", 8080));
    printf("cfg_set(timeout, 30) = %d\n", cfg_set(c, "timeout", 30));
    printf("cfg_get(port) rc=%d val=%lld\n", cfg_get(c, "port", &v),
           (long long)v);
    cfg_set(c, "port", 9090);                  /* 覆盖已有键 */
    cfg_get(c, "port", &v);
    printf("cfg_set(port,9090) 覆盖后 cfg_get(port) val=%lld\n", (long long)v);

    /* 错误路径: 不存在的键 */
    int rc = cfg_get(c, "nope", &v);
    printf("cfg_get(nope): rc=%d (%s)\n", rc, cfg_strerror(rc));

    printf("destroy rc=%d\n", cfg_destroy(c));
    return 0;
}

/* 实测输出（本机一次运行, Apple clang 21.0.0, macOS arm64）：
 * === ex06 handle-based API (opaque pointer) ===
 * 编译平台: macOS (Apple) (条件编译宏 __APPLE__/__linux__/_WIN32 决定)
 * create 成功: name=demo-config (借用指针)
 * cfg_set(port, 8080) = 0
 * cfg_set(timeout, 30) = 0
 * cfg_get(port) rc=0 val=8080
 * cfg_set(port,9090) 覆盖后 cfg_get(port) val=9090
 * cfg_get(nope): rc=-3 (operation not allowed / key not found)
 * destroy rc=0
 */
