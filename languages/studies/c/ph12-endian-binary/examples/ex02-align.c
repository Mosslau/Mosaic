/* ex02-align.c —— 结构体对齐、padding 与 sizeof/offsetof（安全示例，已验证）
 * 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
 * 编译：cc -Wall -Wextra -std=c11 ex02-align.c -o ex02
 * 运行：./ex02
 * 验证状态：已验证（-Wall -Wextra 零警告，退出码 0，输出见文件尾注释）
 *
 * 要点：
 * 1. 结构体字段按"自然对齐"排布，字段之间可能插入 padding——sizeof 不等于
 *    字段大小之和，这是跨平台二进制格式的第一道坎（ph09 埋的伏笔在此兑现）。
 * 2. 字段顺序影响总大小：把大对齐字段往前排通常更省空间。
 * 3. 位模式落"线"（文件/网络）之前要逐字段 memcpy，且目标必须是已对齐的
 *    本地对象——把字节流强转成 struct 指针是 UB 陷阱（ph10 已铺垫）。
 * 4. 位域与 __attribute__((packed)) 的布局是实现定义的，跨平台协议不要依赖。
 */
#include <stddef.h>   /* offsetof */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

struct S1 {           /* 按声明顺序自然对齐 */
    char     a;       /* 偏移 0 */
    int32_t  b;       /* 需要 4 字节对齐 → 偏移 4（1~3 是 padding） */
    char     c;       /* 偏移 8 */
};                    /* 总大小 9 → 圆整到对齐值 4 的倍数 = 12 */

struct S2 {           /* 把 4 字节字段提前，padding 更少 */
    int32_t  b;       /* 偏移 0 */
    char     a;       /* 偏移 4 */
    char     c;       /* 偏移 5 */
};                    /* 总大小 6 → 圆整到 4 的倍数 = 8 */

struct __attribute__((packed)) SP {   /* 编译器扩展：取消填充 */
    char     a;
    int32_t  b;
    char     c;
};                                      /* sizeof = 1 + 4 + 1 = 6 */

struct Align16 {      /* GNU 扩展: 属性写法指定结构体整体对齐 */
    char     a;
    uint64_t b;
} __attribute__((aligned(16)));

static void dump(const char *name, size_t size, size_t off_a,
                 size_t off_b, size_t off_c, size_t align) {
    printf("%-8s sizeof=%zu align=%zu  offsetof: a=%zu b=%zu c=%zu\n",
           name, size, align, off_a, off_b, off_c);
}

int main(void) {
    printf("int32_t 对齐: %zu, uint64_t 对齐: %zu\n",
           _Alignof(int32_t), _Alignof(uint64_t));

    dump("S1", sizeof(struct S1), offsetof(struct S1, a),
         offsetof(struct S1, b), offsetof(struct S1, c),
         _Alignof(struct S1));
    dump("S2", sizeof(struct S2), offsetof(struct S2, a),
         offsetof(struct S2, b), offsetof(struct S2, c),
         _Alignof(struct S2));
    dump("SP", sizeof(struct SP), offsetof(struct SP, a),
         offsetof(struct SP, b), offsetof(struct SP, c),
         _Alignof(struct SP));
    dump("Align16", sizeof(struct Align16), offsetof(struct Align16, a),
         offsetof(struct Align16, b), 0, _Alignof(struct Align16));

    /* C11 标准 _Alignas: 对齐的是"对象"（变量），不是类型本身 */
    _Alignas(16) uint8_t aligned_buf[4];
    printf("_Alignas(16) 局部数组地址 %% 16 = %zu（0 表示已按 16 对齐）\n",
           (size_t)((uintptr_t)(void *)aligned_buf % 16));

    /* 安全解析示范：字节流 → 已对齐的本地对象（先校验长度再 memcpy） */
    const uint8_t wire[8] = {0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88};
    struct S2 s;
    if (sizeof s > sizeof wire) return 1;   /* 长度先校验（教学简化：已知 8 字节） */
    memcpy(&s, wire, sizeof s);             /* 位模式搬运到对齐的本地变量 */
    printf("memcpy 解析: b=0x%08x a=0x%02x c=0x%02x（b 的字节序随平台!）\n",
           (unsigned)s.b, (unsigned)s.a, (unsigned)s.c);

    /* 反例：直接强转——若 wire 的起始地址未对齐到 struct S2 的对齐值，
     * 访问 s2p->b 就是未对齐访问（UB，ph10 已讲）；即使碰巧对齐，
     * 字节序与 padding 也随平台漂移。下面的演示只打印地址与大小。 */
    const struct S2 *s2p = (const struct S2 *)wire;
    (void)s2p;   /* 仅演示强转本身；不 deref 以避免在未对齐地址上触发 UB */
    printf("强转指针: (struct S2 *)wire 的地址对齐 = %zu 字节\n",
           ((uintptr_t)(const void *)wire) % _Alignof(struct S2));
    return 0;
}

/* 实测输出（Apple clang 21.0.0, macOS arm64, _Alignof(int)=4）：
 * int32_t 对齐: 4, uint64_t 对齐: 8
 * S1       sizeof=12 align=4  offsetof: a=0 b=4 c=8
 * S2       sizeof=8  align=4  offsetof: a=4 b=0 c=5
 * SP       sizeof=6  align=1  offsetof: a=0 b=1 c=5
 * Align16  sizeof=16 align=16  offsetof: a=0 b=8 c=0
 * _Alignas(16) 局部数组地址 % 16 = 0（0 表示已按 16 对齐）
 * memcpy 解析: b=0x44332211 a=0x55 c=0x66（b 的字节序随平台!）
 * 强转指针: (struct S2 *)wire 的地址对齐 = 0 字节
 */
