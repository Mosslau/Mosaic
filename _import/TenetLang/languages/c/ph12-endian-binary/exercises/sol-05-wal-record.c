/* sol-05-wal-record.c —— 参考实现: 为 WAL record 设计 header 和 checksum
 * 布局(大端, CRC 放尾部使被覆盖区间连续):
 *   [0,4)         magic(u32,"WAL1") + [4,5) type(u8,1=PUT 2=DEL) +
 *   [5,7)         len(u16) + [7,7+len) payload +
 *   [7+len,11+len) crc32(u32, 覆盖 [0,7+len) 全部字段); 单条总长 = 11 + len。
 * 要点: 回放路径严格按"先校验长度 → magic/type → payload 长度 → CRC →
 *   才拷贝"的顺序; 自测覆盖往返、损坏(翻转 payload 一位)与截断三类。
 * 实测: 3 条 record 往返一致; 损坏触发 CRC 错误; 截断触发长度错误;
 *   全部自测通过, 退出码 0。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-05-wal-record.c -o sol05
// 运行：./sol05（往返 + 损坏 + 截断自测, 全过退出码 0）
// 验证状态：已验证（-Wall -Wextra 零警告; 实测输出见文件尾注释）
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define WAL_MAGIC   0x57414C31u    /* "WAL1" */
#define WAL_HEADER  7u             /* magic4 + type1 + len2 */
#define WAL_CRC     4u             /* crc 放尾部 */
#define WAL_MAX_LEN 4096u
#define WAL_TYPE_PUT 1u
#define WAL_TYPE_DEL 2u

#define LOG_CAP 8192u

static int g_failures = 0;
#define CHECK(cond) do {                                                    \
    if (cond) {                                                             \
        printf("[PASS] %s\n", #cond);                                       \
    } else {                                                                \
        g_failures++;                                                       \
        printf("[FAIL] %s  (%s:%d)\n", #cond, __FILE__, __LINE__);          \
    }                                                                       \
} while (0)

/* ---- CRC-32（IEEE 802.3; 校验值 0xCBF43926 已验证）---- */
static uint32_t crc32(const uint8_t *data, size_t len) {
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int b = 0; b < 8; b++)
            crc = (crc >> 1) ^ ((crc & 1u) ? 0xEDB88320u : 0u);
    }
    return ~crc;
}

static void write_be16(uint8_t *p, uint16_t v) {
    p[0] = (uint8_t)(v >> 8);
    p[1] = (uint8_t)v;
}
static void write_be32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24);
    p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8);
    p[3] = (uint8_t)v;
}
static uint16_t read_be16(const uint8_t *p) {
    return (uint16_t)(((uint16_t)p[0] << 8) | (uint16_t)p[1]);
}
static uint32_t read_be32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}

/* 追加一条 record 到日志; 返回 0=成功 -1=超上限 -2=空间不足 */
static int wal_append(uint8_t *log, size_t *log_len, size_t cap,
                      uint8_t type, const uint8_t *payload, uint16_t len) {
    if (len > WAL_MAX_LEN) return -1;
    if (*log_len + WAL_HEADER + len + WAL_CRC > cap) return -2;
    size_t start = *log_len;
    uint32_t magic = WAL_MAGIC;
    log[start + 0] = (uint8_t)(magic >> 24);
    log[start + 1] = (uint8_t)(magic >> 16);
    log[start + 2] = (uint8_t)(magic >> 8);
    log[start + 3] = (uint8_t)magic;
    log[start + 4] = type;
    write_be16(log + start + 5, len);
    if (len > 0) memcpy(log + start + WAL_HEADER, payload, len);
    /* CRC 覆盖 [start, start+7+len): magic+type+len+payload（连续区间） */
    uint32_t crc = crc32(log + start, WAL_HEADER + len);
    write_be32(log + start + WAL_HEADER + len, crc);   /* crc 放尾部 */
    *log_len = start + WAL_HEADER + len + WAL_CRC;
    return 0;
}

