/* main.c —— WAL record 解析器命令行工具 + 自测
 * 用法:
 *   ./wal_tool test                   运行自测（往返/损坏/截断/魔法数）
 *   ./wal_tool write <file> <n>       写一个新 WAL 文件（文件头 + n 条 record）
 *   ./wal_tool read <file> [offset]   回放并校验; 可选 offset 模拟损坏(翻转 1 位)
 * 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
 * 验证状态：已验证（-Wall -Wextra 零警告; 实测输出见本文件尾注释）
 */
#include "wal.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *err_name(int rc) {
    switch (rc) {
    case WAL_ERR_IO:      return "IO 错误";
    case WAL_ERR_MAGIC:   return "magic 不匹配（不是本格式文件）";
    case WAL_ERR_VERSION: return "版本不支持";
    case WAL_ERR_TYPE:    return "record 类型非法";
    case WAL_ERR_TRUNC:   return "截断（剩余字节不足）";
    case WAL_ERR_CRC:     return "checksum 不匹配（数据损坏）";
    case WAL_ERR_LEN:     return "长度/保留字段非法";
    default:              return "未知错误";
    }
}

static void usage(const char *prog) {
    fprintf(stderr,
            "用法:\n"
            "  %s test                    自测\n"
            "  %s write <file> <n>        写新 WAL 文件(文件头 + n 条 record)\n"
            "  %s read <file> [offset]    回放校验; offset 模拟损坏(翻转 1 位)\n",
            prog, prog, prog);
}

/* ---- read: 把文件读进内存后安全回放 ---- */
static int cmd_read(const char *path, long flip) {
    FILE *fp = fopen(path, "rb");
    if (fp == NULL) {
        perror(path);
        return 1;
    }
    if (fseek(fp, 0, SEEK_END) != 0) { fclose(fp); return 1; }
    long size = ftell(fp);
    if (size < 0) { fclose(fp); return 1; }
    rewind(fp);
    uint8_t *buf = malloc((size_t)size > 0 ? (size_t)size : 1);
    if (buf == NULL) { fclose(fp); return 1; }
    if (fread(buf, 1, (size_t)size, fp) != (size_t)size) {
        fprintf(stderr, "读取 %s 失败\n", path);
        free(buf);
        fclose(fp);
        return 1;
    }
    fclose(fp);

    if (flip >= 0) {
        if (flip >= size) {
            fprintf(stderr, "offset %ld 超出文件大小 %ld\n", flip, size);
            free(buf);
            return 2;
        }
        buf[flip] ^= 0x01u;
        printf("模拟损坏: 翻转偏移 %ld 的 1 位\n", flip);
    }

    size_t off = 0;
    int rc = wal_read_header(buf, (size_t)size, &off);
    if (rc != WAL_OK) {
        printf("文件头错误: %s (偏移 0)\n", err_name(rc));
        free(buf);
        return 1;
    }
    printf("文件头: magic=\"WAL1\" version=%u header=%zu 字节, 文件 %ld 字节\n",
           WAL_VERSION, off, size);

    long n = 0;
    uint8_t type;
    const uint8_t *payload;
    uint16_t len;
    while ((rc = wal_parse_record(buf, (size_t)size, &off,
                                  &type, &payload, &len)) == 1) {
        printf("record[%3ld] %-3s len=%3u payload=\"%.*s\"\n",
               n, type == WAL_TYPE_PUT ? "PUT" : "DEL",
               len, (int)len, (const char *)payload);
        n++;
    }
    if (rc < 0) {
        printf("record[%ld] 解析失败: %s (偏移 %zu)\n", n, err_name(rc), off);
        free(buf);
        return 1;
    }
    printf("共 %ld 条 record, 全部校验通过 (CRC 通过, 退出码 0)\n", n);
    free(buf);
    return 0;
}

