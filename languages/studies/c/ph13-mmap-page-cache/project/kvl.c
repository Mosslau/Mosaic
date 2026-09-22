/* kvl.c —— kvlog 记录格式实现（格式定义见 kvl.h） */
#include "kvl.h"

#include <fcntl.h>
#include <unistd.h>

uint32_t kvl_crc32(const uint8_t *data, uint32_t len) {
    uint32_t crc = 0xFFFFFFFFu;
    for (uint32_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int b = 0; b < 8; b++)
            crc = (crc >> 1) ^ ((crc & 1u) ? 0xEDB88320u : 0u);
    }
    return ~crc;
}

static void write_be32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24);
    p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8);
    p[3] = (uint8_t)v;
}

static uint32_t read_be32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}

static int write_full(int fd, const void *buf, size_t n) {
    const char *p = buf;
    size_t left = n;
    while (left > 0) {
        ssize_t w = write(fd, p, left);
        if (w < 0)
            return -1;
        p += w;
        left -= (size_t)w;
    }
    return 0;
}

int kvl_open_append(const char *path) {
    return open(path, O_CREAT | O_WRONLY | O_APPEND, 0644);
}

int kvl_append(int fd, const void *payload, uint32_t len) {
    if (len > KVL_MAX_PAYLOAD)
        return -1;
    uint8_t hdr[KVL_HDR_SIZE];
    write_be32(hdr, KVL_MAGIC);
    write_be32(hdr + 4, len);
    write_be32(hdr + 8, kvl_crc32(payload, len));
    if (write_full(fd, hdr, sizeof hdr) < 0)
        return -1;
    if (write_full(fd, payload, len) < 0)
        return -1;
    return 0;
}

int kvl_sync(int fd) {
    return fsync(fd);
}

kvl_end_t kvl_replay(const char *path, kvl_visit_fn visit, void *ctx,
                     int *count, off_t *torn_at) {
    static uint8_t payload[KVL_MAX_PAYLOAD];
    uint8_t hdr[KVL_HDR_SIZE];
    int n = 0;
    off_t off = 0;

    int fd = open(path, O_RDONLY);
    if (fd < 0)
        return KVL_END_IOERR;
    for (;;) {
        ssize_t r = pread(fd, hdr, KVL_HDR_SIZE, off);
        if (r < 0)
            goto ioerr;
        if (r == 0)
            break;                          /* 干净 EOF */
        if (r < (ssize_t)KVL_HDR_SIZE)
            goto torn;                      /* 头部没写全 */
        if (read_be32(hdr) != KVL_MAGIC)
            goto torn;                      /* magic 不符 = 损坏 */
        uint32_t len = read_be32(hdr + 4);
        uint32_t crc = read_be32(hdr + 8);
        if (len > KVL_MAX_PAYLOAD)
            goto torn;                      /* 长度非法 = 损坏 */
        r = pread(fd, payload, len, off + (off_t)KVL_HDR_SIZE);
        if (r < 0)
            goto ioerr;
        if (r < (ssize_t)len)
            goto torn;                      /* payload 没写全 */
        if (kvl_crc32(payload, len) != crc)
            goto torn;                      /* 半写入/位翻转 */
        if (visit && visit(payload, len, ctx) != 0)
            break;                          /* 调用方主动停止，视为干净结束 */
        n++;
        off += (off_t)KVL_HDR_SIZE + len;
    }
    close(fd);
    *count = n;
    *torn_at = off;
    return KVL_END_CLEAN;

torn:
    close(fd);
    *count = n;
    *torn_at = off;
    return KVL_END_TORN;

ioerr:
    close(fd);
    return KVL_END_IOERR;
}

int kvl_repair(const char *path, off_t torn_at) {
    int fd = open(path, O_WRONLY);
    if (fd < 0)
        return -1;
    int rc = ftruncate(fd, torn_at);
    close(fd);
    return rc;
}
