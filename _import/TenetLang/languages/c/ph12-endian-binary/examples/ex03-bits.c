/* ex03-bits.c —— 位运算、掩码、移位与位域对比（安全示例，已验证）
 * 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
 * 编译：cc -Wall -Wextra -std=c11 ex03-bits.c -o ex03
 * 运行：./ex03
 * 验证状态：已验证（-Wall -Wextra 零警告，退出码 0，输出见文件尾注释）
 *
 * 要点：
 * 1. 位运算/掩码/移位是二进制格式解析的基本工具：flags 打包、字段提取、
 *    字节序转换都建立在"无符号整型的移位"之上（ph10 教训：位运算一律用无符号）。
 * 2. 位域（bit-field）把位级布局交给编译器，但位域布局是实现定义的，
 *    不能用于跨平台协议；显式掩码 + 移位才是可移植做法。
 * 3. 移位位数必须先检查（0 <= n < 位宽），无符号右移是逻辑移位。
 */
#include <stdint.h>
#include <stdio.h>

/* ---- flags 打包：8 个开关位塞进一个字节（每 bit 一个权限/开关） ---- */
#define FLAG_READ  0x01u   /* bit0 */
#define FLAG_WRITE 0x02u   /* bit1 */
#define FLAG_EXEC  0x04u   /* bit2 */
#define FLAG_OWNER 0x80u   /* bit7 */

static void dump_flags(uint8_t f) {
    printf("flags=0x%02x → read=%d write=%d exec=%d owner=%d\n",
           f,
           (f & FLAG_READ) != 0, (f & FLAG_WRITE) != 0,
           (f & FLAG_EXEC) != 0, (f & FLAG_OWNER) != 0);
}

/* ---- 打包字段提取：4 位类型 + 12 位长度塞进一个 uint16_t ---- */
#define MASK_TYPE 0xF000u   /* 高 4 位 */
#define MASK_LEN  0x0FFFu   /* 低 12 位 */

static uint16_t pack_fields(unsigned type, unsigned len) {
    return (uint16_t)(((uint16_t)(type & 0x0Fu) << 12) | (uint16_t)(len & 0x0FFFu));
}

/* ---- 位域版（对照）：布局由编译器决定，跨平台不可移植 ---- */
struct BitFieldHeader {
    unsigned type : 4;
    unsigned len  : 12;
};

int main(void) {
    /* 1. 掩码读写单个 bit */
    uint8_t f = 0;
    f |= FLAG_READ | FLAG_WRITE;        /* 置位：或 */
    f &= (uint8_t)~FLAG_WRITE;          /* 清位：与非 */
    f ^= FLAG_EXEC;                     /* 翻转：异或 */
    f |= FLAG_OWNER;
    dump_flags(f);
    printf("提取 bit2(EXEC): %d\n", (f >> 2) & 1u);   /* 移位 + 掩码 1u */

    /* 2. 打包字段：显式掩码 + 移位（可移植，位域版见下） */
    uint16_t packed = pack_fields(0x3u /* type=3 */, 0xABC /* len=2748 */);
    unsigned t = (packed & MASK_TYPE) >> 12;
    unsigned l = packed & MASK_LEN;
    printf("packed=0x%04x → type=%u len=%u\n", packed, t, l);

    /* 3. 位域版对照：数值一样，但布局是实现定义的（bit order、是否跨
     *    字节、高低位端）——换编译器/平台可能变，协议格式不要用它 */
    struct BitFieldHeader bfh = {3, 0xABC};
    printf("位域版: type=%u len=%u, sizeof=%zu（布局实现定义）\n",
           bfh.type, bfh.len, sizeof bfh);

    /* 4. 移位边界：无符号移位安全（模 2 语义），但位数要先检查 */
    int n = 31;
    if (n >= 0 && n < 32)
        printf("1u << %d = %u\n", n, 1u << n);
    else
        printf("移位位数 %d 非法\n", n);
    printf("0x80000000u >> 4 = 0x%08x（无符号右移是逻辑移位, 高位补 0）\n",
           0x80000000u >> 4);
    return 0;
}

/* 实测输出（Apple clang 21.0.0, macOS arm64）：
 * flags=0x85 → read=1 write=0 exec=1 owner=1
 * 提取 bit2(EXEC): 1
 * packed=0x3abc → type=3 len=2748
 * 位域版: type=3 len=2748, sizeof=4（布局实现定义）
 * 1u << 31 = 2147483648
 * 0x80000000u >> 4 = 0x08000000（无符号右移是逻辑移位, 高位补 0）
 */
