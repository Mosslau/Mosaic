// 来源：project/ —— kvstore 内存表自测（assert 全过则输出一行）
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c99
// 编译：gcc -Wall -Wextra -std=c99 kv.c main.c -o kvstore
// 运行：./kvstore
// 验证状态：已验证
#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "kv.h"

static int key_count = 0;
static void count_key(const char *key) { (void)key; key_count++; }

int main(void) {
    KVStore *kv = kv_create();
    assert(kv != NULL);
    assert(kv_size(kv) == 0);

    /* 1. 新建写入 */
    assert(kv_put(kv, "name", "Tenet") == 0);
    assert(kv_put(kv, "lang", "C") == 0);
    assert(kv_put(kv, "phase", "05") == 0);
    assert(kv_size(kv) == 3);

    /* 2. 读取 + 值拷贝 */
    char buf[64];
    assert(kv_get(kv, "name", buf, sizeof buf) == 1);
    assert(strcmp(buf, "Tenet") == 0);

    /* 3. 覆盖写入（返回 1 且 size 不变） */
    assert(kv_put(kv, "name", "TenetLang") == 1);
    assert(kv_size(kv) == 3);
    assert(kv_get(kv, "name", buf, sizeof buf) == 1);
    assert(strcmp(buf, "TenetLang") == 0);

    /* 4. 不存在键 */
    assert(kv_get(kv, "missing", buf, sizeof buf) == 0);
    assert(kv_contains(kv, "missing") == 0);
    assert(kv_contains(kv, "lang") == 1);

    /* 5. 删除 */
    assert(kv_delete(kv, "phase") == 1);
    assert(kv_delete(kv, "phase") == 0);     /* 二次删除返回 0 */
    assert(kv_size(kv) == 2);
    assert(kv_get(kv, "phase", buf, sizeof buf) == 0);

    /* 6. 遍历 */
    key_count = 0;
    assert(kv_keys(kv, count_key) == 2);
    assert(key_count == 2);

    /* 7. 大量写入验证哈希分布 */
    for (int i = 0; i < 500; i++) {
        char k[16], v[16];
        snprintf(k, sizeof k, "key%d", i);
        snprintf(v, sizeof v, "val%d", i);
        assert(kv_put(kv, k, v) == 0);
    }
    assert(kv_size(kv) == 502);
    assert(kv_get(kv, "key499", buf, sizeof buf) == 1);
    assert(strcmp(buf, "val499") == 0);

    kv_destroy(kv);
    printf("全部 assert 通过\n");
    return 0;
}
