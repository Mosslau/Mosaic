/* ex01-asan.c —— ASan 抓两类地址错误: 栈越界写 与 堆 use-after-free
 * 运行前提: 必须用 -fsanitize=address 编译运行, 否则勿运行
 *   （越界写会破坏相邻栈内存, UAF 读的是已归还的内存——裸跑行为不可预测）
 * 用法: ./ex01 oob | uaf
 *    oob: 数组越界写 → ERROR: AddressSanitizer: stack-buffer-overflow
 *    uaf: free 后读取  → ERROR: AddressSanitizer: heap-use-after-free
 * 验证环境: Apple clang 21.0.0（cc，macOS arm64）
 * 编译: cc -Wall -Wextra -std=c11 -fsanitize=address -g ex01-asan.c -o ex01
 *       （oob 演示会触发编译期 -Warray-bounds 警告——编译器内建的静态越界
 *         检查, 这是教学点; uaf 则只能靠 ASan 在运行时抓）
 * 运行: ./ex01 oob / ./ex01 uaf（均被 ASan 中止, 退出码 134）
 * 验证状态: 已验证（两种报告关键行见 README 表格与主文档示例 1）
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* 故意越界写: ASan 报 stack-buffer-overflow */
static void demo_oob(void) {
    int arr[3] = {1, 2, 3};
    printf("arr[0]=%d\n", arr[0]);
    arr[3] = 100;          /* 故意越界写 1 个元素 */
    printf("写完了(到不了这行)\n");
}

/* 故意 use-after-free: ASan 报 heap-use-after-free（附分配/释放两段栈） */
static void demo_uaf(void) {
    int *p = malloc(sizeof(int));
    if (p == NULL) return;
    *p = 7;
    free(p);
    printf("%d\n", *p);    /* 故意在 free 后读取 */
    free(p);               /* 故意 double free（第一个错误已中止, 到不了这里） */
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "用法: %s oob|uaf\n", argv[0]);
        return 2;
    }
    if (strcmp(argv[1], "oob") == 0)
        demo_oob();
    else if (strcmp(argv[1], "uaf") == 0)
        demo_uaf();
    else {
        fprintf(stderr, "未知模式: %s\n", argv[1]);
        return 2;
    }
    return 0;
}
