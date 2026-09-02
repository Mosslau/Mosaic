/* sstable.c —— SSTable 实现（布局见 sstable.h） */
#include "sstable.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void put32(uint8_t *d, uint32_t v) {
    d[0] = (uint8_t)(v >> 24); d[1] = (uint8_t)(v >> 16);
    d[2] = (uint8_t)(v >> 8); d[3] = (uint8_t)v;
}
static void put64(uint8_t *d, uint64_t v) {
    for (int i = 0; i < 8; i++) d[i] = (uint8_t)(v >> (56 - 8 * i));
}
static uint32_t get32(const uint8_t *s) {
    return ((uint32_t)s[0] << 24) | ((uint32_t)s[1] << 16) |
           ((uint32_t)s[2] << 8) | (uint32_t)s[3];
}
static uint64_t get64(const uint8_t *s) {
    uint64_t v = 0;
    for (int i = 0; i < 8; i++) v = (v << 8) | s[i];
    return v;
}

int sst_write(const char *path, const memtable_t *m) {
    FILE *f = fopen(path, "wb");
    if (!f) return -1;
    /* bloom: 每 key 10 位, k=7 */
    bloom_t bl;
    if (bloom_init(&bl, m->len * 10 + 64, 7) != 0) { fclose(f); return -1; }
    for (size_t i = 0; i < m->len; i++) bloom_add(&bl, m->e[i].key);

    size_t idx_cap = m->len / SST_IDX_EVERY + 1;
    char (*idx_key)[64] = malloc(idx_cap * sizeof *idx_key);
    uint64_t *idx_off = malloc(idx_cap * sizeof *idx_off);
    if (!idx_key || !idx_off) {
        free(idx_key); free(idx_off); bloom_free(&bl); fclose(f);
        return -1;
    }
    size_t idx_cnt = 0;

    /* 数据区 */
    for (size_t i = 0; i < m->len; i++) {
        if (i % SST_IDX_EVERY == 0) {
            snprintf(idx_key[idx_cnt], 64, "%s", m->e[i].key);
            idx_off[idx_cnt] = (uint64_t)ftell(f);
            idx_cnt++;
        }
        uint8_t hdr[9];
        uint32_t klen = (uint32_t)strlen(m->e[i].key);
        uint32_t vlen = m->e[i].type == MT_DEL ? 0 : (uint32_t)strlen(m->e[i].val);
        put32(hdr, klen);
        hdr[4] = m->e[i].type;
        put32(hdr + 5, vlen);
        if (fwrite(hdr, 1, 9, f) != 9) goto io_fail;
        if (fwrite(m->e[i].key, 1, klen, f) != klen) goto io_fail;
        if (vlen && fwrite(m->e[i].val, 1, vlen, f) != vlen) goto io_fail;
    }
    /* 索引区 */
    uint64_t index_off = (uint64_t)ftell(f);
    for (size_t i = 0; i < idx_cnt; i++) {
        uint8_t buf[4 + 64 + 8];
        uint32_t klen = (uint32_t)strlen(idx_key[i]);
        put32(buf, klen);
        memcpy(buf + 4, idx_key[i], klen);
        put64(buf + 4 + klen, idx_off[i]);
        if (fwrite(buf, 1, 4 + klen + 8, f) != 4 + klen + 8) goto io_fail;
    }
    /* bloom 区 */
    uint64_t bloom_off = (uint64_t)ftell(f);
    size_t bloom_bytes = bl.nbits / 8 + 1;
    if (fwrite(bl.bits, 1, bloom_bytes, f) != bloom_bytes) goto io_fail;
    /* footer */
    {
        uint8_t ftr[SST_FTR_SIZE];
        memset(ftr, 0, sizeof ftr);
        put64(ftr, index_off);
        put32(ftr + 8, (uint32_t)idx_cnt);
        put64(ftr + 12, bloom_off);
        put32(ftr + 20, (uint32_t)bl.nbits);
        put32(ftr + 24, SST_MAGIC);
        if (fwrite(ftr, 1, SST_FTR_SIZE, f) != SST_FTR_SIZE) goto io_fail;
    }
    free(idx_key);
    free(idx_off);
    bloom_free(&bl);
    if (fclose(f) != 0) return -1;
    return 0;

io_fail:
    free(idx_key);
    free(idx_off);
    bloom_free(&bl);
    fclose(f);
    return -1;
}

