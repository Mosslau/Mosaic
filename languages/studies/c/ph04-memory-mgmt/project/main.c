// 来源：project/ —— darray 动态数组库自测（assert 全过则无输出）
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99
// 编译：gcc -Wall -Wextra -std=c99 darray.c main.c -o darray
// 运行：./darray
// 验证状态：已验证
#include <assert.h>
#include <stdio.h>

#include "darray.h"

int main(void) {
    DArray *da = darray_create();
    assert(da != NULL);
    assert(darray_size(da) == 0);
    assert(darray_capacity(da) == 4);

    /* 1. 扩容路径：插入 20 个元素触发 2x 扩容 4→8→16→32 */
    for (int i = 0; i < 20; i++)
        assert(darray_push(da, i * 10) == 0);
    assert(darray_size(da) == 20);
    assert(darray_capacity(da) == 32);

    /* 2. 读路径 */
    assert(darray_get(da, 0) == 0);
    assert(darray_get(da, 19) == 190);

    /* 3. 越界保护：set 越界返回 -1 并置标记；get 越界返回 0（只读不置标记） */
    assert(darray_set(da, 20, 999) == -1);
    assert(darray_get(da, 99) == 0);
    assert(da->last_err != 0);   /* set 越界被记录 */

    /* 4. 弹出 + 缩容路径：弹到 4 个，容量 32→16 */
    while (darray_size(da) > 4)
        darray_pop(da);
    assert(darray_size(da) == 4);
    assert(darray_capacity(da) == 16);
    assert(darray_get(da, 3) == 30);

    /* 5. 空数组 pop 保护 */
    while (darray_size(da) > 0)
        darray_pop(da);
    assert(darray_pop(da) == 0);
    assert(da->last_err != 0);

    /* 6. 写入后回读 */
    assert(darray_push(da, 42) == 0);
    assert(darray_set(da, 0, 7) == 0);
    assert(darray_get(da, 0) == 7);

    darray_destroy(da);
    printf("全部 assert 通过\n");
    return 0;
}