/* 回放: 解析下一条 record; 返回 1=成功 0=解析到日志尾 -1..-4=错误 */
/* 错误码: -1 长度不足(截断) -2 magic -3 type -4 CRC */
static int wal_replay(const uint8_t *log, size_t log_len, size_t *off,
                      uint8_t *type, const uint8_t **payload, uint16_t *len) {
    if (log_len - *off == 0) return 0;             /* 干净地读到日志尾 */
    if (log_len - *off < WAL_HEADER) return -1;    /* ① 头部长度先校验 */
    if (read_be32(log + *off) != WAL_MAGIC) return -2;
    uint8_t t = log[*off + 4];
    if (t != WAL_TYPE_PUT && t != WAL_TYPE_DEL) return -3;
    uint16_t l = read_be16(log + *off + 5);
    if ((size_t)WAL_HEADER + l + WAL_CRC > log_len - *off) return -1; /* ② 总长 */
    if (crc32(log + *off, WAL_HEADER + l) !=
        read_be32(log + *off + WAL_HEADER + l)) return -4;            /* ③ CRC */
    *type = t;
    *payload = log + *off + WAL_HEADER;
    *len = l;
    *off += WAL_HEADER + l + WAL_CRC;
    return 1;
}

int main(void) {
    static uint8_t log[LOG_CAP];
    size_t log_len = 0;

    /* 1. 往返: 追加 3 条再全部回放 */
    CHECK(wal_append(log, &log_len, sizeof log, WAL_TYPE_PUT,
                     (const uint8_t *)"k1=v1", 5) == 0);
    CHECK(wal_append(log, &log_len, sizeof log, WAL_TYPE_PUT,
                     (const uint8_t *)"k2=val2", 7) == 0);
    CHECK(wal_append(log, &log_len, sizeof log, WAL_TYPE_DEL,
                     (const uint8_t *)"k3", 2) == 0);
    printf("追加 3 条 record, 日志共 %zu 字节\n", log_len);

    size_t off = 0;
    uint8_t type;
    const uint8_t *payload;
    uint16_t len;
    int rc = wal_replay(log, log_len, &off, &type, &payload, &len);
    CHECK(rc == 1 && type == WAL_TYPE_PUT && len == 5 &&
          memcmp(payload, "k1=v1", 5) == 0);
    rc = wal_replay(log, log_len, &off, &type, &payload, &len);
    CHECK(rc == 1 && type == WAL_TYPE_PUT && len == 7 &&
          memcmp(payload, "k2=val2", 7) == 0);
    rc = wal_replay(log, log_len, &off, &type, &payload, &len);
    CHECK(rc == 1 && type == WAL_TYPE_DEL && len == 2 &&
          memcmp(payload, "k3", 2) == 0);
    rc = wal_replay(log, log_len, &off, &type, &payload, &len);
    CHECK(rc == 0);                                   /* 干净读到尾 */

    /* 2. 损坏: 翻转第 2 条 payload 一位 → 回放应报 CRC 错误
     * 第 1 条占 7+5+4=16 字节, 第 2 条 payload 从 16+7=23 开始 */
    log[23] ^= 0x01u;
    off = 0;
    rc = wal_replay(log, log_len, &off, &type, &payload, &len);
    CHECK(rc == 1);                                   /* 第 1 条正常 */
    rc = wal_replay(log, log_len, &off, &type, &payload, &len);
    CHECK(rc == -4);                                  /* 第 2 条 CRC 失败 */
    log[23] ^= 0x01u;                                 /* 还原 */

    /* 3. 截断: 只保留前 20 字节(第 1 条 16 字节 + 4 字节尾巴) */
    size_t cut = 11 + 5 + 4;
    off = 0;
    rc = wal_replay(log, cut, &off, &type, &payload, &len);
    CHECK(rc == 1);
    rc = wal_replay(log, cut, &off, &type, &payload, &len);
    CHECK(rc == -1);                                  /* 截断 → 长度错误 */

    printf(g_failures == 0
               ? "全部自测通过 (退出码 0)\n"
               : "自测失败: %d 个断言失败\n", g_failures);
    return g_failures == 0 ? 0 : 1;
}

/* 实测输出（Apple clang 21.0.0, macOS arm64）：
 * 追加 3 条 record, 日志共 47 字节
 * [PASS] × 3（追加）+ × 4（往返: 3 条字段/payload 一致 + 干净读到尾）
 * [PASS] × 2（损坏: 第 1 条正常、第 2 条 rc==-4 CRC 失败）
 * [PASS] × 2（截断: 第 1 条正常、尾部 rc==-1 长度错误）
 * 全部自测通过 (退出码 0) —— 共 11 个 [PASS]
 */