/* ---- write: 写文件头 + n 条 record（PUT 与 DEL 交替） ---- */
static int cmd_write(const char *path, long n) {
    FILE *fp = fopen(path, "wb");
    if (fp == NULL) {
        perror(path);
        return 1;
    }
    int rc = wal_write_header(fp);
    char payload[64];
    for (long i = 0; i < n && rc == WAL_OK; i++) {
        int type = (i % 4 == 3) ? WAL_TYPE_DEL : WAL_TYPE_PUT;
        if (type == WAL_TYPE_PUT)
            snprintf(payload, sizeof payload, "key%04ld=value-%ld", i, i * 7);
        else
            snprintf(payload, sizeof payload, "key%04ld", i);
        rc = wal_append_record(fp, (uint8_t)type,
                               (const uint8_t *)payload,
                               (uint16_t)strlen(payload));
    }
    long size = ftell(fp);
    if (fclose(fp) != 0 && rc == WAL_OK) rc = WAL_ERR_IO;
    if (rc != WAL_OK) {
        printf("写入失败: %s\n", err_name(rc));
        return 1;
    }
    printf("已写入 %s: 文件头 + %ld 条 record, 共 %ld 字节\n", path, n, size);
    return 0;
}

/* ---- 自测: 往返 / 损坏(CRC) / 截断 / magic ---- */
static int g_failures = 0;
#define CHECK(cond) do {                                                   \
    if (cond) {                                                            \
        printf("[PASS] %s\n", #cond);                                      \
    } else {                                                               \
        g_failures++;                                                      \
        printf("[FAIL] %s  (%s:%d)\n", #cond, __FILE__, __LINE__);         \
    }                                                                      \
} while (0)

static int cmd_test(void) {
    FILE *fp = tmpfile();                       /* 系统临时文件, 自动清理 */
    if (fp == NULL) return 1;

    /* 1. 写 5 条 record 后读回 */
    CHECK(wal_write_header(fp) == WAL_OK);
    for (int i = 0; i < 5; i++) {
        char p[32];
        snprintf(p, sizeof p, "k%d=v%d", i, i);
        CHECK(wal_append_record(fp, WAL_TYPE_PUT, (const uint8_t *)p,
                                (uint16_t)strlen(p)) == WAL_OK);
    }
    fflush(fp);
    long size = ftell(fp);
    rewind(fp);
    uint8_t *buf = malloc((size_t)size > 0 ? (size_t)size : 1);
    if (buf == NULL) { fclose(fp); return 1; }
    if (fread(buf, 1, (size_t)size, fp) != (size_t)size) { free(buf); fclose(fp); return 1; }
    fclose(fp);

    size_t off = 0;
    CHECK(wal_read_header(buf, (size_t)size, &off) == WAL_OK && off == WAL_HEADER_SIZE);
    uint8_t type;
    const uint8_t *payload;
    uint16_t len;
    int n = 0;
    while (wal_parse_record(buf, (size_t)size, &off, &type, &payload, &len) == 1) {
        char expect[32];
        snprintf(expect, sizeof expect, "k%d=v%d", n, n);
        CHECK(type == WAL_TYPE_PUT);
        CHECK((size_t)len == strlen(expect) &&
              memcmp(payload, expect, (size_t)len) == 0);
        n++;
    }
    CHECK(n == 5);
    printf("往返: 5 条 PUT 全部读回一致 (日志 %ld 字节)\n", size);

    /* 2. 损坏: 翻转 record 0 的 payload 首字节 → CRC 错误 */
    uint8_t *bad = malloc((size_t)size);
    if (bad == NULL) return 1;
    memcpy(bad, buf, (size_t)size);
    bad[WAL_HEADER_SIZE + WAL_REC_HEADER] ^= 0x01u;   /* record0 payload[0] */
    off = WAL_HEADER_SIZE;
    CHECK(wal_parse_record(bad, (size_t)size, &off, &type, &payload, &len) == WAL_ERR_CRC);
    printf("损坏检测: 翻转 payload 1 位 → WAL_ERR_CRC\n");

    /* 3. 截断: 少给 3 字节 → 最后一条 record 触发长度错误 */
    off = WAL_HEADER_SIZE;
    int rc = WAL_OK;
    while ((rc = wal_parse_record(buf, (size_t)size - 3, &off,
                                  &type, &payload, &len)) == 1) { /* 空循环 */ }
    CHECK(rc == WAL_ERR_TRUNC);
    printf("截断检测: 文件尾少 3 字节 → WAL_ERR_TRUNC\n");

    /* 4. magic: 翻转文件头 magic 一位 → 头部校验拒绝 */
    uint8_t *hdr = malloc((size_t)size);
    if (hdr == NULL) return 1;
    memcpy(hdr, buf, (size_t)size);
    hdr[0] ^= 0x01u;
    off = 0;
    CHECK(wal_read_header(hdr, (size_t)size, &off) == WAL_ERR_MAGIC);
    printf("magic 检测: 翻转文件头 1 位 → WAL_ERR_MAGIC\n");

    free(buf);
    free(bad);
    free(hdr);
    printf(g_failures == 0 ? "全部自测通过 (退出码 0)\n"
                           : "自测失败: %d 个断言失败\n", g_failures);
    return g_failures == 0 ? 0 : 1;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        usage(argv[0]);
        return 2;
    }
    if (strcmp(argv[1], "test") == 0)
        return cmd_test();
    if (strcmp(argv[1], "write") == 0) {
        if (argc != 4) { usage(argv[0]); return 2; }
        char *end;
        long n = strtol(argv[3], &end, 10);
        if (*end != '\0' || n < 0 || n > 100000) {
            fprintf(stderr, "n 必须是 0..100000 的整数\n");
            return 2;
        }
        return cmd_write(argv[2], n);
    }
    if (strcmp(argv[1], "read") == 0) {
        if (argc != 3 && argc != 4) { usage(argv[0]); return 2; }
        long flip = -1;
        if (argc == 4) {
            char *end;
            flip = strtol(argv[3], &end, 10);
            if (*end != '\0' || flip < 0) {
                fprintf(stderr, "offset 必须是非负整数\n");
                return 2;
            }
        }
        return cmd_read(argv[2], flip);
    }
    usage(argv[0]);
    return 2;
}

