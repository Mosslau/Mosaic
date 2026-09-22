/* sol-01-wal-replay.c —— 参考实现: WAL append / replay（含残尾修复与内存态恢复）
 *
 * 题目要点:
 *   - 记录格式: [magic u32 "WAL1"][type u8][klen u32][vlen u32][key][value][crc32 u32]
 *     多字节字段显式大端; crc 覆盖 type..value
 *   - append: O_APPEND + write_full; replay: 长度→magic→上限→CRC 四道校验
 *   - 崩溃残尾: 回放停在准确偏移, ftruncate 修复后恢复可追加
 *   - WAL 恢复语义（练习提示的核心）: 回放把每条 PUT/DEL 应用到一张内存表
 *     （put 覆盖、del 删除）——"重放日志重建内存态"; 工程版见 project/ lsm.c 的
 *     replay_to_mt 回调, 这里用最小内存表演示同一语义
 * 自测断言: 干净 EOF、PUT/DEL 计数、残尾偏移、修复后可追加、恢复后表内状态
 *           （5 PUT + 2 DEL → k0/k2/k4 在表内且值正确, k1/k3 已被 DEL 删除）。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：mkdir -p /tmp/ph16c-sol && cc -Wall -Wextra -std=c11 sol-01-wal-replay.c -o /tmp/ph16c-sol/sol01
// 运行：/tmp/ph16c-sol/sol01（演示文件在 /tmp/ph16c-sol-data/, 退出码 0）
// 验证状态：已验证（零警告; 全部断言 PASS, 见文件尾输出摘要）
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>

#define WAL_MAGIC 0x57414C31u
#define WAL_HDR 13u
#define WAL_MAXKV (1024u * 1024u)

enum { WAL_PUT = 1, WAL_DEL = 2 };

static int g_pass = 0, g_fail = 0;
#define CHECK(cond, name) do { \
    if (cond) { g_pass++; printf("PASS: %s\n", name); } \
    else { g_fail++; printf("FAIL: %s\n", name); } \
} while (0)

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

/* ---- 最小内存表: 回放的应用目标（put 覆盖 / del 删除, 演示"重建内存态"） ---- */
#define TBL_MAX 32

typedef struct {
    char keys[TBL_MAX][16];
    char vals[TBL_MAX][16];
    int n;
} tbl_t;

static void tbl_init(tbl_t *t) { t->n = 0; }

static int tbl_find(const tbl_t *t, const char *key) {
    for (int i = 0; i < t->n; i++)
        if (strcmp(t->keys[i], key) == 0) return i;
    return -1;
}

/* put: 已存在则覆盖, 否则追加; 返回 0 成功, -1 满 */
static int tbl_put(tbl_t *t, const char *key, const char *val) {
    int i = tbl_find(t, key);
    if (i >= 0) {
        snprintf(t->vals[i], sizeof t->vals[0], "%s", val);
        return 0;
    }
    if (t->n >= TBL_MAX) return -1;
    snprintf(t->keys[t->n], sizeof t->keys[0], "%s", key);
    snprintf(t->vals[t->n], sizeof t->vals[0], "%s", val);
    t->n++;
    return 0;
}

/* del: 从表里删除（练习语义"del 删除"; LSM 的 tombstone 语义见主文档 3.3/ex03） */
static void tbl_del(tbl_t *t, const char *key) {
    int i = tbl_find(t, key);
    if (i < 0) return; /* 不存在则忽略 */
    for (int j = i; j < t->n - 1; j++) {
        snprintf(t->keys[j], sizeof t->keys[0], "%s", t->keys[j + 1]);
        snprintf(t->vals[j], sizeof t->vals[0], "%s", t->vals[j + 1]);
    }
    t->n--;
}

/* 查询: 命中返回 1 且 *out 拷贝出值; 未命中返回 0 */
static int tbl_get(const tbl_t *t, const char *key, char *out) {
    int i = tbl_find(t, key);
    if (i < 0) return 0;
    snprintf(out, 16, "%s", t->vals[i]);
    return 1;
}

static int write_full(int fd, const uint8_t *p, size_t n) {
    while (n > 0) {
        ssize_t w = write(fd, p, n);
        if (w < 0) { if (errno == EINTR) continue; return -1; }
        p += (size_t)w; n -= (size_t)w;
    }
    return 0;
}

static int wal_append(int fd, uint8_t type, const char *key, const char *val) {
    uint8_t buf[WAL_HDR + 512 + 4];
    uint32_t klen = (uint32_t)strlen(key), vlen = (uint32_t)strlen(val);
    put32(buf, WAL_MAGIC);
    buf[4] = type;
    put32(buf + 5, klen);
    put32(buf + 9, vlen);
    memcpy(buf + WAL_HDR, key, klen);
    memcpy(buf + WAL_HDR + klen, val, vlen);
    size_t total = WAL_HDR + klen + vlen;
    put32(buf + total, crc32u(0, buf + 4, total - 4));
    return write_full(fd, buf, total + 4);
}

/* 回放: puts/dels 出参计数; apply 非空时把每条记录应用到内存表（重建内存态）。
 * 返回 0 干净 EOF / 1 残尾（torn_at 出参） / -1 IO 错误 */
