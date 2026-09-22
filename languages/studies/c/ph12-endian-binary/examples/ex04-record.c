/* ex04-record.c —— 安全解析二进制 record：magic + 版本 + 字段 + CRC（重点示例，已验证）
 * 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
 * 编译：cc -Wall -Wextra -std=c11 ex04-record.c -o ex04
 * 运行：./ex04
 * 验证状态：已验证（-Wall -Wextra 零警告，退出码 0，输出见文件尾注释）
 *
 * 对应 roadmap 必会概念「不要直接把不可信字节强转成结构体指针」：
 * 本示例演示安全做法——先校验长度与字段合法性，再逐字段显式读取
 * （read_be16/read_be32 + CRC 校验）。把字节流强转成 struct 指针会有
 * 三重风险：① 字节序随平台漂移 ② padding/布局由编译器决定 ③ 缓冲区的
 * 起始地址未必对齐到结构体对齐值（未对齐访问是 UB，ph10 已讲）。
 *
 * 磁盘布局（多字节字段一律大端, CRC 放尾部使被覆盖区间连续）:
 *   [0,4)         magic    uint32 BE = 0x52454331 ("REC1")
 *   [4,6)         version  uint16 BE = 1
 *   [6,8)         type     uint16 BE (1=PUT, 2=DEL)
 *   [8,12)        key_len  uint32 BE
 *   [12,16)       value_len uint32 BE
 *   [16,16+k)     key
 *   [16+k,16+k+v) value
 *   [16+k+v,20+k+v) crc32  uint32 BE —— 覆盖 [0,16+k+v) 全部字段
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define REC_MAGIC        0x52454331u   /* "REC1" */
#define REC_VERSION      1u
#define REC_HEADER_SIZE  16u           /* magic4 + ver2 + type2 + keylen4 + vallen4 */
#define REC_CRC_SIZE     4u
#define REC_TYPE_PUT     1u
#define REC_TYPE_DEL     2u

typedef struct {
    uint16_t type;
    const uint8_t *key;
    uint32_t key_len;
    const uint8_t *value;
    uint32_t value_len;
} Record;

/* 解析结果码 */
enum {
    PARSE_OK = 0,
    PARSE_TRUNC = -1,    /* 剩余字节不足（截断） */
    PARSE_MAGIC = -2,    /* magic 不匹配 */
    PARSE_VERSION = -3,  /* 版本不支持 */
    PARSE_TYPE = -4,     /* 类型非法 */
    PARSE_CRC = -5       /* checksum 不匹配（损坏） */
};

/* ---- CRC-32（IEEE 802.3, 反射多项式 0xEDB88320；校验值 0xCBF43926 已验证）---- */
static uint32_t crc32(const uint8_t *data, size_t len) {
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int b = 0; b < 8; b++)
            crc = (crc >> 1) ^ ((crc & 1u) ? 0xEDB88320u : 0u);
    }
    return ~crc;
}

/* ---- 显式大端读写（布局与平台无关）---- */
static uint16_t read_be16(const uint8_t *p) {
    return (uint16_t)(((uint16_t)p[0] << 8) | (uint16_t)p[1]);
}
static uint32_t read_be32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | (uint32_t)p[3];
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

/* ---- 安全解析（核心示范）：先检查长度与合法性，再逐字段读取 ---- */
static int record_parse(const uint8_t *buf, size_t avail, size_t off,
                        Record *out, size_t *consumed) {
    if (avail - off < REC_HEADER_SIZE)
        return PARSE_TRUNC;                       /* ① 头部长度先校验 */
    if (read_be32(buf + off) != REC_MAGIC)
        return PARSE_MAGIC;                       /* ② magic */
    if (read_be16(buf + off + 4) != REC_VERSION)
        return PARSE_VERSION;                     /* ③ 版本 */
    uint16_t type = read_be16(buf + off + 6);
    if (type != REC_TYPE_PUT && type != REC_TYPE_DEL)
        return PARSE_TYPE;                        /* ④ 类型 */
    uint32_t key_len = read_be32(buf + off + 8);
    uint32_t value_len = read_be32(buf + off + 12);
    /* ⑤ payload + CRC 的总长度先校验（uint64 防溢出） */
    if ((uint64_t)REC_HEADER_SIZE + key_len + value_len + REC_CRC_SIZE >
        avail - off)
        return PARSE_TRUNC;
    /* ⑥ checksum 覆盖 [0, 16+k+v) —— 头部字段 + key + value */
    size_t covered = REC_HEADER_SIZE + (size_t)key_len + value_len;
    if (crc32(buf + off, covered) != read_be32(buf + off + covered))
        return PARSE_CRC;
    out->type = type;
    out->key = buf + off + REC_HEADER_SIZE;
    out->key_len = key_len;
    out->value = buf + off + REC_HEADER_SIZE + key_len;
    out->value_len = value_len;
    *consumed = covered + REC_CRC_SIZE;
    return PARSE_OK;
}

