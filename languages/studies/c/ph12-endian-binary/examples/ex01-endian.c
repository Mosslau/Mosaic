/* ex01-endian.c —— 大小端检测与显式字节序读写（安全示例，已验证）
 * 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
 * 编译：cc -Wall -Wextra -std=c11 ex01-endian.c -o ex01
 * 运行：./ex01
 * 验证状态：已验证（-Wall -Wextra 零警告，退出码 0，输出见文件尾注释）
 *
 * 要点：多字节字段在内存中的字节顺序随平台不同（大端/小端），
 * 跨平台交换必须显式按字节组装/拆解——不要用"强转指针后读字段"，
 * 那会把平台字节序与 padding 直接泄露到线上格式里。
 * 查看对象表示（unsigned char * 指针读字节）在 C 中是合法且可移植的；
 * 把字节流强转成结构体指针才是要避免的（那是 ph12 的核心陷阱）。
 */
#include <arpa/inet.h>   /* POSIX 网络字节序函数 htonl/ntohl（不属于标准 C） */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* ---- 运行期大小端检测：把 0x0102 的位模式搬进字节数组再判读 ---- */
static int is_little_endian(void) {
    uint16_t x = 0x0102u;
    uint8_t b[2];
    memcpy(b, &x, sizeof x);      /* 位模式搬运（memcpy 可移植，union 是 C 扩展语义） */
    return b[0] == 0x02u;         /* 低地址字节是低位 → 小端 */
}

/* ---- 大端读取：按"高位在前"逐字节组装（网络字节序的显式实现） ---- */
static uint16_t read_be16(const uint8_t *p) {
    return (uint16_t)(((uint16_t)p[0] << 8) | (uint16_t)p[1]);
}

static uint32_t read_be32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}

/* ---- 小端读取：低位在前 ---- */
static uint16_t read_le16(const uint8_t *p) {
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

static uint32_t read_le32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* ---- 大端写入：按字节落线 ---- */
static void write_be32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24);
    p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8);
    p[3] = (uint8_t)v;
}

static void print_bytes(const char *label, const uint8_t *b, size_t n) {
    printf("%s: ", label);
    for (size_t i = 0; i < n; i++)
        printf("%02x%s", b[i], (i + 1 == n) ? "\n" : " ");
}

int main(void) {
    /* 1. 平台字节序检测 */
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    printf("编译期判定: 小端（__BYTE_ORDER__ 宏）\n");
#elif __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
    printf("编译期判定: 大端（__BYTE_ORDER__ 宏）\n");
#else
    printf("编译期判定: 未知字节序\n");
#endif
    uint16_t probe = 0x0102u;
    uint8_t pb[2];
    memcpy(pb, &probe, sizeof probe);
    printf("运行期判定: %s（0x0102 的低地址字节 = 0x%02x）\n",
           is_little_endian() ? "小端" : "大端",
           (unsigned)pb[0]);

    /* 2. 显式读写往返：write_be32 写出的字节是固定的（与平台无关） */
    uint8_t buf[4];
    write_be32(buf, 0x01020304u);
    print_bytes("write_be32(0x01020304) 落线字节", buf, 4);
    printf("read_be32 读回: 0x%08x\n", read_be32(buf));
    printf("read_be16 读回前 2 字节: 0x%04x\n", read_be16(buf));
    print_bytes("小端布局字节序列(0x01020304)", (const uint8_t[]){0x04, 0x03, 0x02, 0x01}, 4);
    printf("read_le32 读回: 0x%08x\n",
           read_le32((const uint8_t[]){0x04, 0x03, 0x02, 0x01}));
    printf("read_le16({0x34, 0x12}) = 0x%04x\n",
           read_le16((const uint8_t[]){0x34, 0x12}));

    /* 3. 与 POSIX htonl/ntohl 对照：网络字节序 = 大端 */
    uint32_t n = htonl(0x01020304u);
    uint8_t nb[4];
    memcpy(nb, &n, sizeof n);
    print_bytes("htonl(0x01020304) 首 4 字节", nb, 4);   /* 大端平台或任意平台上都是 01 02 03 04 */
    printf("ntohl(htonl(0x01020304)) = 0x%08x（往返不变）\n", ntohl(n));
    return 0;
}

/* 实测输出（Apple clang 21.0.0, macOS arm64, 小端平台）：
 * 编译期判定: 小端（__BYTE_ORDER__ 宏）
 * 运行期判定: 小端（0x0102 的低地址字节 = 0x02）
 * write_be32(0x01020304) 落线字节: 01 02 03 04
 * read_be32 读回: 0x01020304
 * read_be16 读回前 2 字节: 0x0102
 * 小端布局字节序列(0x01020304): 04 03 02 01
 * read_le32 读回: 0x01020304
 * read_le16({0x34, 0x12}) = 0x1234
 * htonl(0x01020304) 首 4 字节: 01 02 03 04
 * ntohl(htonl(0x01020304)) = 0x01020304（往返不变）
 */