static int wal_replay(const char *path, int *puts, int *dels, long *torn_at,
                      tbl_t *apply) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    *puts = 0; *dels = 0;
    long off = 0;
    static uint8_t payload[WAL_MAXKV + 4];
    static char keybuf[WAL_MAXKV + 1];
    for (;;) {
        uint8_t hdr[WAL_HDR];
        size_t got = fread(hdr, 1, WAL_HDR, f);
        if (got != WAL_HDR) { *torn_at = off; fclose(f); return got == 0 ? 0 : 1; }
        uint8_t type = hdr[4];
        uint32_t klen = get32(hdr + 5), vlen = get32(hdr + 9);
        /* 长度上限必须联合校验: payload 缓冲只留 WAL_MAXKV+4 字节, 若 klen/vlen
         * 各接近 WAL_MAXKV 而只查单项, fread 会越界写坏缓冲——单项 + 合计双保险 */
        if (get32(hdr) != WAL_MAGIC || klen > WAL_MAXKV || vlen > WAL_MAXKV ||
            klen + vlen > WAL_MAXKV) {
            *torn_at = off; fclose(f); return 1;
        }
        if (fread(payload, 1, (size_t)klen + vlen + 4, f) != (size_t)klen + vlen + 4) {
            *torn_at = off; fclose(f); return 1;
        }
        uint32_t crc = crc32u(0, hdr + 4, WAL_HDR - 4);
        crc = crc32u(crc, payload, (size_t)klen + vlen);
        if (crc != get32(payload + klen + vlen)) {
            *torn_at = off; fclose(f); return 1;
        }
        /* 应用: key/val 在 payload 中连续存放, 分别就地加 '\0' 后交给表 */
        memcpy(keybuf, payload, klen);
        keybuf[klen] = '\0';
        payload[klen + vlen] = '\0';
        const char *val = (const char *)payload + klen;
        if (type == WAL_PUT) {
            (*puts)++;
            if (apply) tbl_put(apply, keybuf, val);
        } else if (type == WAL_DEL) {
            (*dels)++;
            if (apply) tbl_del(apply, keybuf);
        }
        off += (long)(WAL_HDR + klen + vlen + 4);
    }
}

int main(void) {
    printf("=== sol-01: WAL append / replay ===\n");
    mkdir("/tmp/ph16c-sol-data", 0755);
    const char *path = "/tmp/ph16c-sol-data/sol01.wal";
    remove(path);

    /* 场景 1: 5 PUT + 2 DEL 往返, 回放应用到内存表 */
    int fd = open(path, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0) { perror("open"); return 1; }
    for (int i = 0; i < 5; i++) {
        char k[16], v[16];
        snprintf(k, sizeof k, "k%d", i);
        snprintf(v, sizeof v, "v%d", i);
        wal_append(fd, WAL_PUT, k, v);
    }
    wal_append(fd, WAL_DEL, "k1", "");
    wal_append(fd, WAL_DEL, "k3", "");
    fsync(fd);
    close(fd);

    int puts = 0, dels = 0;
    long torn = 0;
    char out[16];
    tbl_t t1;
    tbl_init(&t1);
    int r = wal_replay(path, &puts, &dels, &torn, &t1);
    CHECK(r == 0, "干净 EOF");
    CHECK(puts == 5, "PUT 计数 = 5");
    CHECK(dels == 2, "DEL 计数 = 2");
    CHECK(tbl_get(&t1, "k0", out) && strcmp(out, "v0") == 0, "恢复后 k0=v0");
    CHECK(tbl_get(&t1, "k2", out) && strcmp(out, "v2") == 0, "恢复后 k2=v2");
    CHECK(tbl_get(&t1, "k4", out) && strcmp(out, "v4") == 0, "恢复后 k4=v4");
    CHECK(!tbl_get(&t1, "k1", out), "恢复后 k1 已删（DEL 应用生效）");
    CHECK(!tbl_get(&t1, "k3", out), "恢复后 k3 已删（DEL 应用生效）");

    /* 场景 2: 残尾停在准确偏移, 残尾之前的完整记录照常应用 */
    int rd = open(path, O_RDONLY);
    if (rd < 0) { perror("open"); return 1; }
    long sz = (long)lseek(rd, 0, SEEK_END);
    close(rd);
    fd = open(path, O_WRONLY | O_APPEND);
    if (fd < 0) { perror("open"); return 1; }
    write_full(fd, (const uint8_t *)"\x57\x41\x4c\x31\x01", 5); /* 半条头 */
    close(fd);
    tbl_t t2;
    tbl_init(&t2);
    r = wal_replay(path, &puts, &dels, &torn, &t2);
    CHECK(r == 1, "识别残尾");
    CHECK(torn == sz, "残尾偏移 = 追加前文件大小");
    CHECK(puts == 5 && dels == 2, "残尾不影响已完整的记录计数");
    CHECK(tbl_get(&t2, "k4", out) && strcmp(out, "v4") == 0, "残尾前记录已应用");
    CHECK(!tbl_get(&t2, "k9", out), "残尾（半条头）未被应用");

    /* 场景 3: ftruncate 修复后恢复干净并继续追加, 新记录也能恢复 */
    CHECK(truncate(path, torn) == 0, "ftruncate 修复成功");
    tbl_t t3;
    tbl_init(&t3);
    r = wal_replay(path, &puts, &dels, &torn, &t3);
    CHECK(r == 0, "修复后干净 EOF");
    fd = open(path, O_WRONLY | O_APPEND);
    if (fd < 0) { perror("open"); return 1; }
    CHECK(wal_append(fd, WAL_PUT, "k9", "v9") == 0, "修复后可继续追加");
    close(fd);
    tbl_t t4;
    tbl_init(&t4);
    r = wal_replay(path, &puts, &dels, &torn, &t4);
    CHECK(r == 0 && puts == 6, "追加后回放 PUT = 6");
    CHECK(tbl_get(&t4, "k9", out) && strcmp(out, "v9") == 0, "追加的 k9 恢复成功");

    remove(path);
    printf("sol-01: %d PASS, %d FAIL, 退出码 %d\n", g_pass, g_fail, g_fail ? 1 : 0);
    return g_fail ? 1 : 0;
}
