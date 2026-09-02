/* sol-03-cli-parser.c —— 参考实现: 命令行解析器（表驱动选项 + 错误码）
 *
 * 题目要点: 选项表(数组)描述每个选项: 短名/长名/是否带值/目标字段;
 *   解析 argv 时逐项查表, 未知选项/缺值返回稳定错误码; 选项表可复用
 *   于不同命令（再配一张"命令动作"函数指针表即成通用 CLI 框架）。
 * 实测: 支持 --port 8080 -h 10.0.0.1 -v --workers 4 与非法选项/缺值路径。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-03-cli-parser.c -o sol03
// 运行：./sol03（内部 argv 演示, 无外部产物, 退出码 0）
// 验证状态：已验证（零警告; 解析结果/两个错误路径为实测, 见文件尾）
#include <stdio.h>
#include <string.h>

/* ---- 稳定错误码 ---- */
enum {
    CLI_OK = 0,
    CLI_ERR_UNKNOWN = -1,   /* 未知选项 */
    CLI_ERR_NOVALUE = -2,   /* 选项缺值 */
    CLI_ERR_BADVALUE = -3,  /* 值格式非法 */
};

/* ---- 选项表条目: 把"长名/短名/带值与否"声明成数据 ---- */
typedef struct {
    const char *long_name;   /* 如 "port" 对应 --port */
    char short_name;         /* 如 'p' 对应 -p, 0 = 无短名 */
    int takes_value;         /* 1 = 需要跟随一个值 */
    const char *help;
} opt_spec_t;

static const opt_spec_t g_opts[] = {
    { "host",    'h', 1, "监听地址" },
    { "port",    'p', 1, "监听端口" },
    { "verbose", 'v', 0, "详细输出" },
    { "workers", 'w', 1, "工作线程数" },
};
#define OPT_N ((int)(sizeof g_opts / sizeof g_opts[0]))

/* ---- 解析结果 ---- */
typedef struct {
    const char *host;
    int port;
    int verbose;
    int workers;
} cfg_t;

static int cfg_apply(cfg_t *cfg, const opt_spec_t *spec, const char *value) {
    if (strcmp(spec->long_name, "host") == 0)    { cfg->host = value; return CLI_OK; }
    if (strcmp(spec->long_name, "port") == 0) {
        if (sscanf(value, "%d", &cfg->port) != 1 || cfg->port <= 0)
            return CLI_ERR_BADVALUE;
        return CLI_OK;
    }
    if (strcmp(spec->long_name, "verbose") == 0) { cfg->verbose = 1; return CLI_OK; }
    if (strcmp(spec->long_name, "workers") == 0) {
        if (sscanf(value, "%d", &cfg->workers) != 1 || cfg->workers <= 0)
            return CLI_ERR_BADVALUE;
        return CLI_OK;
    }
    return CLI_ERR_UNKNOWN;
}

/* 解析器主体: 遍历 argv, 命中选项表即应用; 返回错误码或 CLI_OK */
static int cli_parse(int argc, char **argv, cfg_t *cfg) {
    for (int i = 1; i < argc; i++) {
        const char *arg = argv[i];
        const opt_spec_t *hit = NULL;

        for (int k = 0; k < OPT_N; k++) {          /* 查表 */
            if ((arg[0] == '-' && arg[1] != '-' &&
                 arg[1] == g_opts[k].short_name) ||
                (arg[0] == '-' && arg[1] == '-' &&
                 strcmp(arg + 2, g_opts[k].long_name) == 0)) {
                hit = &g_opts[k];
                break;
            }
        }
        if (hit == NULL)
            return CLI_ERR_UNKNOWN;                /* 未知选项 */

        const char *value = NULL;
        if (hit->takes_value) {
            if (i + 1 >= argc)
                return CLI_ERR_NOVALUE;            /* 缺值 */
            value = argv[++i];
        }
        int rc = cfg_apply(cfg, hit, value);
        if (rc != CLI_OK)
            return rc;
    }
    return CLI_OK;
}

static const char *cli_strerror(int rc) {
    switch (rc) {
    case CLI_OK:          return "ok";
    case CLI_ERR_UNKNOWN: return "unknown option";
    case CLI_ERR_NOVALUE: return "option requires a value";
    case CLI_ERR_BADVALUE:return "bad value";
    default:              return "unknown error";
    }
}

static void dump(const char *title, int rc, const cfg_t *c) {
    printf("%s → rc=%d (%s)\n", title, rc, cli_strerror(rc));
    printf("   host=%s port=%d verbose=%d workers=%d\n",
           c->host, c->port, c->verbose, c->workers);
}

int main(void) {
    printf("=== sol-03 命令行解析器 ===\n");

    /* 用例 1: 合法参数（长短名混用, -v 无值） */
    {
        cfg_t cfg = {"0.0.0.0", 0, 0, 0};
        char *argv[] = {"prog", "--host", "10.0.0.1", "-p", "8080", "-v",
                        "--workers", "4"};
        int rc = cli_parse(8, argv, &cfg);
        dump("用例1: --host 10.0.0.1 -p 8080 -v --workers 4", rc, &cfg);
    }
    /* 用例 2: 未知选项 */
    {
        cfg_t cfg = {"0.0.0.0", 0, 0, 0};
        char *argv[] = {"prog", "--host", "10.0.0.1", "--nope"};
        int rc = cli_parse(4, argv, &cfg);
        dump("用例2: --host 10.0.0.1 --nope (未知选项)", rc, &cfg);
    }
    /* 用例 3: 缺值 */
    {
        cfg_t cfg = {"0.0.0.0", 0, 0, 0};
        char *argv[] = {"prog", "-p"};
        int rc = cli_parse(2, argv, &cfg);
        dump("用例3: -p (缺值)", rc, &cfg);
    }
    /* 用例 4: 值非法 */
    {
        cfg_t cfg = {"0.0.0.0", 0, 0, 0};
        char *argv[] = {"prog", "--port", "abc"};
        int rc = cli_parse(3, argv, &cfg);
        dump("用例4: --port abc (值非法)", rc, &cfg);
    }

    printf("选项表 %d 条 (数据驱动): 加新选项只改表 + cfg_apply, 解析器主体不动\n",
           OPT_N);
    return 0;
}

/* 实测输出（本机一次运行, Apple clang 21.0.0, macOS arm64）：
 * === sol-03 命令行解析器 ===
 * 用例1: --host 10.0.0.1 -p 8080 -v --workers 4 → rc=0 (ok)
 *    host=10.0.0.1 port=8080 verbose=1 workers=4
 * 用例2: --host 10.0.0.1 --nope (未知选项) → rc=-1 (unknown option)
 *    host=10.0.0.1 port=0 verbose=0 workers=0
 * 用例3: -p (缺值) → rc=-2 (option requires a value)
 *    host=0.0.0.0 port=0 verbose=0 workers=0
 * 用例4: --port abc (值非法) → rc=-3 (bad value)
 *    host=0.0.0.0 port=0 verbose=0 workers=0
 * 选项表 4 条 (数据驱动): 加新选项只改表 + cfg_apply, 解析器主体不动
 */
