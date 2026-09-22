/* sol-02-endian-swap.c —— 参考实现: 大端/小端转换函数
 * 要点: 显式逐字节组装/拆解(与平台无关), swap 函数把主机序的值在
 *   大端/小端之间翻转; htonl/ntohl 只用于对照, 不参与核心逻辑。
 * 实测: write_be32 落线固定 01 02 03 04; 本机(小端)上 swap32 与 htonl 等价。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-02-endian-swap.c -o sol02
// 运行：./sol02（字节序列 + 往返 + htonl 对照, 退出码 0）
// 验证状态：已验证（-Wall -Wextra 零警告; 实测输出见文件尾注释）
#include <arpa/inet.h>   /* POSIX htonl/ntohl（仅对照用） */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* ---- 字节序翻转（swap）: 不关心平台, 只翻转字节顺序 ---- */
static uint16_t swap16(uint16_t v) {
    return (uint16_t)((v << 8) | (v >> 8));
}
static uint32_t swap32(uint32_t v) {
    return ((v & 0x000000FFu) << 24) | ((v & 0x0000FF00u) << 8) |
           ((v & 0x00FF0000u) >> 8) | ((v & 0xFF000000u) >> 24);
}

/* ---- 显式大端读取 ---- */
static uint16_t read_be16(const uint8_t *p) {
    return (uint16_t)(((uint16_t)p[0] << 8) | (uint16_t)p[1]);
}
static uint32_t read_be32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}

/* ---- 显式小端读取 ---- */
static uint16_t read_le16(const uint8_t *p) {
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}
static uint32_t read_le32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* ---- 显式写入 ---- */
static void write_be32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24);
    p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8);
    p[3] = (uint8_t)v;
}
static void write_le32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)v;
    p[1] = (uint8_t)(v >> 8);
    p[2] = (uint8_t)(v >> 16);
    p[3] = (uint8_t)(v >> 24);
}

/* ---- 运行期平台字节序检测: memcpy 位模式搬进字节数组判读 ---- */
static int is_little_endian(void) {
    uint16_t x = 0x0102u;
    uint8_t b[2];
    memcpy(b, &x, sizeof x);
    return b[0] == 0x02u;
}

static void print_bytes(const char *label, const uint8_t *b, size_t n) {
    printf("%s: ", label);
    for (size_t i = 0; i < n; i++)
        printf("%02x%s", b[i], (i + 1 == n) ? "\n" : " ");
}

int main(void) {
    printf("当前平台: %s\n", is_little_endian() ? "小端" : "大端");

    printf("swap16(0x1234) = 0x%04x\n", swap16(0x1234u));
    printf("swap32(0x01020304) = 0x%08x\n", swap32(0x01020304u));

    uint8_t buf[4];
    write_be32(buf, 0x01020304u);
    print_bytes("write_be32(0x01020304) 落线", buf, 4);
    printf("read_be32 读回: 0x%08x（往返一致）\n", read_be32(buf));
    printf("read_be16 读回前 2 字节: 0x%04x\n", read_be16(buf));

    write_le32(buf, 0x01020304u);
    print_bytes("write_le32(0x01020304) 落线", buf, 4);
    printf("read_le32 读回: 0x%08x（往返一致）\n", read_le32(buf));
    printf("read_le16 读回前 2 字节: 0x%04x\n", read_le16(buf));

    /* htonl 对照: 网络字节序 = 大端; 本机小端 → htonl(x) == swap32(x) */
    uint32_t x = 0x01020304u;
    uint8_t nb[4];
    uint32_t hn = htonl(x);
    memcpy(nb, &hn, sizeof hn);
    print_bytes("htonl(0x01020304) 首 4 字节", nb, 4);
    printf("小端平台上 htonl(x) == swap32(x): %s\n",
           hn == swap32(x) ? "是" : "否");
    printf("ntohl(htonl(x)) == x: %s\n", ntohl(hn) == x ? "是" : "否");
    return 0;
}

/* 实测输出（Apple clang 21.0.0, macOS arm64, 小端）：
 * 当前平台: 小端
 * swap16(0x1234) = 0x3412
 * swap32(0x01020304) = 0x04030201
 * write_be32(0x01020304) 落线: 01 02 03 04
 * read_be32 读回: 0x01020304（往返一致）
 * read_be16 读回前 2 字节: 0x0102
 * write_le32(0x01020304) 落线: 04 03 02 01
 * read_le32 读回: 0x01020304（往返一致）
 * read_le16 读回前 2 字节: 0x0304
 * htonl(0x01020304) 首 4 字节: 01 02 03 04
 * 小端平台上 htonl(x) == swap32(x): 是
 * ntohl(htonl(x)) == x: 是
 */
