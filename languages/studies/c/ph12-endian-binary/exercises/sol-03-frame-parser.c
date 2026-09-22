/* sol-03-frame-parser.c —— 参考实现: length-prefix frame 增量解析器
 * 格式: [len: u16 大端][payload: len 字节], len 上限 4096。
 * 增量状态机: 数据分块喂入仍能正确拆帧; 返回 1=完整 frame / 0=还差数据 / -1=长度非法。
 * 实测: 变长块(1,2,3,...)喂入 3 个 frame 全部解出; 截断与超限正确识别。
 */
// 验证环境：Apple clang 21.0.0（cc），macOS（Darwin arm64）
// 编译：cc -Wall -Wextra -std=c11 sol-03-frame-parser.c -o sol03
// 运行：./sol03（变长块喂入 + 截断 + 超限, 退出码 0）
// 验证状态：已验证（-Wall -Wextra 零警告; 实测输出见文件尾注释）
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define FRAME_MAX 4096u

typedef struct {
    uint8_t buf[FRAME_MAX + 2];
    size_t len;
    size_t need;
} Framer;

static void fr_init(Framer *f) {
    f->len = 0;
    f->need = 0;
}

/* 喂入数据; 返回 1=解出 frame(payload 拷入 out) / 0=还差 / -1=长度非法 */
static int fr_feed(Framer *f, const uint8_t *data, size_t n,
                   uint8_t *out, size_t cap, size_t *out_len) {
    if (n > sizeof f->buf - f->len)
        n = sizeof f->buf - f->len;
    if (n > 0) {
        memcpy(f->buf + f->len, data, n);
        f->len += n;
    }
    if (f->len >= 2) {
        uint16_t plen = (uint16_t)(((uint16_t)f->buf[0] << 8) | f->buf[1]);
        if (plen > FRAME_MAX) return -1;        /* 长度超上限: 非法 */
        f->need = (size_t)plen + 2;
        if (f->len >= f->need) {
            if (plen > cap) return -1;
            memcpy(out, f->buf + 2, plen);
            *out_len = plen;
            memmove(f->buf, f->buf + f->need, f->len - f->need);
            f->len -= f->need;
            f->need = 0;
            return 1;
        }
    }
    return 0;
}

int main(void) {
    /* 3 个 frame: "ping"(4) + "pong"(4) + "frame-parser"(13) */
    const char *p[3] = {"ping", "pong", "frame-parser"};
    const size_t plen[3] = {4, 4, 13};
    uint8_t stream[512];
    size_t total = 0;
    for (int i = 0; i < 3; i++) {
        stream[total++] = 0;
        stream[total++] = (uint8_t)plen[i];
        memcpy(stream + total, p[i], plen[i]);
        total += plen[i];
    }

    printf("== 变长块喂入（1,2,3,... 字节）==\n");
    Framer f;
    fr_init(&f);
    uint8_t payload[FRAME_MAX];
    size_t got = 0, fed = 0, chunk = 1;
    int frames = 0;
    while (fed < total) {
        if (chunk > total - fed) chunk = total - fed;
        int rc = fr_feed(&f, stream + fed, chunk, payload, sizeof payload, &got);
        if (rc == 1) {
            printf("解出 frame %d: \"%.*s\" (%zu 字节)\n",
                   frames + 1, (int)got, (const char *)payload, got);
            frames++;
        } else if (rc == -1) {
            printf("长度非法\n");
            break;
        }
        fed += chunk;
        chunk++;                       /* 变长: 1,2,3,... */
    }
    printf("共解出 %d 个 frame\n", frames);

    printf("== 截断场景 ==\n");
    fr_init(&f);
    int rc = fr_feed(&f, (const uint8_t[]){0x00, 0x20}, 2,
                     payload, sizeof payload, &got);
    rc = fr_feed(&f, (const uint8_t[]){'a', 'b', 'c'}, 3,
                 payload, sizeof payload, &got);
    printf("长度=32 只喂 5 字节 → %s（EOF 时应判截断）\n",
           rc == 1 ? "完整 frame" : rc == 0 ? "还差数据" : "长度非法");

    printf("== 超限场景 ==\n");
    fr_init(&f);
    rc = fr_feed(&f, (const uint8_t[]){0xFF, 0xFF}, 2,
                 payload, sizeof payload, &got);
    printf("长度=0xFFFF(>上限 %u) → %s\n", FRAME_MAX,
           rc == -1 ? "长度非法" : "（意外）");
    return 0;
}

/* 实测输出（Apple clang 21.0.0, macOS arm64）：
 * == 变长块喂入（1,2,3,... 字节）==
 * 解出 frame 1: "ping" (4 字节)
 * 解出 frame 2: "pong" (4 字节)
 * 解出 frame 3: "frame-parser" (13 字节)
 * 共解出 3 个 frame
 * == 截断场景 ==
 * 长度=32 只喂 5 字节 → 还差数据（EOF 时应判截断）
 * == 超限场景 ==
 * 长度=0xFFFF(>上限 4096) → 长度非法
 */
