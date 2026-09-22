// 来源：project/ —— darray 动态数组库实现
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99
// 编译：gcc -Wall -Wextra -std=c99 darray.c main.c -o darray
// 验证状态：已验证
#include "darray.h"

#include <stdlib.h>

#define DARRAY_MIN_CAP 4
#define DARRAY_SHRINK_THRESHOLD 16  /* 容量低于此值不缩容 */

DArray *darray_create(void) {
    DArray *da = malloc(sizeof(DArray));
    if (da == NULL) return NULL;
    da->data = malloc(DARRAY_MIN_CAP * sizeof(int));
    if (da->data == NULL) {
        free(da);
        return NULL;
    }
    da->len = 0;
    da->cap = DARRAY_MIN_CAP;
    da->last_err = 0;
    return da;
}

void darray_destroy(DArray *da) {
    if (da == NULL) return;
    free(da->data);
    da->data = NULL;
    da->len = da->cap = 0;
    free(da);
}

int darray_push(DArray *da, int val) {
    if (da == NULL) return -1;
    if (da->len == da->cap) {
        size_t new_cap = da->cap * 2;
        int *tmp = realloc(da->data, new_cap * sizeof(int));
        if (tmp == NULL) {
            da->last_err = 1;   /* 扩容失败：原数据不丢失 */
            return -1;
        }
        da->data = tmp;
        da->cap  = new_cap;
    }
    da->data[da->len++] = val;
    return 0;
}

int darray_pop(DArray *da) {
    if (da == NULL || da->len == 0) {
        if (da) da->last_err = 1;   /* 空数组 pop */
        return 0;
    }
    int val = da->data[--da->len];
    /* 使用率 < 25% 且容量 > 阈值时缩容 */
    if (da->cap > DARRAY_SHRINK_THRESHOLD && da->len < da->cap / 4) {
        size_t new_cap = da->cap / 2;
        int *tmp = realloc(da->data, new_cap * sizeof(int));
        if (tmp != NULL) {
            da->data = tmp;
            da->cap  = new_cap;
        }
    }
    return val;
}

int darray_get(const DArray *da, size_t idx) {
    /* 只读查询：不修改 da（const），越界仅返回 0，由调用者判断 */
    if (da == NULL || idx >= da->len) return 0;
    return da->data[idx];
}

int darray_set(DArray *da, size_t idx, int val) {
    if (da == NULL || idx >= da->len) {
        if (da) da->last_err = 1;   /* 越界写 */
        return -1;
    }
    da->data[idx] = val;
    return 0;
}

size_t darray_size(const DArray *da) {
    return da ? da->len : 0;
}

size_t darray_capacity(const DArray *da) {
    return da ? da->cap : 0;
}
