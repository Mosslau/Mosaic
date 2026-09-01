/* cli.c —— kvdb 命令行自测（make test 的第一环）
 *
 * 编译（macOS）：
 *   cc -Wall -Wextra -std=c11 kvdb.c cli.c -o /tmp/ph14-proj/kvdb-cli
 * 运行：/tmp/ph14-proj/kvdb-cli [wal 路径，默认 /tmp/ph14-proj/cli-test.db]
 *
 * 覆盖：put/get 文本与二进制往返、覆盖、NOTFOUND 错误码与消息、
 * BADARG 空参数、sync 后重新打开（WAL 回放）持久化验证。
 */
#include <stdio.h>
#include <string.h>

#include "kvdb.h"

#define WAL_DEFAULT "/tmp/ph14-proj/cli-test.db"

static int failures = 0;
static int checks = 0;

#define CHECK(cond, msg)                                           \
    do {                                                           \
        checks++;                                                  \
        if (cond)                                                  \
            printf("PASS: %s\n", msg);                             \
        else {                                                     \
            printf("FAIL: %s\n", msg);                             \
            failures++;                                            \
        }                                                          \
    } while (0)

int main(int argc, char **argv) {
    const char *wal = argc > 1 ? argv[1] : WAL_DEFAULT;
    remove(wal);                                   /* 从干净状态开始 */
    int32_t err = KVDB_OK;

    /* 1. create（新建 WAL + 空回放） */
    kvdb_t *db = kvdb_create(wal, &err);
    CHECK(db != NULL && err == KVDB_OK, "kvdb_create: 非 NULL, err=0");

    /* 2. put/get 文本值 */
    CHECK(kvdb_put(db, "greeting", (const uint8_t *)"hello world", 11) ==
              KVDB_OK,
          "put(greeting) 成功");
    char buf[64];
    uint32_t vlen = 0;
    CHECK(kvdb_get(db, "greeting", (uint8_t *)buf, sizeof buf, &vlen) ==
              KVDB_OK,
          "get(greeting) 成功");
    CHECK(vlen == 11 && memcmp(buf, "hello world", 11) == 0,
          "get(greeting) 内容与长度正确");

    /* 3. 覆盖 */
    CHECK(kvdb_put(db, "greeting", (const uint8_t *)"hi", 2) == KVDB_OK,
          "put(greeting) 覆盖成功");
    vlen = 0;
    CHECK(kvdb_get(db, "greeting", (uint8_t *)buf, sizeof buf, &vlen) ==
              KVDB_OK,
          "get(greeting) 覆盖后读取成功");
    CHECK(vlen == 2 && memcmp(buf, "hi", 2) == 0,
          "覆盖后内容 == \"hi\"");

    /* 4. 二进制值（含 \0 字节）往返 */
    const uint8_t blob[4] = {0x01, 0x00, 0xFF, 0x02};
    CHECK(kvdb_put(db, "blob", blob, sizeof blob) == KVDB_OK,
          "put(blob) 二进制值成功");
    uint8_t got[4];
    vlen = 0;
    CHECK(kvdb_get(db, "blob", got, sizeof got, &vlen) == KVDB_OK,
          "get(blob) 成功");
    CHECK(vlen == 4 && memcmp(got, blob, 4) == 0,
          "二进制值往返一致（含 \\0 字节）");

    /* 5. NOTFOUND 错误码与消息 */
    int32_t rc = kvdb_get(db, "missing", (uint8_t *)buf, sizeof buf, &vlen);
    CHECK(rc == KVDB_ERR_NOTFOUND, "get(missing): err=-5(NOTFOUND)");
    CHECK(strcmp(kvdb_strerror(rc), "key not found") == 0,
          "err=-5 的消息 == \"key not found\"");

    /* 6. BADARG 空参数 */
    rc = kvdb_put(db, NULL, (const uint8_t *)"x", 1);
    CHECK(rc == KVDB_ERR_BADARG, "put(NULL key): err=-1(BADARG)");
    rc = kvdb_put(db, "", (const uint8_t *)"x", 1);
    CHECK(rc == KVDB_ERR_BADARG, "put(空 key): err=-1(BADARG)");

    /* 7. sync + destroy + 重开（WAL 回放持久化验证） */
    CHECK(kvdb_sync(db) == KVDB_OK, "kvdb_sync 成功");
    CHECK(kvdb_destroy(db) == KVDB_OK, "kvdb_destroy 成功");

    db = kvdb_create(wal, &err);
    CHECK(db != NULL && err == KVDB_OK, "重新打开: 非 NULL, err=0");
    vlen = 0;
    CHECK(kvdb_get(db, "greeting", (uint8_t *)buf, sizeof buf, &vlen) ==
              KVDB_OK,
          "重开后 get(greeting) 命中");
    CHECK(vlen == 2 && memcmp(buf, "hi", 2) == 0,
          "重开后内容仍 == \"hi\"（WAL 回放恢复）");
    vlen = 0;
    CHECK(kvdb_get(db, "blob", got, sizeof got, &vlen) == KVDB_OK,
          "重开后 get(blob) 命中");
    CHECK(vlen == 4 && memcmp(got, blob, 4) == 0,
          "重开后二进制值仍一致");
    CHECK(kvdb_destroy(db) == KVDB_OK, "再次 destroy 成功");

    remove(wal);
    if (failures == 0)
        printf("cli: 全部断言通过（%d 项）, 退出码 0\n", checks);
    else
        printf("cli: %d 项失败\n", failures);
    return failures == 0 ? 0 : 1;
}