/* ---- 构造一条 record（写路径同样按显式字节序落线）---- */
static uint8_t *record_build(uint16_t type, const uint8_t *key, uint32_t key_len,
                             const uint8_t *value, uint32_t value_len,
                             size_t *out_size) {
    size_t total = REC_HEADER_SIZE + (size_t)key_len + value_len + REC_CRC_SIZE;
    uint8_t *b = malloc(total);
    if (b == NULL) return NULL;
    write_be32(b, REC_MAGIC);
    write_be16(b + 4, REC_VERSION);
    write_be16(b + 6, type);
    write_be32(b + 8, key_len);
    write_be32(b + 12, value_len);
    if (key_len > 0) memcpy(b + REC_HEADER_SIZE, key, key_len);
    if (value_len > 0)
        memcpy(b + REC_HEADER_SIZE + key_len, value, value_len);
    size_t covered = REC_HEADER_SIZE + (size_t)key_len + value_len;
    write_be32(b + covered, crc32(b, covered));   /* CRC 放尾部 */
    *out_size = total;
    return b;
}

static void print_record(const Record *r) {
    printf("type=%s key=\"%.*s\" value=\"%.*s\" (key_len=%u value_len=%u)\n",
           r->type == REC_TYPE_PUT ? "PUT" : "DEL",
           (int)r->key_len, (const char *)r->key,
           (int)r->value_len, (const char *)r->value,
           r->key_len, r->value_len);
}

int main(void) {
    /* 1. 构造两条 record 并拼进同一缓冲区（模拟从文件/网络读到的字节流） */
    size_t s1, s2;
    uint8_t *r1 = record_build(REC_TYPE_PUT, (const uint8_t *)"name", 4,
                               (const uint8_t *)"mosslau", 7, &s1);
    uint8_t *r2 = record_build(REC_TYPE_DEL, (const uint8_t *)"old", 3,
                               NULL, 0, &s2);
    if (r1 == NULL || r2 == NULL) return 1;
    size_t total = s1 + s2;
    uint8_t *buf = malloc(total);
    if (buf == NULL) return 1;
    memcpy(buf, r1, s1);
    memcpy(buf + s1, r2, s2);

    /* 2. 安全解析全部 record */
    size_t off = 0;
    int count = 0;
    while (off < total) {
        Record rec;
        size_t consumed = 0;
        int rc = record_parse(buf, total, off, &rec, &consumed);
        if (rc != PARSE_OK) {
            printf("解析失败: 错误码 %d (应到不了这里)\n", rc);
            break;
        }
        printf("record %d: ", ++count);
        print_record(&rec);
        off += consumed;
    }
    printf("解析结果: %d 条 record 全部通过 (CRC 校验通过)\n", count);

    /* 3. 损坏 payload 一字节 → CRC 检测到损坏 */
    uint8_t *bad = malloc(total);
    if (bad == NULL) return 1;
    memcpy(bad, buf, total);
    bad[REC_HEADER_SIZE] ^= 0x01u;              /* key 首字节翻转一位 */
    Record rec;
    size_t consumed = 0;
    int rc = record_parse(bad, total, 0, &rec, &consumed);
    printf("== 损坏 payload 一字节 ==\n");
    printf("解析结果: %s\n", rc == PARSE_CRC
           ? "PARSE_CRC —— checksum 不匹配, 检测到数据损坏"
           : "（意外: 未检测到损坏）");

    /* 4. 截断 → 长度校验兜底 */
    rc = record_parse(buf, s1 - 3, 0, &rec, &consumed);  /* 第 1 条 payload 被截断 */
    printf("== 截断 record（payload 只到一半）==\n");
    printf("解析结果: %s\n", rc == PARSE_TRUNC
           ? "PARSE_TRUNC —— 剩余字节不足, 检测到截断"
           : "（意外: 未检测到截断）");

    free(r1);
    free(r2);
    free(buf);
    free(bad);
    return 0;
}

/* 实测输出（Apple clang 21.0.0, macOS arm64）：
 * record 1: type=PUT key="name" value="mosslau" (key_len=4 value_len=7)
 * record 2: type=DEL key="old" value="" (key_len=3 value_len=0)
 * 解析结果: 2 条 record 全部通过 (CRC 校验通过)
 * == 损坏 payload 一字节 ==
 * 解析结果: PARSE_CRC —— checksum 不匹配, 检测到数据损坏
 * == 截断 record（payload 只到一半）==
 * 解析结果: PARSE_TRUNC —— 剩余字节不足, 检测到截断
 */
