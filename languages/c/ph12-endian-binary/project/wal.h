/* wal.h —— WAL record 解析器: 格式定义与 API
 * 文件布局（多字节字段一律大端）:
 *   文件头(8 字节): magic(u32,"WAL1") + version(u16) + reserved(u16, 必须为 0)
 *   每条 record(11+len 字节): magic(u32) + type(u8) + len(u16) +
 *     payload[len] + crc32(u32, 覆盖 magic+type+len+payload)
 * 设计原则（roadmap 必会概念）:
 *   - 多字节字段显式大端读写, 不依赖 struct 布局
 *   - 先校验长度再读字段, 绝不把不可信字节强转成结构体指针
 *   - magic + 版本 + CRC 构成格式契约: 识别非本格式文件、旧版本、损坏与截断
 */
#ifndef WAL_H
#define WAL_H

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#define WAL_MAGIC        0x57414C31u   /* "WAL1" */
#define WAL_VERSION      1u
#define WAL_HEADER_SIZE  8u            /* magic4 + version2 + reserved2 */
#define WAL_REC_HEADER   7u            /* magic4 + type1 + len2 */
#define WAL_REC_CRC      4u
#define WAL_MAX_PAYLOAD  65535u        /* len 是 u16, 上限即其最大值 */
#define WAL_TYPE_PUT     1u
#define WAL_TYPE_DEL     2u

/* 解析结果码 */
enum {
    WAL_OK = 0,
    WAL_ERR_IO = -1,      /* 文件读写失败 */
    WAL_ERR_MAGIC = -2,   /* magic 不匹配（不是本格式文件） */
    WAL_ERR_VERSION = -3, /* 版本不支持 */
    WAL_ERR_TYPE = -4,    /* record 类型非法 */
    WAL_ERR_TRUNC = -5,   /* 剩余字节不足（截断/半写入） */
    WAL_ERR_CRC = -6,     /* checksum 不匹配（数据损坏） */
    WAL_ERR_LEN = -7      /* 保留字段/长度非法 */
};

/* CRC-32（IEEE 802.3, 反射多项式 0xEDB88320; 校验值 0xCBF43926 已验证） */
uint32_t wal_crc32(const uint8_t *data, size_t len);

/* 写文件头; 返回 WAL_OK / WAL_ERR_IO */
int wal_write_header(FILE *fp);

/* 校验并读取文件头, *off 越过文件头; 返回 WAL_OK / 错误码 */
int wal_read_header(const uint8_t *buf, size_t avail, size_t *off);

/* 追加一条 record; 返回 WAL_OK / WAL_ERR_IO */
int wal_append_record(FILE *fp, uint8_t type,
                      const uint8_t *payload, uint16_t len);

/* 内存中解析下一条 record（安全解析示范: 先校验长度再逐字段读取）;
 * 返回 1=成功 / 0=读到日志尾 / 负数为错误码。
 * payload 指向 buf 内部, 不拷贝——只读使用安全 */
int wal_parse_record(const uint8_t *buf, size_t avail, size_t *off,
                     uint8_t *type, const uint8_t **payload, uint16_t *len);

#endif /* WAL_H */
