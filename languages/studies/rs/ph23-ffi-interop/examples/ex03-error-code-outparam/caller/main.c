/* ex03 的 C 侧消费者：main.c —— 错误码 + out 参数 + panic 护栏。
 *
 * 教学点：
 * - C 侧不看 Result，只看返回值：0=成功、负数=错误码；成功才读 out。
 * - panic 不会穿越边界（ex03_panic_probe(1) 返回 -3 而不是中止进程）。
 *
 * 验证环境：Apple clang 21.0.0（macOS arm64）。
 * 编译/链接/运行命令（在 examples/ex03-error-code-outparam/ 下执行）：
 *   export PATH="$HOME/.cargo/bin:$PATH"
 *   export CARGO_TARGET_DIR=/tmp/ph23-ex03-target
 *   cargo build --release
 *   clang -Wall -Wextra -O2 caller/main.c -o /tmp/ph23-ex03-main \
 *       -L/tmp/ph23-ex03-target/release -lex03_error \
 *       -Wl,-rpath,/tmp/ph23-ex03-target/release
 *   /tmp/ph23-ex03-main
 */
#include <stdio.h>

/* 错误码常量必须与 Rust 侧保持一致（FFI_OK=0 / NULL=-1 / PARSE=-2 / PANIC=-3）；
 * 用 cbindgen 生成头文件（ex05）可让「两边的错误码」不再靠人肉同步。 */
#define FFI_OK 0
#define FFI_ERR_NULL (-1)
#define FFI_ERR_PARSE (-2)
#define FFI_ERR_PANIC (-3)

extern int ex03_parse_port(const char *s, unsigned short *out);
extern int ex03_panic_probe(int trigger);

static void try_parse(const char *label, const char *s) {
    unsigned short out = 0xDEAD; /* 哨兵值：失败时不应被写入 */
    int code = ex03_parse_port(s, &out);
    if (code == FFI_OK) {
        printf("%-16s -> OK, port=%u\n", label, out);
    } else {
        printf("%-16s -> err=%d (out 未被写入, 哨兵保留=%u)\n", label, code, out);
    }
}

int main(void) {
    int fail = 0;

    try_parse("\"8080\"", "8080");
    try_parse("\"0\"", "0");           /* 业务非法：端口 0 */
    try_parse("\"70000\"", "70000");   /* 超出 u16 */
    try_parse("\"abc\"", "abc");       /* 非数字 */

    /* null 指针路径 */
    int code = ex03_parse_port(NULL, NULL);
    printf("%-16s -> err=%d\n", "NULL, NULL", code);
    if (code != FFI_ERR_NULL) fail = 1;

    /* panic 护栏：trigger=1 在 Rust 侧故意 panic，期望返回 -3 而非进程崩溃 */
    int p0 = ex03_panic_probe(0);
    int p1 = ex03_panic_probe(1);
    printf("panic_probe(0)=%d panic_probe(1)=%d (护栏生效=%s)\n", p0, p1,
           p1 == FFI_ERR_PANIC ? "yes" : "NO");
    if (p1 != FFI_ERR_PANIC) fail = 1;

    printf(fail ? "FAIL\n" : "ALL OK\n");
    return fail;
}
