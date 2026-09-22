/* ex01-stdint-protocol.c —— 用 stdint.h 定义跨平台协议字段:
 * uint32_t 保证字段宽度不随 int/long 的平台差异漂移; _Static_assert 把
 * "尺寸契约"写进编译期; 结构体上"线"逐字段 memcpy, 规避对齐填充的平台差异;
 * 位域布局是实现定义的, 跨平台协议慎用
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 ex01-stdint-protocol.c -o ex01
// 运行：./ex01
// 验证状态：已验证（-std=c11 零警告；sizeof(proto_header_t)==16 断言通过）
#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* 固定 16 字节的协议头: 每个字段宽度与平台无关 */
typedef struct {
    uint16_t magic;    /* 魔数 0xCAFE */
    uint8_t  version;  /* 协议版本 */
    uint8_t  flags;    /* 标志位 */
    uint32_t seq;      /* 报文序号 */
    uint32_t length;   /* 载荷长度 */
    uint32_t crc32;    /* 校验和 */
} proto_header_t;

_Static_assert(sizeof(proto_header_t) == 16, "协议头必须是 16 字节");

/* 位域: 紧凑, 但布局(位顺序/对齐)由编译器决定 —— 跨平台协议慎用 */
typedef struct {
    uint16_t version : 4;
    uint16_t type    : 4;
    uint16_t flags   : 8;
} flags_bits_t;

int main(void) {
    proto_header_t h = {0xCAFEu, 1, 0, 100u, 0u, 0u};
    unsigned char wire[16];
    /* 逐字段拷贝到字节缓冲, 规避结构体对齐/填充的平台差异 */
    memcpy(wire + 0, &h.magic, 2);
    wire[2] = h.version;
    wire[3] = h.flags;
    memcpy(wire + 4, &h.seq, 4);
    memcpy(wire + 8, &h.length, 4);
    memcpy(wire + 12, &h.crc32, 4);
    printf("协议头 %zu 字节, 线上前 4 字节: %02x %02x %02x %02x\n",
           sizeof h, wire[0], wire[1], wire[2], wire[3]);
    printf("位域结构 sizeof = %zu (不同编译器可能不同!)\n", sizeof(flags_bits_t));
    return 0;
}