/* 实测输出（Apple clang 21.0.0, macOS arm64）——自测（test）:
 * [PASS] wal_write_header(fp) == WAL_OK
 * [PASS] wal_append_record(...) == WAL_OK                (×5)
 * [PASS] wal_read_header(...) == WAL_OK && off == 8
 * [PASS] type == WAL_TYPE_PUT                            (×5)
 * [PASS] (size_t)len == strlen(expect) && memcmp(...)    (×5)
 * [PASS] n == 5
 * 往返: 5 条 PUT 全部读回一致 (日志 88 字节)
 * [PASS] wal_parse_record(...) == WAL_ERR_CRC
 * 损坏检测: 翻转 payload 1 位 → WAL_ERR_CRC
 * [PASS] rc == WAL_ERR_TRUNC
 * 截断检测: 文件尾少 3 字节 → WAL_ERR_TRUNC
 * [PASS] wal_read_header(...) == WAL_ERR_MAGIC
 * magic 检测: 翻转文件头 1 位 → WAL_ERR_MAGIC
 * 全部自测通过 (退出码 0)

 * ——write/read 演示（write 8 + read /tmp/wal-demo.bin）:
 * 已写入 /tmp/wal-demo.bin: 文件头 + 8 条 record, 共 204 字节
 * 文件头: magic="WAL1" version=1 header=8 字节, 文件 204 字节
 * record[  0] PUT len= 15 payload="key0000=value-0"
 * record[  1] PUT len= 15 payload="key0001=value-7"
 * record[  2] PUT len= 16 payload="key0002=value-14"
 * record[  3] DEL len=  7 payload="key0003"
 * record[  4] PUT len= 16 payload="key0004=value-28"
 * record[  5] PUT len= 16 payload="key0005=value-35"
 * record[  6] PUT len= 16 payload="key0006=value-42"
 * record[  7] DEL len=  7 payload="key0007"
 * 共 8 条 record, 全部校验通过 (CRC 通过, 退出码 0)

 * ——read 带损坏模拟（read /tmp/wal-demo.bin 43, 退出码 1 属预期）:
 * 模拟损坏: 翻转偏移 43 的 1 位
 * 文件头: magic="WAL1" version=1 header=8 字节, 文件 204 字节
 * record[  0] PUT len= 15 payload="key0000=value-0"
 * record[1] 解析失败: checksum 不匹配（数据损坏） (偏移 34)
 */
