/* ex05-frame.c —— length-prefix frame：增量式流式解析（安全示例，已验证）
 * 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
 * 编译：cc -Wall -Wextra -std=c11 ex05-frame.c -o ex05
 * 运行：./ex05
 * 验证状态：已验证（-Wall -Wextra 零警告，退出码 0，输出见文件尾注释）
 *
 * 要点：网络/文件数据是"分块到达"的——一个 frame 可能被拆在多次 read
 * 里。length-prefix 格式（[2 字节长度][payload]）配合"先读长度、按长度
 * 等数据"的增量状态机，就能正确处理任意切分，还能识别截断与超限。
 * 对应 roadmap 必会概念「多数二进制解析应先检查长度再读取字段」。
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define FRAME_MAX_PAYLOAD 4096u   /* 长度上限: 防超长 frame 撑爆缓冲 */

/* 增量帧读取器: 维护一个"已缓冲但未消费"的字节窗口 */
typedef struct {
    uint8_t buf[FRAME_MAX_PAYLOAD + 2];   /* 上限 + 2 字节长度字段 */
    size_t  len;                          /* 当前缓冲字节数 */
    size_t  need;                         /* 当前 frame 期望总长(2+payload) */
} FrameReader;

static void fr_init(FrameReader *r) {
    r->len = 0;
    r->need = 0;
}

/* 喂入数据。返回:
 *   1  解出一个完整 frame（payload 拷入 out, 长度写入 *out_len, 可继续喂）
 *   0  数据还不够（继续喂）
 *  -1  长度字段非法（payload 超上限）
 */
static int fr_feed(FrameReader *r, const uint8_t *data, size_t n,
                   uint8_t *out, size_t cap, size_t *out_len) {
    if (n > sizeof r->buf - r->len)
        n = sizeof r->buf - r->len;              /* 防内部溢出: 只收得下的部分 */
    if (n > 0) {
        memcpy(r->buf + r->len, data, n);
        r->len += n;
    }
    if (r->len >= 2) {                           /* 长度字段(大端)齐了 */
        uint16_t plen = (uint16_t)(((uint16_t)r->buf[0] << 8) | r->buf[1]);
        if (plen > FRAME_MAX_PAYLOAD)
            return -1;                           /* 长度超上限: 直接判非法 */
        r->need = (size_t)plen + 2;
        if (r->len >= r->need) {                 /* 整个 frame 齐了 */
            if (plen > cap) return -1;           /* 调用方缓冲太小 */
            memcpy(out, r->buf + 2, plen);
            *out_len = plen;
            memmove(r->buf, r->buf + r->need, r->len - r->need);
            r->len -= r->need;                   /* 消费掉, 窗口前移 */
            r->need = 0;
            return 1;
        }
    }
    return 0;
}

/* 演示辅助: 打印一次喂入的结果 */
static const char *rc_name(int rc) {
    return rc == 1 ? "完整 frame" : rc == 0 ? "还差数据" : "长度非法";
}

int main(void) {
    /* 构造 3 个 frame 的原始字节流: "hi", "hello world", "frame3" */
    const uint8_t *p1 = (const uint8_t *)"hi";
    const uint8_t *p2 = (const uint8_t *)"hello world";
    const uint8_t *p3 = (const uint8_t *)"frame3";
    uint8_t stream[2 + 2 + 2 + 11 + 2 + 6];
    size_t off = 0;
    stream[off++] = 0; stream[off++] = 2;
    memcpy(stream + off, p1, 2); off += 2;
    stream[off++] = 0; stream[off++] = 11;
    memcpy(stream + off, p2, 11); off += 11;
    stream[off++] = 0; stream[off++] = 6;
    memcpy(stream + off, p3, 6); off += 6;
    size_t total = off;

    printf("原始字节流 %zu 字节, 含 3 个 frame\n", total);

    /* 场景 1: 分块喂入（模拟多次 read）——每 5 字节喂一次 */
    FrameReader fr;
    fr_init(&fr);
    uint8_t payload[FRAME_MAX_PAYLOAD];
    size_t got = 0, fed = 0;
    while (fed < total) {
        size_t chunk = 5;
        if (chunk > total - fed) chunk = total - fed;
        int rc = fr_feed(&fr, stream + fed, chunk, payload, sizeof payload, &got);
        printf("喂入 %zu 字节 → %s%s\n", chunk, rc_name(rc),
               rc == 1 ? "" : "");
        if (rc == 1) printf("  解出 frame: \"%.*s\" (%zu 字节)\n",
                            (int)got, (const char *)payload, got);
        else if (rc == -1) break;
        fed += chunk;
    }

    /* 场景 2: 截断——只给 2 字节长度 + 1 字节 payload, 然后 EOF */
    fr_init(&fr);
    int rc = fr_feed(&fr, (const uint8_t[]){0x00, 0x10}, 2,
                     payload, sizeof payload, &got);
    printf("截断场景: 喂 2 字节(长度=16) → %s\n", rc_name(rc));
    rc = fr_feed(&fr, (const uint8_t[]){0x61}, 1,
                 payload, sizeof payload, &got);
    printf("再喂 1 字节 payload → %s（长度 16 还差 13 字节, EOF 时应判截断）\n",
           rc_name(rc));

    /* 场景 3: 长度超上限 → 直接判非法, 不继续等 */
    fr_init(&fr);
    rc = fr_feed(&fr, (const uint8_t[]){0xFF, 0xFF}, 2,
                 payload, sizeof payload, &got);
    printf("超限场景: 长度=0xFFFF(>上限 %u) → %s\n",
           FRAME_MAX_PAYLOAD, rc_name(rc));
    return 0;
}

/* 实测输出（Apple clang 21.0.0, macOS arm64）：
 * 原始字节流 25 字节, 含 3 个 frame
 * 喂入 5 字节 → 完整 frame
 *   解出 frame: "hi" (2 字节)
 * 喂入 5 字节 → 还差数据
 * 喂入 5 字节 → 还差数据
 * 喂入 5 字节 → 完整 frame
 *   解出 frame: "hello world" (11 字节)
 * 喂入 5 字节 → 完整 frame
 *   解出 frame: "frame3" (6 字节)
 * 截断场景: 喂 2 字节(长度=16) → 还差数据
 * 再喂 1 字节 payload → 还差数据（长度 16 还差 13 字节, EOF 时应判截断）
 * 超限场景: 长度=0xFFFF(>上限 4096) → 长度非法
 */
