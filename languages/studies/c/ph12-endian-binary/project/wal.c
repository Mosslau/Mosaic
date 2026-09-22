/* wal.c —— WAL record 解析器实现
 * 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
 * 编译：见 project/Makefile（cc -Wall -Wextra -std=c11 -O1 -g wal.c main.c）
 * 运行：./wal_tool test / write / read
 * 验证状态：已验证（-Wall -Wextra 零警告; 自测与演示输出见 main.c 尾注释）
 */
#include "wal.h"

#include <stdlib.h>
#include <string.h>

/* ---- 显式大端读写（布局与平台无关） ---- */
static uint16_t be16(const uint8_t *p) {
    return (uint16_t)(((uint16_t)p[0] << 8) | (uint16_t)p[1]);
}
static uint32_t be32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}
static void put_be16(uint8_t *p, uint16_t v) {
    p[0] = (uint8_t)(v >> 8);
    p[1] = (uint8_t)v;
}
static void put_be32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24);
    p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8);
    p[3] = (uint8_t)v;
}

uint32_t wal_crc32(const uint8_t *data, size_t len) {
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int b = 0; b < 8; b++)
            crc = (crc >> 1) ^ ((crc & 1u) ? 0xEDB88320u : 0u);
    }
    return ~crc;
}

int wal_write_header(FILE *fp) {
    uint8_t h[WAL_HEADER_SIZE];
    put_be32(h, WAL_MAGIC);
    put_be16(h + 4, WAL_VERSION);
    h[6] = 0;                 /* reserved: 固定为 0, 供未来扩展 */
    h[7] = 0;
    return fwrite(h, 1, sizeof h, fp) == sizeof h ? WAL_OK : WAL_ERR_IO;
}

int wal_read_header(const uint8_t *buf, size_t avail, size_t *off) {
    if (avail < WAL_HEADER_SIZE) return WAL_ERR_TRUNC;   /* ① 长度先校验 */
    if (be32(buf) != WAL_MAGIC) return WAL_ERR_MAGIC;    /* ② magic */
    if (be16(buf + 4) != WAL_VERSION) return WAL_ERR_VERSION; /* ③ 版本 */
    if (buf[6] != 0 || buf[7] != 0) return WAL_ERR_LEN;  /* ④ reserved */
    *off = WAL_HEADER_SIZE;
    return WAL_OK;
}

int wal_append_record(FILE *fp, uint8_t type,
                      const uint8_t *payload, uint16_t len) {
    if (len > WAL_MAX_PAYLOAD) return WAL_ERR_LEN;
    size_t total = WAL_REC_HEADER + (size_t)len + WAL_REC_CRC;
    uint8_t *b = malloc(total);
    if (b == NULL) return WAL_ERR_IO;
    put_be32(b, WAL_MAGIC);
    b[4] = type;
    put_be16(b + 5, len);
    if (len > 0) memcpy(b + WAL_REC_HEADER, payload, len);
    /* CRC 覆盖 [0, 7+len): magic+type+len+payload（连续区间, crc 放尾部） */
    put_be32(b + WAL_REC_HEADER + len, wal_crc32(b, WAL_REC_HEADER + len));
    int rc = fwrite(b, 1, total, fp) == total ? WAL_OK : WAL_ERR_IO;
    free(b);
    return rc;
}

int wal_parse_record(const uint8_t *buf, size_t avail, size_t *off,
                     uint8_t *type, const uint8_t **payload, uint16_t *len) {
    if (avail - *off == 0) return 0;                      /* 干净地读到尾部 */
    if (avail - *off < WAL_REC_HEADER) return WAL_ERR_TRUNC;  /* ① 长度 */
    if (be32(buf + *off) != WAL_MAGIC) return WAL_ERR_MAGIC;  /* ② magic */
    uint8_t t = buf[*off + 4];
    if (t != WAL_TYPE_PUT && t != WAL_TYPE_DEL) return WAL_ERR_TYPE; /* ③ type */
    uint16_t l = be16(buf + *off + 5);
    if ((size_t)WAL_REC_HEADER + l + WAL_REC_CRC > avail - *off)
        return WAL_ERR_TRUNC;                             /* ④ 总长先校验 */
    if (wal_crc32(buf + *off, WAL_REC_HEADER + l) !=
        be32(buf + *off + WAL_REC_HEADER + l))
        return WAL_ERR_CRC;                               /* ⑤ checksum */
    *type = t;
    *payload = buf + *off + WAL_REC_HEADER;
    *len = l;
    *off += WAL_REC_HEADER + (size_t)l + WAL_REC_CRC;
    return 1;
}