int sst_open(sst_t *s, const char *path) {
    memset(s, 0, sizeof *s);
    snprintf(s->path, sizeof s->path, "%s", path);
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    uint8_t ftr[SST_FTR_SIZE];
    if (fseek(f, -(long)SST_FTR_SIZE, SEEK_END) != 0 ||
        fread(ftr, 1, SST_FTR_SIZE, f) != SST_FTR_SIZE ||
        get32(ftr + 24) != SST_MAGIC) {
        fclose(f);
        return -1;
    }
    uint64_t index_off = get64(ftr);
    uint32_t idx_cnt = get32(ftr + 8);
    uint64_t bloom_off = get64(ftr + 12);
    uint32_t bloom_bits = get32(ftr + 20);

    s->idx_key = malloc((idx_cnt ? idx_cnt : 1) * sizeof *s->idx_key);
    s->idx_off = malloc((idx_cnt ? idx_cnt : 1) * sizeof *s->idx_off);
    if (!s->idx_key || !s->idx_off) { fclose(f); return -1; }
    s->idx_cnt = idx_cnt;
    if (fseek(f, (long)index_off, SEEK_SET) != 0) goto fail;
    for (uint32_t i = 0; i < idx_cnt; i++) {
        uint8_t lb[4];
        if (fread(lb, 1, 4, f) != 4) goto fail;
        uint32_t klen = get32(lb);
        if (klen >= 64 || fread(s->idx_key[i], 1, klen, f) != klen) goto fail;
        s->idx_key[i][klen] = '\0';
        uint8_t ob[8];
        if (fread(ob, 1, 8, f) != 8) goto fail;
        s->idx_off[i] = get64(ob);
    }
    if (bloom_init(&s->bloom, bloom_bits, 7) != 0) goto fail;
    if (fseek(f, (long)bloom_off, SEEK_SET) != 0) goto fail;
    if (fread(s->bloom.bits, 1, bloom_bits / 8 + 1, f) != bloom_bits / 8 + 1) goto fail;
    fclose(f);
    return 0;

fail:
    free(s->idx_key);
    free(s->idx_off);
    s->idx_key = NULL;
    s->idx_off = NULL;
    fclose(f);
    return -1;
}

int sst_get(sst_t *s, const char *key, char *out, size_t cap) {
    /* 1. bloom 预检: 肯定不在 → 零数据区 IO */
    if (!bloom_maybe(&s->bloom, key)) {
        s->bloom_skips++;
        return 1;
    }
    /* 2. 索引二分: 最后一个 key <= target 的索引项 */
    long lo = -1;
    uint32_t hi = s->idx_cnt;
    while ((uint32_t)(lo + 1) < hi) {
        uint32_t mid = (uint32_t)(lo + 1) + (hi - (uint32_t)(lo + 1)) / 2;
        if (strcmp(s->idx_key[mid], key) <= 0) lo = (long)mid;
        else hi = mid;
    }
    if (lo < 0) return 1;
    /* 3. 数据区顺扫至多 SST_IDX_EVERY 条 */
    FILE *f = fopen(s->path, "rb");
    if (!f) return -1;
    s->disk_reads++;
    int rc = 1;
    if (fseek(f, (long)s->idx_off[lo], SEEK_SET) != 0) { fclose(f); return -1; }
    for (int i = 0; i < SST_IDX_EVERY; i++) {
        uint8_t hdr[9];
        if (fread(hdr, 1, 9, f) != 9) break;
        uint32_t klen = get32(hdr);
        uint8_t type = hdr[4];
        uint32_t vlen = get32(hdr + 5);
        char kbuf[64];
        if (klen >= 64 || fread(kbuf, 1, klen, f) != klen) break;
        kbuf[klen] = '\0';
        int cmp = strcmp(kbuf, key);
        if (cmp == 0) {
            if (type == MT_DEL) { rc = 2; break; } /* tombstone: 挡住旧层 */
            uint32_t take = vlen < cap - 1 ? vlen : (uint32_t)cap - 1;
            if (fread(out, 1, take, f) != take) { rc = -1; break; }
            out[take] = '\0';
            rc = 0;
            break;
        }
        if (cmp > 0) break;
        if (fseek(f, (long)vlen, SEEK_CUR) != 0) break;
    }
    fclose(f);
    return rc;
}

void sst_close(sst_t *s) {
    free(s->idx_key);
    free(s->idx_off);
    bloom_free(&s->bloom);
    s->idx_key = NULL;
    s->idx_off = NULL;
}
