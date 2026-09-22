/* ex07 的 C 侧消费者：main.c —— 观察「Rust 分配 → C 改写 → Rust 校验 → Rust 释放」。
 *
 * 教学点：
 * - C 侧持有的是普通指针，写起来毫无限制——自由越大责任越大：不许 free() 它、
 *   归还时必须带上与分配时一致的 len。
 * - ex07_sum 是对 C 改写的校验：证明内存是同一块，不是拷贝。
 *
 * 验证环境：Apple clang 21.0.0（macOS arm64）。
 * 编译/链接/运行命令（在 examples/ex07-ownership-box-transfer/ 下执行）：
 *   export PATH="$HOME/.cargo/bin:$PATH"
 *   export CARGO_TARGET_DIR=/tmp/ph23-ex07-target
 *   cargo build --release
 *   clang -Wall -Wextra -O2 caller/main.c -o /tmp/ph23-ex07-main \
 *       -L/tmp/ph23-ex07-target/release -lex07_ownership \
 *       -Wl,-rpath,/tmp/ph23-ex07-target/release
 *   /tmp/ph23-ex07-main
 */
#include <stdio.h>

extern double *ex07_allocate(int len);
extern double ex07_sum(const double *buf, int len);
extern void ex07_free(double *buf, int len);

int main(void) {
    int fail = 0;
    const int len = 16;

    double *buf = ex07_allocate(len);
    if (buf == NULL) {
        printf("allocate returned NULL\n");
        return 1;
    }
    printf("allocated buf=%p len=%d\n", (void *)buf, len);

    /* C 侧直接写内存：让每个元素 = 下标平方（完全绕过 Rust 借用检查） */
    for (int i = 0; i < len; i++) {
        buf[i] = (double)(i * i);
    }

    /* 调回 Rust：求和应等于 Σi² = len(len-1)(2len-1)/6 */
    double s = ex07_sum(buf, len);
    double expect = (double)len * (len - 1) * (2 * len - 1) / 6.0;
    printf("sum after C writes = %.0f (expect %.0f)\n", s, expect);
    if (s != expect) fail = 1;

    /* 归还：唯一合法通道是 ex07_free（与分配成对，且带上 len）。
     * 绝不能在这里调用 free(buf)——那是 C 分配器在释放 Rust 分配器的内存，
     * 是「谁分配谁释放」红线的违例（见主文档 3.6/4.3）。 */
    ex07_free(buf, len);
    printf(fail ? "FAIL\n" : "ALL OK\n");
    return fail;
}
