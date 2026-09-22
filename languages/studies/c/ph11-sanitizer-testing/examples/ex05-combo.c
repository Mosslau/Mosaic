/* ex05-combo.c —— ASan+UBSan 组合: 一次编译, 地址错误与逻辑错误双管齐下
 * 运行前提: 三个模式都要用 -fsanitize=address,undefined 编译运行
 *   （badmem/badlogic 是故意出错的演示, 裸跑行为不可预测/无意义）
 * 用法: ./ex05 safe | badmem | badlogic
 *    safe   : 正确的动态数组 push/get（含边界检查）→ 零报告, 退出码 0
 *    badmem : 越界写 → ASan 报 heap-buffer-overflow
 *    badlogic: 有符号溢出 → UBSan 报 signed integer overflow
 * 编译: cc -Wall -Wextra -std=c11 -fsanitize=address,undefined -g ex05-combo.c -o ex05
 *   （CI 的标准组合: -fsanitize=address,undefined 一次编译两种都查;
 *     加 -fno-sanitize-recover=undefined 可让 UBSan 报错即中止）
 * 验证环境: Apple clang 21.0.0（cc，macOS arm64）
 * 验证状态: 已验证（三种模式输出见 README 表格与主文档示例 5）
 */
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* 极简动态数组（ph04 动态数组的缩小版）: push 带边界检查与扩容失败路径 */
typedef struct {
    int   *data;
    size_t len;
    size_t cap;
} IntVec;

static int vec_init(IntVec *v, size_t cap) {
    if (v == NULL) return -1;
    cap = cap ? cap : 1;                           /* 0 容量退化为 1, 与 ex06 一致(防扩容死循环) */
    if (cap > SIZE_MAX / sizeof(int)) return -1;   /* 字节数溢出防护(防御性) */
    v->data = malloc(cap * sizeof(int));
    if (v->data == NULL) return -1;
    v->len = 0;
    v->cap = cap;
    return 0;
}

static void vec_destroy(IntVec *v) {
    if (v == NULL) return;
    free(v->data);
    v->data = NULL;
    v->len = v->cap = 0;
}

static int vec_push(IntVec *v, int val) {
    if (v == NULL) return -1;
    if (v->len == v->cap) {                    /* 满了: 2 倍扩容 */
        if (v->cap > SIZE_MAX / 2) return -1;  /* 扩容溢出防护(防御性) */
        size_t new_cap = v->cap * 2;
        if (new_cap > SIZE_MAX / sizeof(int)) return -1;  /* 字节数溢出防护(防御性) */
        int *tmp = realloc(v->data, new_cap * sizeof(int));
        if (tmp == NULL) return -1;            /* 扩容失败: 原数据不丢 */
        v->data = tmp;
        v->cap = new_cap;
    }
    v->data[v->len++] = val;
    return 0;
}

static int vec_get(const IntVec *v, size_t idx, int *out) {
    if (v == NULL || out == NULL) return -1;
    if (idx >= v->len) return -1;              /* 边界检查: 越界返回 -1 */
    *out = v->data[idx];
    return 0;
}

/* safe: 正确代码在组合 Sanitizer 下必须零报告 */
static void demo_safe(void) {
    IntVec v;
    if (vec_init(&v, 4) != 0) return;
    for (int i = 0; i < 100; i++)              /* 越过初始容量, 触发 2x 扩容 */
        vec_push(&v, i);
    int val = -1;
    if (vec_get(&v, 99, &val) == 0)
        printf("v[99]=%d len=%zu (组合 Sanitizer 零报告)\n", val, v.len);
    if (vec_get(&v, 100, &val) != 0)
        printf("v[100] 越界被拦截\n");
    vec_destroy(&v);
}

/* badmem: 故意去掉边界检查 → ASan 抓越界写 */
static void demo_badmem(void) {
    IntVec v;
    if (vec_init(&v, 4) != 0) return;
    vec_push(&v, 1);
    int *p = v.data;
    p[5] = 999;                                /* 故意越界写(绕过 get 的检查) */
    printf("写完了(到不了这行)\n");
    vec_destroy(&v);
}

/* badlogic: 故意有符号溢出 → UBSan 抓逻辑错误 */
static void demo_badlogic(void) {
    int a = INT_MAX;
    int b = a + 1;                             /* 故意溢出 */
    printf("b = %d\n", b);
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "用法: %s safe|badmem|badlogic\n", argv[0]);
        return 2;
    }
    if (strcmp(argv[1], "safe") == 0)
        demo_safe();
    else if (strcmp(argv[1], "badmem") == 0)
        demo_badmem();
    else if (strcmp(argv[1], "badlogic") == 0)
        demo_badlogic();
    else {
        fprintf(stderr, "未知模式: %s\n", argv[1]);
        return 2;
    }
    return 0;
}
