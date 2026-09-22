/* ex02-append-replay.c —— append-only WAL：追加 / fsync / replay / 残尾处理
 *
 * 把 ex01 的记录格式落到文件：O_APPEND 原子追加（ph13 的 write_full/fsync
 * 纪律）+ 顺序 replay（长度→magic→上限→CRC 四道校验, 任一失败即停在残尾）。
 * 另含吞吐实测：结尾一次 fsync vs 每条 fsync（复现 ph13 ex03 的结论, 换
 * WAL record 口径再测一次）。
 *
 * 演示文件写 /tmp/ph16c-ex-data/, 退出时删除, 仓库零残留。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：mkdir -p /tmp/ph16c-ex && cc -Wall -Wextra -std=c11 ex02-append-replay.c -o /tmp/ph16c-ex/ex02
// 运行：/tmp/ph16c-ex/ex02（产物在 /tmp/ph16c-ex-data/, 退出码 0）
// 验证状态：已验证（零警告; 回放计数/残尾偏移为实测, 吞吐数值随机器波动、结论稳定）
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/stat.h>

#define WAL_MAGIC 0x57414C31u /* "WAL1" */
#define WAL_HDR_SIZE 13u      /* magic(4) + type(1) + klen(4) + vlen(4) */
#define WAL_MAX_KV (1024u * 1024u)

enum { WAL_PUT = 1, WAL_DEL = 2 };

static uint32_t crc32_update(uint32_t crc, const uint8_t *p, size_t n) {
    crc = ~crc;
    for (size_t i = 0; i < n; i++) {
        crc ^= p[i];
        for (int b = 0; b < 8; b++)
            crc = (crc >> 1) ^ (0xEDB88320u & (uint32_t)-(int32_t)(crc & 1u));
    }
    return ~crc;
}
static void put_u32be(uint8_t *d, uint32_t v) {
    d[0] = (uint8_t)(v >> 24); d[1] = (uint8_t)(v >> 16);
    d[2] = (uint8_t)(v >> 8);  d[3] = (uint8_t)v;
}
static uint32_t get_u32be(const uint8_t *s) {
    return ((uint32_t)s[0] << 24) | ((uint32_t)s[1] << 16) |
           ((uint32_t)s[2] << 8) | (uint32_t)s[3];
}

/* 组装一条记录到 buf, 返回总长（crc 覆盖 type..value, 即跳过 magic） */
static size_t rec_build(uint8_t *buf, uint8_t type,
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
    put_u32be(buf + total, crc32_update(0, buf + 4, total - 4));
    return total + 4;
}

/* ph13 的 write_full 纪律: 短写循环写完 */
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

static int wal_append(int fd, uint8_t type, const char *key, const char *val) {
    uint8_t buf[WAL_HDR_SIZE + 256 + 4];
    size_t n = rec_build(buf, type, key, val);
    return write_full(fd, buf, n);
}

/* ---- replay: 四道校验（长度→magic→上限→CRC）, 任一失败即停在残尾 ----
 * 长度上限是"联合上限": klen/vlen 除各自 ≤ WAL_MAX_KV 外, 还要求
 * klen+vlen ≤ WAL_MAX_KV, 否则 static payload[WAL_MAX_KV+4] 会被
 * fread 越界写坏——"防恶意文件"必须同时挡住"各接近上限的两段"。 */
typedef struct {
    int puts;
    int dels;
} replay_stat_t;

/* 返回 0=干净 EOF, 1=残尾（*torn_at 为截断点偏移）, -1=IO 错误 */
static int wal_replay(const char *path, replay_stat_t *st, long *torn_at) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    st->puts = 0;
    st->dels = 0;
    long off = 0;
    static uint8_t payload[WAL_MAX_KV + 4];
    for (;;) {
        uint8_t hdr[WAL_HDR_SIZE];
        size_t got = fread(hdr, 1, WAL_HDR_SIZE, f);
        if (got != WAL_HDR_SIZE) {
            /* 头都读不齐: 正好干净 EOF 返回 0, 否则是截断残尾 */
            *torn_at = off;
            fclose(f);
            return (got == 0) ? 0 : 1;
        }
        uint32_t magic = get_u32be(hdr);
        uint8_t type = hdr[4];
        uint32_t klen = get_u32be(hdr + 5);
        uint32_t vlen = get_u32be(hdr + 9);
        if (magic != WAL_MAGIC || klen > WAL_MAX_KV || vlen > WAL_MAX_KV ||
            klen + vlen > WAL_MAX_KV) {
            *torn_at = off;          /* magic/联合长度上限拦截（防 payload 越界） */
            fclose(f);
            return 1;
        }
        if (fread(payload, 1, (size_t)klen + vlen + 4, f) != (size_t)klen + vlen + 4) {
            *torn_at = off;          /* payload 读不齐=截断 */
            fclose(f);
            return 1;
        }
        /* crc 覆盖 type..value: 头里跳过 magic 的 9 字节 + payload 前 klen+vlen;
         * 两段式 crc32_update 与对拼接区单段计算等价（~ 翻转成对抵消） */
        uint32_t crc = crc32_update(0, hdr + 4, WAL_HDR_SIZE - 4);
        crc = crc32_update(crc, payload, (size_t)klen + vlen);
        uint32_t crc_stored = get_u32be(payload + klen + vlen);
        if (crc != crc_stored) {
            *torn_at = off;          /* CRC 拦截 */
            fclose(f);
            return 1;
        }
        if (type == WAL_PUT) st->puts++;
        else if (type == WAL_DEL) st->dels++;
        off += (long)(WAL_HDR_SIZE + klen + vlen + 4);
    }
}

