/* ex06-c-ownership.c —— 三种跨语言所有权约定的 C 侧对照
 *
 * 编译（macOS）：
 *   cc -Wall -Wextra -std=c11 -dynamiclib bufio.c -o /tmp/ph14-ex/libbufio.dylib
 *   cc -Wall -Wextra -std=c11 ex06-c-ownership.c -L/tmp/ph14-ex -lbufio \
 *       -o /tmp/ph14-ex/ex06-c
 * 运行：/tmp/ph14-ex/ex06-c
 */
#include <stdint.h>
#include <stdio.h>

#include "bufio.h"

int main(void) {
    /* 约定 1：C 分配、C 释放 */
    char *dup = bufio_str_dup("malloc'd by C");
    printf("约定1: dup=%s\n", dup);
    bufio_str_free(dup);               /* 必须用 C 侧释放函数 */
    dup = NULL;

    /* 约定 2：调用方分配 buffer，C 只写 */
    char buf[32];
    size_t need = bufio_str_copy(buf, sizeof buf, "caller buffer");
    printf("约定2: buf=%s need=%zu\n", buf, need);

    /* 约定 3：C 只读借用调用方数组 */
    int32_t arr[] = {1, 2, 3, 4, 5};
    int64_t sum = bufio_sum(arr, sizeof arr / sizeof arr[0]);
    printf("约定3: sum=%lld\n", (long long)sum);

    /* POD 结构体按值传递（跨语言布局需一致） */
    bufio_pt a = {10, 20};
    bufio_pt b = {30, 40};
    bufio_pt r = bufio_pt_add(a, b);
    printf("struct: (%d,%d)+(%d,%d)=(%d,%d)\n",
           (int)a.x, (int)a.y, (int)b.x, (int)b.y, (int)r.x, (int)r.y);
    return 0;
}
