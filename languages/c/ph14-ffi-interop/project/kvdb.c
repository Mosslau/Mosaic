/* kvdb.c —— C ABI KV 库实现（WAL 持久化, 格式见 kvdb.h 头部注释）
 *
 * 编译（macOS, 供其他语言调用）：
 *   cc -Wall -Wextra -std=c11 -dynamiclib kvdb.c -o /tmp/ph14-proj/libkvdb.dylib
 */
#include "kvdb.h"

#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define KVDB_MAGIC 0x4B564442u   /* "KVDB" */
#define WAL_HDR_SIZE 12u         /* magic + plen + crc */

struct kvdb {
    int fd;                       /* WAL 文件描述符（O_APPEND 追加写） */
    char keys[KVDB_MAX_KEYS][KVDB_MAX_KEY_LEN];  /* 教学用固定容量线性表 */
    uint8_t *vals[KVDB_MAX_KEYS];
    uint32_t vlen[KVDB_MAX_KEYS];
    uint32_t count;
};

/* ---------- 字节序与 CRC（衔接 ph12/ph13 的线上格式纪律） ---------- */

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

/* CRC-32（IEEE 802.3 反射多项式）, 与 ph13 kvl 同一实现 */
static uint32_t crc32(const uint8_t *data, uint32_t len) {
    uint32_t crc = 0xFFFFFFFFu;
    for (uint32_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int b = 0; b < 8; b++)
            crc = (crc >> 1) ^ ((crc & 1u) ? 0xEDB88320u : 0u);
    }
    return ~crc;
}

/* write_full：循环写齐（短写处理, ph13 纪律） */
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

/* ---------- 内存态应用（put 与回放共用） ---------- */

static int32_t apply(kvdb_t *db, const char *key, uint32_t klen,
                     const uint8_t *val, uint32_t vlen) {
    if (klen >= KVDB_MAX_KEY_LEN || vlen > KVDB_MAX_VAL_LEN)
        return KVDB_ERR_BADARG;
    uint32_t slot = db->count;
    for (uint32_t i = 0; i < db->count; i++) {
        if (strncmp(db->keys[i], key, klen) == 0 && db->keys[i][klen] == '\0') {
            slot = i;                 /* 覆盖已有 key */
            break;
        }
    }
    if (slot == db->count) {          /* 新 key */
        if (db->count >= KVDB_MAX_KEYS)
            return KVDB_ERR_FULL;
        memcpy(db->keys[slot], key, klen);
        db->keys[slot][klen] = '\0';
        db->count++;
    }
    uint8_t *copy = malloc(vlen == 0 ? 1u : vlen);
    if (copy == NULL)
        return KVDB_ERR_NOMEM;
    if (vlen > 0)
        memcpy(copy, val, vlen);
    free(db->vals[slot]);             /* 覆盖旧值 */
    db->vals[slot] = copy;
    db->vlen[slot] = vlen;
    return KVDB_OK;
}

/* ---------- WAL 追加与回放 ---------- */

static int32_t append_wal(kvdb_t *db, const char *key, uint32_t klen,
                          const uint8_t *val, uint32_t vlen) {
    uint32_t plen = 4u + klen + 4u + vlen;   /* [klen][key][vlen][val] */
    uint8_t *pl = malloc(plen == 0u ? 1u : plen);
    if (pl == NULL)
        return KVDB_ERR_NOMEM;
    write_be32(pl, klen);
    memcpy(pl + 4, key, klen);
    write_be32(pl + 4 + klen, vlen);
    if (vlen > 0)
        memcpy(pl + 4 + klen + 4, val, vlen);

    uint8_t hdr[WAL_HDR_SIZE];
    write_be32(hdr, KVDB_MAGIC);
    write_be32(hdr + 4, plen);
    write_be32(hdr + 8, crc32(pl, plen));

    int ok = write_full(db->fd, hdr, sizeof hdr) == 0 &&
             write_full(db->fd, pl, plen) == 0;
    free(pl);
    return ok ? KVDB_OK : KVDB_ERR_IO;
}

/* 回放 WAL 重建内存态：读到干净 EOF 停；残尾（半写/损坏）安全忽略
 * （ph13 的"崩溃最多留下最后一条残记录"语义） */
