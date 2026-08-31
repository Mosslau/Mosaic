/* pitfall_catalog.c —— C 常见坑示例库: 主程序
 * 把本阶段 10 类 UB 各写成"坏版本 + 好版本"两件套(坏版本被 Sanitizer 中止并
 * 报告, 好版本安全运行), 配 Makefile 一键编译/自检/逐个演示:
 *   ./pitfall_catalog list        —— 列出全部坑与检测工具(评审检查清单)
 *   ./pitfall_catalog <名字>      —— 触发该坑坏版本, 看 Sanitizer 报告
 *   ./pitfall_catalog <名字> good —— 运行该坑好版本(安全写法)
 *   ./pitfall_catalog check       —— 依次运行全部好版本并自检
 *   make demos                    —— 逐个触发 10 个坏版本(循环, 不因中止而停)
 * 本文件要求 -Wall -Wextra 零警告; 坏版本单独放在 bad_demos.c(故意触发警告,
 * 已在 Makefile 里用 -Wno-* 抑制)。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：make（构建命令见 Makefile; 也可 cc -Wall -Wextra -std=c11 -O1 -g
//       -fsanitize=address,undefined -fno-sanitize-recover=all pitfall_catalog.c
//       bad_demos.c -o pitfall_catalog）
// 运行/测试：make check（自检退出码 0）; make demos（逐个演示坏版本）
// 验证状态：已验证（构建零警告; make check 通过、退出码 0; 10 个坏版本报告
//           全部实测, 见 README 表格）
#include "pitfall.h"

#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---------- 10 个好版本: 修复后的安全写法 ---------- */

static void good_oob(void) {
    int arr[3] = {1, 2, 3};
    size_t i = 3;                     /* 想写"第 4 个元素" */
    if (i < 3)
        arr[i] = 100;
    else
        printf("good_oob: 索引 i=%zu 越界被拦截\n", i);
}

static void good_null(void) {
    int *p = NULL;
    if (p != NULL)
        *p = 1;
    else
        printf("good_null: 空指针在解引用前被拦截\n");
}

static void good_uaf(void) {
    int *p = malloc(sizeof(int));
    if (p == NULL) {
        printf("good_uaf: malloc 失败\n");
        return;
    }
    *p = 7;
    free(p);
    p = NULL;                         /* 置 NULL: 重复 free 变无害, 再解引用立即崩(可发现) */
    printf("good_uaf: free 后置 NULL, 无 use-after-free / double free\n");
}

static void good_overflow(void) {
    int a = INT_MAX;
    if (a > INT_MAX - 1)
        printf("good_overflow: %d + 1 溢出被拦截\n", a);
    else
        printf("good_overflow: sum=%d\n", a + 1);
}

static void good_uninit(void) {
    int x = 0;                        /* 声明即初始化 */
    printf("good_uninit: x=%d\n", x);
}

static void good_alias(void) {
    uint32_t bits = 0x3F800000u;
    float f;
    memcpy(&f, &bits, sizeof f);      /* 位模式搬运一律 memcpy(编译器优化为单指令) */
    printf("good_alias: %g (memcpy 正解)\n", f);
}

static void good_align(void) {
    unsigned char buf[16] = {0};
    memcpy(buf + 1, "\x00\x00\x00\x01", 4);
    uint32_t v;
    memcpy(&v, buf + 1, sizeof v);    /* 先 memcpy 到对齐的本地变量, 再读字段 */
    printf("good_align: %u (memcpy 到对齐变量)\n", v);
}

static void good_divzero(void) {
    int d = 0;
    if (d == 0)
        printf("good_divzero: 除数为 0 被拦截\n");
    else
        printf("good_divzero: q=%d\n", 100 / d);
}

static void good_shift(void) {
    int n = 31;
    if (n >= 0 && n < 32)
        printf("good_shift: 1u << %d = %u\n", n, 1u << n);   /* 无符号 + 位数检查 */
    else
        printf("good_shift: 移位位数 %d 非法\n", n);
}

static void good_strbuf(void) {
    char buf[4];
    snprintf(buf, sizeof buf, "%s", "hello world!");  /* 保证 \0, 超长截断 */
    printf("good_strbuf: %s (截断为 %zu 字节, 保证 \\0)\n", buf, strlen(buf));
}

/* ---------- 坑目录表: 名字 / 中文名 / 检测工具 / 识别要点 ---------- */

