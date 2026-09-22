/* sol-01-fixed-record.c —— 参考实现: 解析固定格式二进制 record
 * 布局(多字节字段大端): id(u32,4) + name(8, 补0) + score(u16,2) + level(u8,1) + reserved(u8,1)
 * 要点: 布局写死在解析逻辑里, 不依赖 struct 的 sizeof/padding——
 *   struct 布局由编译器决定(ph12 主文档 3.3), 不能当线上格式。
 * 实测: 3 条 record 全部正确解析, 截断缓冲区报"剩余 4 字节"。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-01-fixed-record.c -o sol01
// 运行：./sol01（3 条 record + 截断检测, 退出码 0）
// 验证状态：已验证（-Wall -Wextra 零警告; 实测输出见文件尾注释）
#include <stdint.h>
#include <stdio.h>

#define REC_SIZE 16u            /* 固定 record 总长 */

/* 解析一条 record; 返回 0=成功 1=长度不足 2=level 非法 */
static int parse_one(const uint8_t *b, size_t avail,
                     uint32_t *id, char name[9], uint16_t *score, int *level) {
    if (avail < REC_SIZE) return 1;              /* ① 长度先校验 */
    *id = ((uint32_t)b[0] << 24) | ((uint32_t)b[1] << 16) |
          ((uint32_t)b[2] << 8) | b[3];
    name[8] = '\0';                               /* 定界, 防溢出 */
    for (size_t i = 0; i < 8; i++)
        name[i] = (char)b[4 + i];                 /* 8 字节定长, 补 0 即 NUL */
    *score = (uint16_t)(((uint16_t)b[12] << 8) | b[13]);
    *level = b[14];
    if (*level < 1 || *level > 5) return 2;       /* ② 字段合法性校验 */
    return 0;
}

int main(void) {
    /* 构造 3 条合法 record（直接按字节写, 演示"布局即字节流"） */
    uint8_t buf[3 * REC_SIZE];
    size_t n = 0;
    /* record 0: id=1 name="alice" score=95 level=3 */
    buf[n++] = 0; buf[n++] = 0; buf[n++] = 0; buf[n++] = 1;
    const char *a = "alice";
    for (int i = 0; i < 8; i++) buf[n++] = (uint8_t)(i < 5 ? a[i] : 0);
    buf[n++] = 0; buf[n++] = 95;
    buf[n++] = 3; buf[n++] = 0;
    /* record 1: id=2 name="bob" score=87 level=2 */
    buf[n++] = 0; buf[n++] = 0; buf[n++] = 0; buf[n++] = 2;
    const char *b0 = "bob";
    for (int i = 0; i < 8; i++) buf[n++] = (uint8_t)(i < 3 ? b0[i] : 0);
    buf[n++] = 0; buf[n++] = 87;
    buf[n++] = 2; buf[n++] = 0;
    /* record 2: id=3 name="carol" score=99 level=5 */
    buf[n++] = 0; buf[n++] = 0; buf[n++] = 0; buf[n++] = 3;
    const char *c = "carol";
    for (int i = 0; i < 8; i++) buf[n++] = (uint8_t)(i < 5 ? c[i] : 0);
    buf[n++] = 0; buf[n++] = 99;
    buf[n++] = 5; buf[n++] = 0;

    printf("== 固定格式 record 解析 ==\n");
    size_t off = 0;
    int count = 0;
    while (off + REC_SIZE <= n) {
        uint32_t id;
        char name[9];
        uint16_t score;
        int level;
        int rc = parse_one(buf + off, n - off, &id, name, &score, &level);
        if (rc == 2) {
            printf("record[%d]: level 非法\n", count);
            break;
        }
        printf("record[%d]: id=%u name=%-8s score=%u level=%d\n",
               count, id, name, score, level);
        count++;
        off += REC_SIZE;
    }
    printf("共 %d 条 record (%zu 字节)\n", count, off);

    /* 截断检测: 只给 20 字节 = 1 条 + 4 字节尾巴 */
    printf("== 截断检测 ==\n");
    size_t truncated = 20;
    size_t off2 = 0;
    while (off2 + REC_SIZE <= truncated) off2 += REC_SIZE;
    printf("剩余 %zu 字节不足一条完整 record (%u 字节) → 判为截断\n",
           truncated - off2, REC_SIZE);
    return 0;
}

/* 实测输出（Apple clang 21.0.0, macOS arm64）：
 * == 固定格式 record 解析 ==
 * record[0]: id=1 name=alice    score=95 level=3
 * record[1]: id=2 name=bob      score=87 level=2
 * record[2]: id=3 name=carol    score=99 level=5
 * 共 3 条 record (48 字节)
 * == 截断检测 ==
 * 剩余 4 字节不足一条完整 record (16 字节) → 判为截断
 */
