/* sol-04-varint.c —— 参考实现: varint(LEB128) 编码解码
 * 要点: 低 7 位一组, 非末字节带续位 0x80; uint32 最长 5 字节。
 *   解码必须检查截断(全是续位)与超长(>5 字节)——非法输入返回 0。
 * 实测: 6 组边界值编码字节序列与往返全部正确; {0x80,0x80} 判非法;
 *   连续解码 3 个 varint 结果正确。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-04-varint.c -o sol04
// 运行：./sol04（边界往返 + 非法输入 + 连续解码, 退出码 0）
// 验证状态：已验证（-Wall -Wextra 零警告; 实测输出见文件尾注释）
#include <stdint.h>
#include <stdio.h>

#define VARINT_MAX 5u

static size_t varint_encode(uint32_t v, uint8_t out[VARINT_MAX]) {
    size_t n = 0;
    while (v >= 0x80u) {
        out[n++] = (uint8_t)(v & 0x7Fu) | 0x80u;
        v >>= 7;
    }
    out[n++] = (uint8_t)v;
    return n;
}

/* 返回消耗字节数; 截断/超长返回 0 */
static size_t varint_decode(const uint8_t *in, size_t avail, uint32_t *out) {
    uint32_t v = 0;
    size_t n = 0;
    while (n < avail && n < VARINT_MAX) {
        v |= (uint32_t)(in[n] & 0x7Fu) << (7u * n);
        if ((in[n] & 0x80u) == 0) {
            *out = v;
            return n + 1;
        }
        n++;
    }
    return 0;
}

static void print_enc(const char *label, uint32_t v) {
    uint8_t enc[VARINT_MAX];
    size_t n = varint_encode(v, enc);
    printf("%-12s = %-10u → [", label, v);
    for (size_t i = 0; i < n; i++)
        printf("%s%02x", i ? " " : "", enc[i]);
    printf("] (%zu 字节) → ", n);
    uint32_t dec;
    size_t dn = varint_decode(enc, n, &dec);
    printf("解码 %u %s\n", dec,
           dn == n && dec == v ? "一致" : "不一致!");
}

int main(void) {
    printf("== 边界值往返 ==\n");
    print_enc("0", 0u);
    print_enc("127", 127u);
    print_enc("128", 128u);
    print_enc("16383", 16383u);
    print_enc("16384", 16384u);
    print_enc("0xFFFFFFFF", 0xFFFFFFFFu);

    printf("== 非法输入 ==\n");
    uint32_t dec;
    const uint8_t truncated[] = {0x80u, 0x80u};          /* 全是续位 */
    printf("截断 {0x80, 0x80}: %s\n",
           varint_decode(truncated, sizeof truncated, &dec) == 0
               ? "非法(截断)" : "意外");
    const uint8_t overlong[] = {0x80u, 0x80u, 0x80u, 0x80u, 0x80u, 0x01u};
    printf("超长 6 字节: %s\n",
           varint_decode(overlong, sizeof overlong, &dec) == 0
               ? "非法(超长)" : "意外");

    printf("== 连续解码 ==\n");
    const uint8_t stream[] = {0x01u, 0x7Fu, 0x80u, 0x01u};   /* 1, 127, 128 */
    size_t off = 0;
    const uint32_t expect[] = {1u, 127u, 128u};
    int ok = 1;
    for (size_t i = 0; i < 3; i++) {
        size_t dn = varint_decode(stream + off, sizeof stream - off, &dec);
        printf("第 %zu 个: %u %s\n", i + 1, dec,
               dn > 0 && dec == expect[i] ? "正确" : "错误");
        if (dn == 0 || dec != expect[i]) ok = 0;
        off += dn;
    }
    return ok ? 0 : 1;
}

/* 实测输出（Apple clang 21.0.0, macOS arm64）：
 * == 边界值往返 ==
 * 0            = 0          → [00] (1 字节) → 解码 0 一致
 * 127          = 127        → [7f] (1 字节) → 解码 127 一致
 * 128          = 128        → [80 01] (2 字节) → 解码 128 一致
 * 16383        = 16383      → [ff 7f] (2 字节) → 解码 16383 一致
 * 16384        = 16384      → [80 80 01] (3 字节) → 解码 16384 一致
 * 0xFFFFFFFF   = 4294967295 → [ff ff ff ff 0f] (5 字节) → 解码 4294967295 一致
 * == 非法输入 ==
 * 截断 {0x80, 0x80}: 非法(截断)
 * 超长 6 字节: 非法(超长)
 * == 连续解码 ==
 * 第 1 个: 1 正确
 * 第 2 个: 127 正确
 * 第 3 个: 128 正确
 */
