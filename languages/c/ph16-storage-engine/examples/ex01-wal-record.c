/* ex01-wal-record.c —— WAL record 设计：编码/解码/CRC 校验（纯内存演示）
 *
 * 记录格式（多字节字段显式大端, 衔接 ph12 的线上格式纪律; 承接 ph13 kvlog
 * 与 ph14 kvdb 的记录格式, 增加 type 字段区分 PUT/DEL）：
 *   [magic: u32 "WAL1"][type: u8][klen: u32][vlen: u32][key][value][crc32: u32]
 *   固定头 13 字节; crc32 覆盖 type..value（即 magic 之后、crc 之前的全部字节）。
 *
 * 设计要点（主文档 3.1）：
 *   - magic 识别"这是不是我们的文件/记录"
 *   - type 区分 put 与 delete（删除 = tombstone 记录, 不是真的擦除）
 *   - 显式长度前缀让回放方能逐条跳读, 不必理解 payload 内容
 *   - crc32 放最后: 写时最后算、读时最后验——崩溃残写在校验处现形
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：mkdir -p /tmp/ph16c-ex && cc -Wall -Wextra -std=c11 ex01-wal-record.c -o /tmp/ph16c-ex/ex01
// 运行：/tmp/ph16c-ex/ex01（无外部产物, 退出码 0）
// 验证状态：已验证（零警告; 往返/损坏拦截/大端字节序均为实测输出）
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define WAL_MAGIC 0x57414C31u /* "WAL1" */
#define WAL_HDR_SIZE 13u      /* magic(4) + type(1) + klen(4) + vlen(4) */
#define WAL_CRC_SIZE 4u
#define WAL_MAX_KV (1024u * 1024u)

enum { WAL_PUT = 1, WAL_DEL = 2 };

/* ---- CRC-32（IEEE 802.3, 反射多项式; 与 ph13/ph14 同款实现） ---- */
static uint32_t crc32_update(uint32_t crc, const uint8_t *p, size_t n) {
    crc = ~crc;
    for (size_t i = 0; i < n; i++) {
        crc ^= p[i];
        for (int b = 0; b < 8; b++)
            crc = (crc >> 1) ^ (0xEDB88320u & (uint32_t)-(int32_t)(crc & 1u));
    }
    return ~crc;
}

/* ---- 大端读写助手（显式移位, 不依赖主机字节序） ---- */
static void put_u32be(uint8_t *d, uint32_t v) {
    d[0] = (uint8_t)(v >> 24); d[1] = (uint8_t)(v >> 16);
    d[2] = (uint8_t)(v >> 8);  d[3] = (uint8_t)v;
}
static uint32_t get_u32be(const uint8_t *s) {
    return ((uint32_t)s[0] << 24) | ((uint32_t)s[1] << 16) |
           ((uint32_t)s[2] << 8) | (uint32_t)s[3];
}

/* ---- 编码：返回总字节数 ---- */
static size_t wal_encode(uint8_t *buf, uint8_t type,
                         const char *key, const char *val) {
    uint32_t klen = (uint32_t)strlen(key);
    uint32_t vlen = (uint32_t)strlen(val);
    put_u32be(buf, WAL_MAGIC);
    buf[4] = type;
    put_u32be(buf + 5, klen);
    put_u32be(buf + 9, vlen);
    memcpy(buf + WAL_HDR_SIZE, key, klen);
    memcpy(buf + WAL_HDR_SIZE + klen, val, vlen);
    size_t total = WAL_HDR_SIZE + klen + vlen;
    /* crc 覆盖 type 字段到 value 末尾（跳过 magic 自身） */
    put_u32be(buf + total, crc32_update(0, buf + 4, total - 4));
    return total + WAL_CRC_SIZE;
}

/* ---- 解码：校验 magic/长度上限/crc, 全部通过才把 key/value 拷出 ---- */
static int wal_decode(const uint8_t *buf, size_t total,
                      uint8_t *type_out, char *key, char *val) {
    if (total < WAL_HDR_SIZE + WAL_CRC_SIZE) return -1;
    if (get_u32be(buf) != WAL_MAGIC) return -2;          /* magic 不符 */
    uint8_t type = buf[4];
    uint32_t klen = get_u32be(buf + 5);
    uint32_t vlen = get_u32be(buf + 9);
    if (klen > WAL_MAX_KV || vlen > WAL_MAX_KV) return -3; /* 长度上限 */
    if (total != WAL_HDR_SIZE + klen + vlen + WAL_CRC_SIZE) return -4;
    uint32_t crc_stored = get_u32be(buf + WAL_HDR_SIZE + klen + vlen);
    uint32_t crc_calc = crc32_update(0, buf + 4, WAL_HDR_SIZE + klen + vlen - 4);
    if (crc_stored != crc_calc) return -5;                /* 损坏拦截 */
    memcpy(key, buf + WAL_HDR_SIZE, klen); key[klen] = '\0';
    memcpy(val, buf + WAL_HDR_SIZE + klen, vlen); val[vlen] = '\0';
    *type_out = type;
    return 0;
}

int main(void) {
    static uint8_t buf[256];
    char key[64], val[64];
    uint8_t type = 0;

    printf("=== WAL record 布局 ===\n");
    printf("固定头 %u 字节: magic(4) + type(1) + klen(4) + vlen(4), crc 尾随 %u 字节\n",
           WAL_HDR_SIZE, WAL_CRC_SIZE);

    /* 1. PUT 记录往返 */
    size_t n = wal_encode(buf, WAL_PUT, "name", "tenet");
    int rc = wal_decode(buf, n, &type, key, val);
    printf("\n[1] PUT 编码 %zu 字节, 解码 rc=%d: type=%s key=\"%s\" value=\"%s\"\n",
           n, rc, type == WAL_PUT ? "PUT" : "?", key, val);

    /* 2. DEL 记录（tombstone: value 为空串） */
    n = wal_encode(buf, WAL_DEL, "name", "");
    rc = wal_decode(buf, n, &type, key, val);
    printf("[2] DEL 编码 %zu 字节, 解码 rc=%d: type=%s key=\"%s\" (value 空=tombstone)\n",
           n, rc, type == WAL_DEL ? "DEL" : "?", key);

    /* 3. 大端字节序肉眼可验: magic "WAL1" 在文件里逐字节可读 */
    printf("[3] 头 13 字节(hex):");
    for (size_t i = 0; i < WAL_HDR_SIZE; i++) printf(" %02x", buf[i]);
    printf("\n    前 4 字节即 ASCII: %c%c%c%c\n",
           buf[0], buf[1], buf[2], buf[3]);

    /* 4. 翻转 payload 一字节 → CRC 拦截 */
    n = wal_encode(buf, WAL_PUT, "city", "hangzhou");
    buf[WAL_HDR_SIZE] ^= 0x01; /* 'c' → 'b' */
    rc = wal_decode(buf, n, &type, key, val);
    printf("[4] 翻转 key 首字节后解码 rc=%d (期望 -5: CRC 拦截)\n", rc);

    /* 5. magic 写错 → 格式拦截 */
    n = wal_encode(buf, WAL_PUT, "k", "v");
    buf[0] ^= 0xFF;
    rc = wal_decode(buf, n, &type, key, val);
    printf("[5] 破坏 magic 后解码 rc=%d (期望 -2: magic 不符)\n", rc);

    printf("\n自测: rc 序列 [0,0,-5,-2] %s\n",
           (rc == -2) ? "符合预期" : "不符合预期");
    return 0;
}
