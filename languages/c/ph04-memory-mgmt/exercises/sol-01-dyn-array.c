// 来源：exercises/README.md 练习 1 —— 动态数组参考实现
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99 零警告
// 编译：gcc -Wall -Wextra -std=c99 sol-01-dyn-array.c -o sol-01-dyn-array
// 运行：./sol-01-dyn-array
// 验证状态：已验证
#include <stdio.h>
#include <stdlib.h>

typedef struct {
    int   *data;
    size_t len;
    size_t cap;
    int    empty_pop;   /* 空数组 pop 的错误标记 */
} DynArray;

int da_init(DynArray *da) {
    da->data = malloc(4 * sizeof(int));
    if (da->data == NULL) return -1;
    da->len = 0;
    da->cap = 4;
    da->empty_pop = 0;
    return 0;
}

void da_destroy(DynArray *da) {
    free(da->data);
    da->data = NULL;
    da->len = da->cap = 0;
}

int da_push(DynArray *da, int val) {
    if (da->len == da->cap) {
        size_t new_cap = da->cap * 2;
        int *tmp = realloc(da->data, new_cap * sizeof(int));
        if (tmp == NULL) return -1;   /* 扩容失败，原数据不丢失 */
        da->data = tmp;
        da->cap  = new_cap;
    }
    da->data[da->len++] = val;
    return 0;
}

int da_pop(DynArray *da) {
    if (da->len == 0) {
        da->empty_pop = 1;            /* 置错误标记 */
        return 0;
    }
    return da->data[--da->len];
}

/* 使用率 < 25% 时容量减半 */
void da_shrink(DynArray *da) {
    if (da->len < da->cap / 4 && da->cap > 4) {
        size_t new_cap = da->cap / 2;
        int *tmp = realloc(da->data, new_cap * sizeof(int));
        if (tmp != NULL) { da->data = tmp; da->cap = new_cap; }
    }
}

int main(void) {
    DynArray da;
    if (da_init(&da) != 0) return 1;

    for (int i = 0; i < 20; i++) {
        if (da_push(&da, i) != 0) { fprintf(stderr, "push 失败\n"); return 1; }
    }
    printf("插入 20 个后: len=%zu, cap=%zu\n", da.len, da.cap);

    /* 弹出到只剩 4 个 */
    while (da.len > 4) da_pop(&da);
    da_shrink(&da);
    printf("弹出到 4 个后: len=%zu, cap=%zu, data=[", da.len, da.cap);
    for (size_t i = 0; i < da.len; i++)
        printf("%d%s", da.data[i], i < da.len - 1 ? ", " : "");
    printf("]\n");

    /* 空数组 pop 测试 */
    while (da.len > 0) da_pop(&da);
    da_pop(&da);
    printf("空数组 pop 错误标记: %d\n", da.empty_pop);

    da_destroy(&da);
    return 0;
}
