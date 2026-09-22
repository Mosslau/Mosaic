/* ex02 的 C 侧消费者：main.c —— 观察 CString/CStr 跨边界的三种形态。
 *
 * 教学点：同一批字节，C 的 strlen 数的是字节数；ex02_bytes_len 与 C 一致；
 * ex02_utf8_chars 才是「字符数」；内嵌 NUL 在 C 侧与 Rust 侧都只认到首个 NUL。
 *
 * 验证环境：Apple clang 21.0.0（macOS arm64）。
 * 编译/链接/运行命令（在 examples/ex02-cstring-boundary/ 下执行）：
 *   export PATH="$HOME/.cargo/bin:$PATH"
 *   export CARGO_TARGET_DIR=/tmp/ph23-ex02-target
 *   cargo build --release          # 先构建（cargo test 见 examples/README.md）
 *   clang -Wall -Wextra -O2 caller/main.c -o /tmp/ph23-ex02-main \
 *       -L/tmp/ph23-ex02-target/release -lex02_cstring \
 *       -Wl,-rpath,/tmp/ph23-ex02-target/release
 *   /tmp/ph23-ex02-main            # 期望输出见文件尾部注释
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern int ex02_bytes_len(const char *s);
extern int ex02_utf8_chars(const char *s);
extern char *ex02_make_greeting(void);
extern void ex02_free_string(char *s);

int main(void) {
    int fail = 0;

    /* 形态 A：C→Rust。中文串：字节数 ≠ 字符数，Rust 两侧各有其职 */
    const char *zh = "\xe4\xbd\xa0\xe5\xa5\xbd\xef\xbc\x8cRust"; /* "你好，Rust" 的 UTF-8 */
    int zb = ex02_bytes_len(zh);
    int zc = ex02_utf8_chars(zh);
    printf("zh: C strlen=%zu bytes=%d chars=%d\n", strlen(zh), zb, zc);
    if (!(zb == 13 && zc == 7)) fail = 1;

    /* 形态 B：内嵌 NUL。两侧都只认到第一个 NUL */
    const char *with_nul = "ab\0cd";
    int nb = ex02_bytes_len(with_nul);
    int nc = ex02_utf8_chars(with_nul);
    printf("with_nul: bytes=%d chars=%d (C strlen=%zu)\n", nb, nc, strlen(with_nul));
    if (!(nb == 2 && nc == 2)) fail = 1;

    /* 形态 C：Rust 分配 → C 使用 → 调回 Rust 释放（谁分配谁释放） */
    char *greeting = ex02_make_greeting();
    printf("greeting: %s\n", greeting);
    if (strcmp(greeting, "hello from rust") != 0) fail = 1;
    ex02_free_string(greeting); /* 绝不能用 free(greeting)——见主文档 3.6/4.3 */

    /* 非法 UTF-8：CStr 层照常数出字节数，&str 层拒绝返回 -1 */
    char bad[3] = {(char)0xFF, (char)0xFE, '\0'};
    int bb = ex02_bytes_len(bad);
    int bc = ex02_utf8_chars(bad);
    printf("bad-utf8: bytes=%d chars=%d\n", bb, bc);
    if (!(bb == 2 && bc == -1)) fail = 1;

    printf(fail ? "FAIL\n" : "ALL OK\n");
    return fail;
}