static double now_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

int main(void) {
    const char *dir = "/tmp/ph16c-ex-data";
    mkdir(dir, 0755);
    char path[128];
    snprintf(path, sizeof path, "%s/demo.wal", dir);
    remove(path);

    /* 1. 追加 3 条: PUT name / PUT city / DEL name */
    int fd = open(path, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0) { perror("open"); return 1; }
    wal_append(fd, WAL_PUT, "name", "tenet");
    wal_append(fd, WAL_PUT, "city", "hangzhou");
    wal_append(fd, WAL_DEL, "name", "");
    fsync(fd); /* 刷盘边界: 到这才算落盘（macOS 真落盘需 F_FULLFSYNC, 见 ph13） */
    close(fd);
    replay_stat_t st;
    long torn = 0;
    int r = wal_replay(path, &st, &torn);
    printf("[1] 追加 3 条后回放: 结果=%s, PUT=%d DEL=%d\n",
           r == 0 ? "干净 EOF" : "残尾", st.puts, st.dels);

    /* 2. 制造残尾: 手工写 6 字节（magic 对但头不全）, 回放应停在准确偏移 */
    fd = open(path, O_WRONLY | O_APPEND);
    const char *junk = "\x57\x41\x4c\x31\x01\x00";
    write_full(fd, (const uint8_t *)junk, 6);
    close(fd);
    r = wal_replay(path, &st, &torn);
    printf("[2] 写入 6 字节残尾后回放: 结果=%s, PUT=%d DEL=%d, 残尾偏移=%ld\n",
           r == 1 ? "残尾" : "?", st.puts, st.dels, torn);
    truncate(path, torn); /* 与 ph13 kvl_repair 同款: ftruncate 砍掉残尾 */
    r = wal_replay(path, &st, &torn);
    printf("    ftruncate 修复后回放: 结果=%s（恢复干净, 可继续追加）\n",
           r == 0 ? "干净 EOF" : "?");

    /* 3. 吞吐实测: 20000 条, 结尾一次 fsync vs 每条 fsync */
    double t_batch = 0.0, t_each = 0.0;
    for (int mode = 0; mode < 2; mode++) {
        char bp[128];
        snprintf(bp, sizeof bp, "%s/bench%d.wal", dir, mode);
        remove(bp);
        fd = open(bp, O_WRONLY | O_CREAT | O_APPEND, 0644);
        double t0 = now_sec();
        const int N = 20000;
        for (int i = 0; i < N; i++) {
            char k[32], v[32];
            snprintf(k, sizeof k, "key%06d", i);
            snprintf(v, sizeof v, "val%06d", i);
            wal_append(fd, WAL_PUT, k, v);
            if (mode == 1) fsync(fd); /* 每条都刷盘 */
        }
        fsync(fd);
        double dt = now_sec() - t0;
        close(fd);
        if (mode == 0) t_batch = dt; else t_each = dt;
        printf("[3] %s: %d 条 / %.1f ms ≈ %.0f 条/s\n",
               mode == 0 ? "结尾一次 fsync" : "每条都 fsync  ",
               N, dt * 1000.0, (double)N / dt);
        remove(bp);
    }
    printf("    每条 fsync 比批量慢约 %.0f 倍（数值随机器与负载波动）; macOS 的 fsync\n",
           t_each / t_batch);
    printf("    只到设备缓存, 真落盘用 fcntl(F_FULLFSYNC) 差距更大（见 ph13 ex03）\n");
    remove(path);
    return 0;
}
