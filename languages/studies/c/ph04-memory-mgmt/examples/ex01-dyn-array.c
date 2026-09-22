// 来源：04-memory-mgmt.md 第 6 章示例 1 —— 动态数组（含扩容与缩容）
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99 零警告
// 编译：gcc -Wall -Wextra -std=c99 ex01-dyn-array.c -o ex01-dyn-array
// 运行：./ex01-dyn-array
// 验证状态：已验证
#include <stdio.h>
#include <stdlib.h>

typedef struct {
    int   *data;
    size_t len;   /* 已使用的元素数 */
    size_t cap;   /* 已分配的容量（元素数） */
} DynArray;

int da_init(DynArray *da) {
    da->data = malloc(4 * sizeof(int));
    if (da->data == NULL) return -1;
    da->len = 0;
    da->cap = 4;
    return 0;
}

void da_destroy(DynArray *da) {
    free(da->data);
    da->data = NULL;
    da->len = da->cap = 0;
}

/* 追加元素，容量不够时自动 2x 扩容 */
int da_push(DynArray *da, int val) {
    if (da->len == da->cap) {
        size_t new_cap = da->cap * 2;
        int *tmp = realloc(da->data, new_cap * sizeof(int));
        if (tmp == NULL) return -1;  /* 扩容失败，原数据不丢失 */
        da->data = tmp;
        da->cap  = new_cap;
    }
    da->data[da->len++] = val;
    return 0;
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

    for (int i = 0; i < 20; i++)
        da_push(&da, i * 10);
    printf("插入 20 个后: len=%zu, cap=%zu\n", da.len, da.cap);

    da.len = 4;  /* 模拟弹出到只剩 4 个元素 */
    da_shrink(&da);
    printf("缩容后: len=%zu, cap=%zu, data=[", da.len, da.cap);
    for (size_t i = 0; i < da.len; i++)
        printf("%d%s", da.data[i], i < da.len - 1 ? ", " : "");
    printf("]\n");

    da_destroy(&da);
    return 0;
}
