/* bad_demos.c —— C 常见坑示例库: 10 类 UB 的"坏版本"
 * 警告: 本文件每个函数都是故意写错的 UB 演示, 禁止在生产代码中模仿。
 * 构建: 本文件用 -Wno-array-bounds/-Wno-uninitialized/-Wno-fortify-source
 * 抑制"故意触发的编译期警告"——这些警告本身就是教学点(编译期能拦一部分坑),
 * 详见 README「关于故意出错的代码」; 主文件 pitfall_catalog.c 保持零警告。
 * 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
 * 编译：make（或 cc -Wall -Wextra -std=c11 -O1 -g -fsanitize=address,undefined
 *       -fno-sanitize-recover=all -Wno-array-bounds -Wno-uninitialized
 *       -Wno-fortify-source -c bad_demos.c -o bad_demos.o）
 * 运行：./pitfall_catalog <名字>（每个坏版本都会被对应 Sanitizer 中止并报告;
 *       uninit/alias 两个坑工具抓不到, 会"跑完"——见 README 对应说明）
 * 验证状态：已验证（10 个坏版本全部实测, 报告关键行见 README 表格;
 *           本环境缺 llvm-symbolizer, ASan 栈帧未符号化）
 */
#include "pitfall.h"

#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void bad_oob(void) {
    int arr[3] = {1, 2, 3};
    arr[3] = 100;   /* UB: 越界写 1 个元素 —— ASan 报 stack-buffer-overflow */
    (void)arr[0];
}

void bad_null(void) {
    int *p = NULL;
    *p = 1;         /* UB: 解引用空指针 —— UBSan 报 store to null pointer */
}

void bad_uaf(void) {
    int *p = malloc(sizeof(int));
    if (p == NULL) return;
    *p = 7;
    free(p);
    printf("%d\n", *p); /* UB: use-after-free —— ASan 报 heap-use-after-free
                         * (先于 double free 中止; 单独看 double free 请注释这行) */
    free(p);            /* UB: double free —— ASan 报 attempting double-free */
}

void bad_overflow(void) {
    int a = INT_MAX;
    a = a + 1;      /* UB: 有符号溢出 —— UBSan 报 signed integer overflow */
    printf("%d\n", a);
}

void bad_uninit(void) {
    int x;              /* 未初始化: 栈垃圾值 */
    printf("%d\n", x);  /* UB: 读不确定值 —— 编译期 -Wuninitialized 警告;
                         * 运行时没有 Sanitizer 能抓(MSan 需全程序插桩, 属 ph11) */
}

void bad_alias(void) {
    uint32_t bits = 0x3F800000u;     /* float 1.0f 的位模式 */
    float f = *(float *)&bits;       /* UB: 类型双关违反严格别名 —— UBSan 不查,
                                      * 靠代码评审; 本环境 -O0~-O3 实测均输出 1 */
    printf("%g\n", f);
}

void bad_align(void) {
    unsigned char buf[16] = {0};
    memcpy(buf + 1, "\x00\x00\x00\x01", 4);
    uint32_t *p = (uint32_t *)(buf + 1); /* p 未 4 字节对齐 */
    printf("%u\n", *p);                  /* UB: 未对齐读 —— UBSan 报 misaligned address */
}

void bad_divzero(void) {
    int d = 0;
    printf("%d\n", 100 / d); /* UB: 整数除零 —— UBSan 报 division by zero
                              * (裸跑在 x86 上 SIGFPE、arm64 上可能静默得 0) */
}

void bad_shift(void) {
    int s = 1 << 31;         /* UB: 移位位数 == int 位宽 —— UBSan 报 shift */
    (void)s;
}

void bad_strbuf(void) {
    char buf[4];
    strcpy(buf, "hello world!"); /* UB: 缓冲区溢出 —— ASan 报 stack-buffer-overflow
                                  * (编译期另有 -Wfortify-source 警告, 已实测) */
    printf("%s\n", buf);
}
