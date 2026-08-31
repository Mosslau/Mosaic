/* sol-01-protocol-fields.c —— 参考实现：用 stdint.h 重写协议字段定义
 * 把"int/long 声明"的协议头改成 uint16_t/uint32_t 固定宽度, 加 _Static_assert
 * 尺寸契约; 提供 pack/unpack 打包解包函数, 字段打印一律用 PRIx32/PRIx64 格式宏
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-01-protocol-fields.c -o sol01
// 运行：./sol01（题目与验收见 exercises/README 练习 1）
// 验证状态：已验证（-std=c11 零警告; 打包→解包往返一致, 尺寸断言通过）
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* 消息头: 每个字段宽度与平台无关, 可用于协议/文件格式 */
typedef struct {
    uint16_t magic;   /* 魔数 0xCAFE */
    uint8_t  version; /* 协议版本 */
    uint8_t  flags;   /* 标志位 */
    uint32_t seq;     /* 报文序号 */
    uint32_t length;  /* 载荷长度 */
} msg_header_t;

/* 尺寸契约: 2+1+1+4+4 = 12 字节, 无对齐填充(对齐=2, 4 字节字段偏移 4/8 已对齐) */
_Static_assert(sizeof(msg_header_t) == 12, "消息头必须是 12 字节");

#define MSG_MAX 4096 /* 线上缓冲上限 */

/* 打包: 逐字段 memcpy 进字节缓冲, 规避结构体对齐/填充的平台差异;
 * 返回写入的字节数; 缓冲过小返回 -1 */
static int pack_header(const msg_header_t *h, unsigned char *out, size_t cap) {
    if (cap < sizeof(msg_header_t))
        return -1;
    size_t o = 0;
    memcpy(out + o, &h->magic, sizeof h->magic);  o += sizeof h->magic;
    memcpy(out + o, &h->version, sizeof h->version); o += sizeof h->version;
    memcpy(out + o, &h->flags, sizeof h->flags);  o += sizeof h->flags;
    memcpy(out + o, &h->seq, sizeof h->seq);      o += sizeof h->seq;
    memcpy(out + o, &h->length, sizeof h->length); o += sizeof h->length;
    return (int)o;
}

/* 解包: 反向逐字段拷回结构体 */
static void unpack_header(const unsigned char *in, msg_header_t *h) {
    size_t o = 0;
    memcpy(&h->magic, in + o, sizeof h->magic);   o += sizeof h->magic;
    memcpy(&h->version, in + o, sizeof h->version); o += sizeof h->version;
    memcpy(&h->flags, in + o, sizeof h->flags);   o += sizeof h->flags;
    memcpy(&h->seq, in + o, sizeof h->seq);       o += sizeof h->seq;
    memcpy(&h->length, in + o, sizeof h->length); o += sizeof h->length;
}

int main(void) {
    msg_header_t h = {0xCAFEu, 1u, 0x08u, 42u, 1024u};
    unsigned char wire[MSG_MAX];
    int n = pack_header(&h, wire, sizeof wire);
    if (n < 0) {
        fprintf(stderr, "打包失败: 缓冲不足\n");
        return 1;
    }
    msg_header_t back;
    unpack_header(wire, &back);
    /* 打印一律用格式宏: 写死 %d/%ld 在宽度不同的平台上就是错的 */
    printf("打包 %d 字节: magic=0x%04" PRIx16 " version=%" PRIu8
           " flags=0x%02" PRIx8 " seq=%" PRIu32 " length=%" PRIu32 "\n",
           n, back.magic, back.version, back.flags, back.seq, back.length);
    if (back.magic == h.magic && back.seq == h.seq && back.length == h.length) {
        printf("往返一致: 通过\n");
        return 0;
    }
    printf("往返一致: 失败\n");
    return 1;
}