const pitfall_t g_pitfalls[] = {
    {"oob",      "数组越界",          "ASan(-fsanitize=address)",        "arr[i] 的 i 越界: 越界写比越界读危险(可能覆盖返回地址)", bad_oob,      good_oob},
    {"null",     "空指针解引用",      "UBSan(-fsanitize=undefined)",     "解引用 NULL: 实际平台几乎总段错误, 标准层面是 UB",       bad_null,     good_null},
    {"uaf",      "悬空指针/UAF/重复释放", "ASan",                         "free 后使用、重复 free: 破坏堆元数据",                  bad_uaf,      good_uaf},
    {"overflow", "有符号整数溢出",    "UBSan",                            "INT_MAX+1 是 UB; 无符号回绕才是定义行为",               bad_overflow, good_overflow},
    {"uninit",   "未初始化变量",      "编译期 -Wuninitialized",           "读栈垃圾值: 不确定值, 优化器可按任意值推理",            bad_uninit,   good_uninit},
    {"alias",    "类型双关/严格别名", "代码评审(工具抓不到)",             "*(float*)&u32 是 UB; 位模式搬运一律 memcpy",            bad_alias,    good_alias},
    {"align",    "未对齐访问",        "UBSan(-fsanitize=alignment)",      "从字节流偏移处强转读字段是 UB",                        bad_align,    good_align},
    {"divzero",  "整数除零/INT_MIN/-1", "UBSan",                          "整数除零是 UB(浮点除零是定义行为, 得 ±inf)",           bad_divzero,  good_divzero},
    {"shift",    "非法移位",          "UBSan",                            "移位位数 ≥ 位宽或为负是 UB",                           bad_shift,    good_shift},
    {"strbuf",   "字符串缓冲区溢出",  "ASan + 编译期 -Wfortify-source",   "strcpy 不检查容量: 历史漏洞重灾区",                    bad_strbuf,   good_strbuf},
};
const size_t g_pitfall_count = sizeof g_pitfalls / sizeof g_pitfalls[0];

/* ---------- 主程序 ---------- */

static const pitfall_t *find_pitfall(const char *name) {
    for (size_t i = 0; i < g_pitfall_count; i++)
        if (strcmp(g_pitfalls[i].name, name) == 0)
            return &g_pitfalls[i];
    return NULL;
}

static void usage(const char *prog) {
    fprintf(stderr, "用法: %s <名字> [good] | list | check\n", prog);
    fprintf(stderr, "  <名字>        运行该坑的坏版本(UB, 被 Sanitizer 中止并报告)\n");
    fprintf(stderr, "  <名字> good   运行该坑的好版本(安全写法)\n");
    fprintf(stderr, "  list          列出全部坑与检测工具(代码评审检查清单)\n");
    fprintf(stderr, "  check         依次运行全部好版本并自检\n");
}

int main(int argc, char **argv) {
    if (argc < 2) {
        usage(argv[0]);
        return 2;
    }
    if (strcmp(argv[1], "list") == 0) {
        printf("%-9s %-26s %-34s %s\n", "名字", "坑", "检测工具", "识别要点");
        for (size_t i = 0; i < g_pitfall_count; i++)
            printf("%-9s %-26s %-34s %s\n", g_pitfalls[i].name, g_pitfalls[i].title,
                   g_pitfalls[i].tool, g_pitfalls[i].desc);
        return 0;
    }
    if (strcmp(argv[1], "check") == 0) {
        for (size_t i = 0; i < g_pitfall_count; i++)
            g_pitfalls[i].good();
        printf("自检完成: %zu 个好版本全部运行, 无 Sanitizer 报告\n", g_pitfall_count);
        return 0;
    }
    const pitfall_t *p = find_pitfall(argv[1]);
    if (p == NULL) {
        fprintf(stderr, "未知坑: %s (list 查看全部)\n", argv[1]);
        return 2;
    }
    if (argc > 2 && strcmp(argv[2], "good") == 0) {
        p->good();
        return 0;
    }
    fprintf(stderr, "===== 触发 [%s] %s 坏版本 (%s) =====\n",
            p->name, p->title, p->tool);
    p->bad();   /* 坏版本通常被 Sanitizer 中止, 不会执行到下一行 */
    fprintf(stderr, "===== 没有 Sanitizer 报告? 这个坑运行时工具抓不到(uninit/alias),\n");
    fprintf(stderr, "     靠编译期警告与代码评审 —— 这正是「识别工具」的边界 =====\n");
    return 0;
}
