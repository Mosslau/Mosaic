/* sol-04 的 C 侧验收程序：main.c —— 不透明句柄模式。
 *
 * 教学点：VecStore 对 C 是完全不透明类型（只有前向声明），所有操作走句柄函数；
 * 归还唯一通道是 vecstore_destroy——C 侧没有机会用 free()/sizeof 犯错。
 *
 * 验证环境：Apple clang 21.0.0（macOS arm64）。
 * 命令（在 sol-04-opaque-handle/ 下执行）：
 *   export PATH="$HOME/.cargo/bin:$PATH"
 *   export CARGO_TARGET_DIR=/tmp/ph23-sol04-target
 *   cargo build --release
 *   clang -Wall -Wextra -O2 caller/main.c -o /tmp/ph23-sol04-main \
 *       -L/tmp/ph23-sol04-target/release -lsol04_vecstore \
 *       -Wl,-rpath,/tmp/ph23-sol04-target/release
 *   /tmp/ph23-sol04-main
 */
#include <stdio.h>

/* 错误码常量与 Rust 侧一致 */
#define VS_OK 0
#define VS_ERR_NULL (-1)
#define VS_ERR_IDX (-2)

/* 不透明类型前向声明：C 侧永远只知道「有这么个结构体」 */
typedef struct VecStore VecStore;

extern VecStore *vecstore_new(void);
extern int vecstore_push(VecStore *h, double v);
extern int vecstore_get(VecStore *h, long long i, double *out);
extern long long vecstore_len(VecStore *h);
extern void vecstore_destroy(VecStore *h);

int main(void) {
    int fail = 0;
    VecStore *h = vecstore_new();
    if (h == NULL) {
        printf("vecstore_new returned NULL\n");
        return 1;
    }

    /* push 5 个值：f(i) = i*i + 0.5 */
    for (int i = 0; i < 5; i++) {
        if (vecstore_push(h, (double)(i * i) + 0.5) != VS_OK) {
            printf("push failed at %d\n", i);
            return 1;
        }
    }
    if (vecstore_len(h) != 5) fail = 1;

    /* 全部读回并断言 */
    for (int i = 0; i < 5; i++) {
        double v = 0.0;
        int code = vecstore_get(h, i, &v);
        double expect = (double)(i * i) + 0.5;
        if (code != VS_OK || v != expect) {
            printf("get(%d) = %f, want %f (code=%d)\n", i, v, expect, code);
            fail = 1;
        }
    }

    /* 越界读：返回 -2，不写 out */
    double v = 123.0;
    if (vecstore_get(h, 99, &v) != VS_ERR_IDX || v != 123.0) {
        printf("out-of-range contract broken\n");
        fail = 1;
    }
    /* null 句柄：返回 -1 而非崩溃 */
    if (vecstore_push(NULL, 1.0) != VS_ERR_NULL) fail = 1;
    if (vecstore_len(NULL) != -1) fail = 1;

    vecstore_destroy(h);
    /* destroy(NULL) 是 no-op，也验一下 */
    vecstore_destroy(NULL);

    printf("push/get/len/destroy 全契约通过: %s\n", fail ? "FAIL" : "ALL OK");
    return fail;
}
