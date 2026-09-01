/* ex06-varint.c —— varint 编码解码 + magic/版本号文件头（安全示例，已验证）
 * 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
 * 编译：cc -Wall -Wextra -std=c11 ex06-varint.c -o ex06
 * 运行：./ex06
 * 验证状态：已验证（-Wall -Wextra 零警告，退出码 0，输出见文件尾注释）
 *
 * 要点：
 * 1. varint（LEB128）：每个字节 7 位数据 + 1 位"还有后续"标记，小整数只占
 *    1 字节——紧凑且与字节序无关（按字节流解释，天然可移植）。
 * 2. 解码必须检查"是否还有后续"与溢出（超过 5 字节即非法, 高位数据丢失）。
 * 3. magic number + 版本号是文件格式的第一道防线：识别"这不是我们的文件"
 *   与"这是旧版本文件", 配合长度/CRC 形成完整格式契约（对应 roadmap 必会
 *   概念「二进制格式要考虑版本兼容和损坏检测」）。
 */
#include <stdint.h>
#include <stdio.h>

#define VARINT_MAX_BYTES 5u      /* uint32 的 varint 最长 5 字节 */

/* ---- 编码: 低 7 位一组, 高位字节带续位标记 ---- */
static size_t varint_encode(uint32_t v, uint8_t out[VARINT_MAX_BYTES]) {
    size_t n = 0;
    while (v >= 0x80u) {
        out[n++] = (uint8_t)(v & 0x7Fu) | 0x80u;   /* 续位标记 0x80 */
        v >>= 7;
    }
    out[n++] = (uint8_t)v;                          /* 末字节无续位标记 */
    return n;
}

/* ---- 解码: 返回消耗字节数; 非法输入返回 0 ---- */
static size_t varint_decode(const uint8_t *in, size_t avail, uint32_t *out) {
    uint32_t v = 0;
    size_t n = 0;
    while (n < avail && n < VARINT_MAX_BYTES) {
        v |= (uint32_t)(in[n] & 0x7Fu) << (7u * n);   /* 每字节 7 位 */
        if ((in[n] & 0x80u) == 0) {                   /* 无续位 → 结束 */
            *out = v;
            return n + 1;
        }
        n++;
    }
    return 0;   /* 截断或超 5 字节: 非法 */
}

/* ---- 文件头: magic(4) + 版本(1) + 记录数 varint(1~5) ---- */
#define HDR_MAGIC 0x4E563031u   /* "NV01" */
#define HDR_VERSION 1u

int main(void) {
    /* 1. 编码/解码往返 */
    const uint32_t tests[] = {0u, 1u, 127u, 128u, 300u, 16383u, 16384u,
                              0xFFFFFFFFu};
    size_t ntests = sizeof tests / sizeof tests[0];
    for (size_t i = 0; i < ntests; i++) {
        uint8_t enc[VARINT_MAX_BYTES];
        size_t n = varint_encode(tests[i], enc);
        printf("varint(%-10u) =", tests[i]);
        for (size_t j = 0; j < n; j++)
            printf(" %02x", enc[j]);
        printf("  (%zu 字节)", n);
        uint32_t dec = 0;
        size_t dn = varint_decode(enc, n, &dec);
        printf(" → 解码 %u (%s)\n", dec,
               dn == n && dec == tests[i] ? "往返一致" : "往返不一致!");
    }

    /* 2. 非法输入: 截断的 varint（只有续位, 没有结束字节） */
    const uint8_t bad1[] = {0x80u, 0x80u};          /* 2 字节都是续位 */
    uint32_t dec = 0;
    printf("解码 {0x80 0x80}: %s\n",
           varint_decode(bad1, sizeof bad1, &dec) == 0 ? "非法(截断)" : "意外");

    /* 3. 文件头: magic + 版本 + 记录数, 模拟"读取文件头并校验" */
    uint8_t hdr[4 + 1 + VARINT_MAX_BYTES];
    size_t h = 0;
    hdr[h++] = (uint8_t)(HDR_MAGIC >> 24);
    hdr[h++] = (uint8_t)(HDR_MAGIC >> 16);
    hdr[h++] = (uint8_t)(HDR_MAGIC >> 8);
    hdr[h++] = (uint8_t)HDR_MAGIC;
    hdr[h++] = HDR_VERSION;
    h += varint_encode(300000u, hdr + h);           /* 记录数 */

    uint32_t magic = ((uint32_t)hdr[0] << 24) | ((uint32_t)hdr[1] << 16) |
                     ((uint32_t)hdr[2] << 8) | hdr[3];
    if (magic != HDR_MAGIC) {
        printf("文件头: magic 不匹配 (0x%08x)\n", magic);
        return 1;
    }
    if (hdr[4] != HDR_VERSION) {
        printf("文件头: 版本 %u 不支持\n", hdr[4]);
        return 1;
    }
    size_t dn = varint_decode(hdr + 5, h - 5, &dec);
    printf("文件头: magic=0x%08x 版本=%u 记录数=%u (%zu 字节头)\n",
           magic, hdr[4], dec, 5u + dn);
    return 0;
}

/* 实测输出（Apple clang 21.0.0, macOS arm64）：
 * varint(0         ) = 00  (1 字节) → 解码 0 (往返一致)
 * varint(1         ) = 01  (1 字节) → 解码 1 (往返一致)
 * varint(127       ) = 7f  (1 字节) → 解码 127 (往返一致)
 * varint(128       ) = 80 01  (2 字节) → 解码 128 (往返一致)
 * varint(300       ) = ac 02  (2 字节) → 解码 300 (往返一致)
 * varint(16383     ) = ff 7f  (2 字节) → 解码 16383 (往返一致)
 * varint(16384     ) = 80 80 01  (3 字节) → 解码 16384 (往返一致)
 * varint(4294967295) = ff ff ff ff 0f  (5 字节) → 解码 4294967295 (往返一致)
 * 解码 {0x80 0x80}: 非法(截断)
 * 文件头: magic=0x4e563031 版本=1 记录数=300000 (8 字节头)
 */
