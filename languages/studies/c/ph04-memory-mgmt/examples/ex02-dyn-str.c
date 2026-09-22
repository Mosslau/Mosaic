// 来源：04-memory-mgmt.md 第 6 章示例 2 —— 动态字符串（append 操作）
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99 零警告
// 编译：gcc -Wall -Wextra -std=c99 ex02-dyn-str.c -o ex02-dyn-str
// 运行：./ex02-dyn-str
// 验证状态：已验证
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    char  *data;
    size_t len;   /* 不含 \0 的字符数 */
    size_t cap;   /* 缓冲区总字节数，含 \0 */
} DynStr;

int ds_init(DynStr *ds) {
    ds->data = malloc(16);
    if (ds->data == NULL) return -1;
    ds->data[0] = '\0';
    ds->len = 0;
    ds->cap = 16;
    return 0;
}

void ds_destroy(DynStr *ds) {
    free(ds->data);
    ds->data = NULL;
    ds->len = ds->cap = 0;
}

/* 在末尾追加 C 字符串 */
int ds_append(DynStr *ds, const char *suffix) {
    size_t slen = strlen(suffix);
    size_t need = ds->len + slen + 1;   /* +1 给 \0 */
    if (need > ds->cap) {
        size_t new_cap = ds->cap;
        while (new_cap < need) new_cap *= 2;
        char *tmp = realloc(ds->data, new_cap);
        if (tmp == NULL) return -1;
        ds->data = tmp;
        ds->cap  = new_cap;
    }
    memcpy(ds->data + ds->len, suffix, slen + 1); /* +1 复制 \0 */
    ds->len += slen;
    return 0;
}

int main(void) {
    DynStr ds;
    if (ds_init(&ds) != 0) return 1;

    ds_append(&ds, "Hello");
    ds_append(&ds, ", ");
    ds_append(&ds, "World!");
    printf("\"%s\"  (len=%zu, cap=%zu)\n", ds.data, ds.len, ds.cap);

    ds_destroy(&ds);
    return 0;
}
