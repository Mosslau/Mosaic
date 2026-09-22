/* wal.c —— WAL 实现（格式与契约见 wal.h） */
#include "wal.h"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static uint32_t crc32u(uint32_t crc, const uint8_t *p, size_t n) {
    crc = ~crc;
    for (size_t i = 0; i < n; i++) {
        crc ^= p[i];
        for (int b = 0; b < 8; b++)
            crc = (crc >> 1) ^ (0xEDB88320u & (uint32_t)-(int32_t)(crc & 1u));
    }
    return ~crc;
}
static void put32(uint8_t *d, uint32_t v) {
    d[0] = (uint8_t)(v >> 24); d[1] = (uint8_t)(v >> 16);
    d[2] = (uint8_t)(v >> 8); d[3] = (uint8_t)v;
}
static uint32_t get32(const uint8_t *s) {
    return ((uint32_t)s[0] << 24) | ((uint32_t)s[1] << 16) |
           ((uint32_t)s[2] << 8) | (uint32_t)s[3];
}

int wal_open(const char *path) {
    return open(path, O_WRONLY | O_CREAT | O_APPEND, 0644);
}

static int write_full(int fd, const uint8_t *p, size_t n) {
    while (n > 0) {
        ssize_t w = write(fd, p, n);
        if (w < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        p += (size_t)w;
        n -= (size_t)w;
    }
    return 0;
}

int wal_append(int fd, uint8_t type, const char *key, const char *val) {
    uint8_t stack_buf[WAL_HDR_SIZE + 4096 + 4];
    uint32_t klen = (uint32_t)strlen(key);
    uint32_t vlen = (uint32_t)strlen(val);
    if (klen > WAL_MAX_KV || vlen > WAL_MAX_KV) return -1;
    uint8_t *buf = stack_buf;
    if (klen + vlen > 4096) return -1; /* 教学版: 单条 key+value ≤ 4 KiB */
    put32(buf, WAL_MAGIC);
    buf[4] = type;
    put32(buf + 5, klen);
    put32(buf + 9, vlen);
    memcpy(buf + WAL_HDR_SIZE, key, klen);
    memcpy(buf + WAL_HDR_SIZE + klen, val, vlen);
    size_t total = WAL_HDR_SIZE + klen + vlen;
    put32(buf + total, crc32u(0, buf + 4, total - 4));
    return write_full(fd, buf, total + 4);
}

int wal_sync(int fd) {
    return fsync(fd);
}

wal_end_t wal_replay(const char *path, wal_visit_fn visit, void *ctx,
                     long *torn_at) {
    FILE *f = fopen(path, "rb");
    if (!f) return WAL_END_IOERR;
    long off = 0;
    static uint8_t payload[WAL_MAX_KV + 4];
    for (;;) {
        uint8_t hdr[WAL_HDR_SIZE];
        size_t got = fread(hdr, 1, WAL_HDR_SIZE, f);
        if (got != WAL_HDR_SIZE) {
            *torn_at = off;
            fclose(f);
            return got == 0 ? WAL_END_CLEAN : WAL_END_TORN;
        }
        uint8_t type = hdr[4];
        uint32_t klen = get32(hdr + 5), vlen = get32(hdr + 9);
        /* 防恶意文件: 除单项上限外, 还要校验单条 klen+vlen 联合上限——
         * payload 缓冲只有 WAL_MAX_KV+4 字节, 若只查单项, klen/vlen 各接近
         * WAL_MAX_KV 时下面的 fread 会越过缓冲写坏内存。写路径同款限制
         * 见 wal_append（单条 key+value ≤ 4 KiB, 远小于此处上限, 合法文件不会误伤） */
        if (get32(hdr) != WAL_MAGIC || klen > WAL_MAX_KV || vlen > WAL_MAX_KV ||
            klen + vlen > WAL_MAX_KV) {
            *torn_at = off;
            fclose(f);
            return WAL_END_TORN;
        }
        if (fread(payload, 1, (size_t)klen + vlen + 4, f) != (size_t)klen + vlen + 4) {
            *torn_at = off;
            fclose(f);
            return WAL_END_TORN;
        }
        uint32_t crc = crc32u(0, hdr + 4, WAL_HDR_SIZE - 4);
        crc = crc32u(crc, payload, (size_t)klen + vlen);
        if (crc != get32(payload + klen + vlen)) {
            *torn_at = off;
            fclose(f);
            return WAL_END_TORN;
        }
        if (visit) {
            /* key/val 在 payload 中连续存放, 需分别终止:
             * key 拷到独立缓冲加 '\0'; val 末尾本来就跟 crc, 就地终止安全 */
            static char keybuf[WAL_MAX_KV + 1];
            memcpy(keybuf, payload, klen);
            keybuf[klen] = '\0';
            payload[klen + vlen] = '\0';
            char *val = (char *)payload + klen;
            int stop = visit(type, keybuf, val, ctx);
            if (stop) {
                fclose(f);
                *torn_at = off;
                return WAL_END_CLEAN;
            }
        }
        off += (long)(WAL_HDR_SIZE + klen + vlen + 4);
    }
}

int wal_repair(const char *path, long torn_at) {
    return truncate(path, torn_at);
}
