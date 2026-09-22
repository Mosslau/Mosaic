/* ex05 的 C 侧消费者：main.c —— include cbindgen 生成的 ex05_rust_lib.h，链接 Rust 静态库。
 *
 * 教学点：与 ex01 的「手工 extern 声明」对照——这里的声明全部来自生成的头文件，
 * Rust 侧签名一变、重新 cbindgen，C 侧编译器立刻在类型层暴露不一致。
 * 头文件里甚至带着 Rust 侧的 doc 注释（如 ex05_quadrant 的象限约定）。
 *
 * 验证环境：Apple clang 21.0.0（macOS arm64）。
 * 编译/链接/运行命令（在 examples/ex05-cbindgen-header/ 下执行，先装 cbindgen）：
 *   # 1. 安装 cbindgen（只需一次；本机验证版本 0.27.0）
 *   export PATH="$HOME/.cargo/bin:$PATH"
 *   cargo install cbindgen --version 0.27.0 --locked
 *   # 2. 构建 Rust 库（staticlib + cdylib）
 *   export CARGO_TARGET_DIR=/tmp/ph23-ex05-target
 *   cargo build --release --manifest-path rust_lib/Cargo.toml
 *   # 3. 生成头文件到 /tmp（cbindgen 需在 crate 目录内运行，--crate 用「包名」）
 *   cd rust_lib
 *   cbindgen --config cbindgen.toml --crate ex05-rust-lib \
 *       --output /tmp/ph23-ex05-target/ex05_rust_lib.h
 *   cd ..
 *   # 4. 编译 C 程序并链接 Rust 静态库
 *   clang -Wall -Wextra -O2 -I/tmp/ph23-ex05-target caller/main.c \
 *       /tmp/ph23-ex05-target/release/libex05_rust_lib.a -o /tmp/ph23-ex05-main
 *   # 5. 运行
 *   /tmp/ph23-ex05-main
 */
#include <stdio.h>

/* 唯一的一处 include：声明全部来自 cbindgen 生成的头文件 */
#include "ex05_rust_lib.h"

int main(void) {
    int fail = 0;
    Point2D a = {0.0, 0.0};
    Point2D b = {3.0, 4.0};

    double d = ex05_distance(a, b);
    printf("distance((0,0),(3,4)) = %.1f\n", d);
    if (d != 5.0) fail = 1;

    Quadrant q = ex05_quadrant(b);
    printf("quadrant((3,4)) = %d\n", (int)q);
    if (q != Q1) fail = 1;

    const char *tag = ex05_tag();
    printf("tag = %s\n", tag);
    if (!tag || tag[0] == '\0') fail = 1;

    printf(fail ? "FAIL\n" : "ALL OK\n");
    return fail;
}
