/* ex01 的 C 侧消费者：main.c —— 同一个文件用「动态链接」与「静态链接」各编一次。
 *
 * 教学要点：本文件刻意【手工写 extern 声明】而不引入生成的头文件——与 ex05
 * （cbindgen 自动生成头文件）形成对照，演示「手工声明易漏/易错，生成器保同步」。
 *
 * 验证环境：Apple clang 21.0.0（macOS arm64）。
 * 编译/链接/运行命令（在 examples/ex01-export-c-function/ 下执行，假设已 cargo build --release）：
 *   # 1. 先构建 Rust 库（cdylib + staticlib 同时产出）
 *   export PATH="$HOME/.cargo/bin:$PATH"
 *   export CARGO_TARGET_DIR=/tmp/ph23-ex01-target
 *   cargo build --release
 *   # 2. 动态链接：需要 -lex01_export 与运行时 rpath
 *   clang -Wall -Wextra -O2 caller/main.c -o /tmp/ph23-ex01-main-dyn \
 *       -L/tmp/ph23-ex01-target/release -lex01_export \
 *       -Wl,-rpath,/tmp/ph23-ex01-target/release
 *   /tmp/ph23-ex01-main-dyn          # 期望 add(20,22)=42 mul(6,7)=42 impl=ex01-rust-cdylib
 *   # 3. 静态链接：直接把 .a 归档喂给 clang，无需运行时动态库
 *   clang -Wall -Wextra -O2 caller/main.c /tmp/ph23-ex01-target/release/libex01_export.a \
 *       -o /tmp/ph23-ex01-main-static
 *   /tmp/ph23-ex01-main-static       # 输出同上
 */
#include <stdio.h>
#include <string.h>

/* 手工声明的导出函数（与 Rust 侧 #[no_mangle] extern "C" 一一对应）。
 * 若 Rust 侧签名改动而这里漏改，链接期或运行期才会暴露——这正是 cbindgen 存在的理由。 */
extern int ex01_add(int a, int b);
extern int ex01_mul(int a, int b);
extern const char *ex01_impl_name(void);

int main(void) {
    int r = ex01_add(20, 22);
    int m = ex01_mul(6, 7);
    const char *name = ex01_impl_name();
    printf("add(20,22)=%d mul(6,7)=%d impl=%s (strlen=%zu)\n",
           r, m, name, strlen(name));
    /* 返回值用作自检：两个 42 才算成功，方便脚本断言 */
    return (r == 42 && m == 42 && strcmp(name, "ex01-rust-cdylib") == 0) ? 0 : 1;
}