static int32_t replay(kvdb_t *db) {
    uint8_t hdr[WAL_HDR_SIZE];
    off_t off = 0;
    for (;;) {
        ssize_t r = pread(db->fd, hdr, WAL_HDR_SIZE, off);
        if (r < 0)
            return KVDB_ERR_IO;
        if (r == 0)
            break;                              /* 干净 EOF */
        if (r < (ssize_t)WAL_HDR_SIZE)
            break;                              /* 残尾: 头部没写全 */
        if (read_be32(hdr) != KVDB_MAGIC)
            break;                              /* 损坏: 忽略之后全部 */
        uint32_t plen = read_be32(hdr + 4);
        uint32_t crc = read_be32(hdr + 8);
        if (plen > 4u + KVDB_MAX_KEY_LEN + 4u + KVDB_MAX_VAL_LEN)
            break;                              /* 长度非法 */
        uint8_t *pl = malloc(plen == 0u ? 1u : plen);
        if (pl == NULL)
            return KVDB_ERR_NOMEM;
        r = pread(db->fd, pl, plen, off + (off_t)WAL_HDR_SIZE);
        if (r < 0) {
            free(pl);
            return KVDB_ERR_IO;
        }
        if (r < (ssize_t)plen) {
            free(pl);
            break;                              /* 残尾: payload 没写全 */
        }
        if (crc32(pl, plen) != crc) {
            free(pl);
            break;                              /* 残尾: 半写入/位翻转 */
        }
        uint32_t klen = read_be32(pl);
        uint32_t vlen = read_be32(pl + 4 + klen);
        if (4u + klen + 4u + vlen != plen) {
            free(pl);
            break;                              /* 长度自相矛盾 */
        }
        int32_t rc = apply(db, (const char *)(pl + 4), klen,
                           pl + 4 + klen + 4, vlen);
        free(pl);
        if (rc != KVDB_OK)
            return rc;
        off += (off_t)WAL_HDR_SIZE + plen;
    }
    return KVDB_OK;
}

/* ---------- 公共接口 ---------- */

kvdb_t *kvdb_create(const char *path, int32_t *err_out) {
    if (err_out != NULL)
        *err_out = KVDB_OK;
    if (path == NULL || path[0] == '\0') {
        if (err_out != NULL)
            *err_out = KVDB_ERR_BADARG;
        return NULL;
    }
    int fd = open(path, O_CREAT | O_RDWR | O_APPEND, 0644);
    if (fd < 0) {
        if (err_out != NULL)
            *err_out = KVDB_ERR_IO;
        return NULL;
    }
    kvdb_t *db = malloc(sizeof *db);
    if (db == NULL) {
        close(fd);
        if (err_out != NULL)
            *err_out = KVDB_ERR_NOMEM;
        return NULL;
    }
    memset(db, 0, sizeof *db);
    db->fd = fd;
    int32_t rc = replay(db);
    if (rc != KVDB_OK) {
        kvdb_destroy(db);
        if (err_out != NULL)
            *err_out = rc;
        return NULL;
    }
    return db;
}

int32_t kvdb_put(kvdb_t *db, const char *key,
                 const uint8_t *val, uint32_t vlen) {
    if (db == NULL || key == NULL || key[0] == '\0' ||
        (vlen > 0 && val == NULL))
        return KVDB_ERR_BADARG;
    size_t klen = strlen(key);
    if (klen >= KVDB_MAX_KEY_LEN || vlen > KVDB_MAX_VAL_LEN)
        return KVDB_ERR_BADARG;
    int32_t rc = apply(db, key, (uint32_t)klen, val, vlen);
    if (rc != KVDB_OK)
        return rc;
    return append_wal(db, key, (uint32_t)klen, val, vlen);
}

int32_t kvdb_get(kvdb_t *db, const char *key,
                 uint8_t *out, uint32_t cap, uint32_t *vlen_out) {
    if (db == NULL || key == NULL || (cap > 0 && out == NULL))
        return KVDB_ERR_BADARG;
    for (uint32_t i = 0; i < db->count; i++) {
        if (strcmp(db->keys[i], key) == 0) {
            if (vlen_out != NULL)
                *vlen_out = db->vlen[i];
            if (cap < db->vlen[i])
                return KVDB_ERR_BADARG;       /* 缓冲区不够 */
            if (db->vlen[i] > 0)
                memcpy(out, db->vals[i], db->vlen[i]);
            return KVDB_OK;
        }
    }
    return KVDB_ERR_NOTFOUND;
}

int32_t kvdb_sync(kvdb_t *db) {
    if (db == NULL)
        return KVDB_ERR_BADARG;
    return fsync(db->fd) == 0 ? KVDB_OK : KVDB_ERR_IO;
}

int32_t kvdb_destroy(kvdb_t *db) {
    if (db == NULL)
        return KVDB_ERR_BADARG;
    for (uint32_t i = 0; i < db->count; i++)
        free(db->vals[i]);
    close(db->fd);
    free(db);
    return KVDB_OK;
}

const char *kvdb_strerror(int32_t err) {
    switch (err) {
    case KVDB_OK:         return "ok";
    case KVDB_ERR_BADARG: return "invalid argument";
    case KVDB_ERR_NOMEM:  return "out of memory";
    case KVDB_ERR_IO:     return "io error";
    case KVDB_ERR_FULL:   return "kv store full";
    case KVDB_ERR_NOTFOUND: return "key not found";
    default:              return "unknown error";
    }
}
