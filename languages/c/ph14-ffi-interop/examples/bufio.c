/* bufio.c —— 所有权约定演示库实现
 *
 * 编译（macOS）：
 *   cc -Wall -Wextra -std=c11 -dynamiclib bufio.c -o /tmp/ph14-ex/libbufio.dylib
 */
#include "bufio.h"

#include <stdlib.h>
#include <string.h>

char *bufio_str_dup(const char *s) {
    if (s == NULL)
        return NULL;
    size_t n = strlen(s) + 1;
    char *p = malloc(n);
    if (p != NULL)
        memcpy(p, s, n);
    return p;                 /* 所有权随指针转移给调用方 */
}

void bufio_str_free(char *s) {
    free(s);                  /* 释放必须由 C 侧完成 */
}

size_t bufio_str_copy(char *dst, size_t cap, const char *s) {
    size_t need = strlen(s);  /* 需要的长度（不含 \0） */
    if (dst == NULL || cap == 0)
        return need;
    size_t n = need < cap ? need : cap - 1;
    memcpy(dst, s, n);
    dst[n] = '\0';
    return need;              /* 返回"需要的"长度，可能大于实际拷贝 */
}

int64_t bufio_sum(const int32_t *arr, size_t n) {
    int64_t sum = 0;
    for (size_t i = 0; i < n; i++)
        sum += arr[i];
    return sum;
}

bufio_pt bufio_pt_add(bufio_pt a, bufio_pt b) {
    bufio_pt r = {a.x + b.x, a.y + b.y};
    return r;
}
