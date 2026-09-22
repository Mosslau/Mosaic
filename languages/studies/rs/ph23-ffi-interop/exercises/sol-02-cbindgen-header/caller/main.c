/* sol-02 的 C 侧验收程序：main.c —— include cbindgen 生成的头文件消费 Fraction。
 *
 * 验证环境：Apple clang 21.0.0（macOS arm64）。
 * 命令（在 sol-02-cbindgen-header/ 下执行）：
 *   export PATH="$HOME/.cargo/bin:$PATH"
 *   export CARGO_TARGET_DIR=/tmp/ph23-sol02-target
 *   cargo build --release
 *   cbindgen --config cbindgen.toml --crate sol02-cbindgen-header \
 *       --output /tmp/ph23-sol02-target/sol02_fraction.h
 *   clang -Wall -Wextra -O2 -I/tmp/ph23-sol02-target caller/main.c \
 *       /tmp/ph23-sol02-target/release/libsol02_fraction.a -o /tmp/ph23-sol02-main
 *   /tmp/ph23-sol02-main
 */
#include <stdio.h>

/* 声明全部来自生成的头文件——不用手工 extern */
#include "sol02_fraction.h"

int main(void) {
    int fail = 0;
    Fraction half = {1, 2};
    Fraction third = {1, 3};

    Fraction sum = fraction_add(half, third);
    printf("1/2 + 1/3 = %lld/%lld\n", sum.num, sum.den);
    if (sum.num != 5 || sum.den != 6) fail = 1;

    /* 分母为 0：业务约定返回 {0,0} */
    Fraction bad = fraction_add(half, (Fraction){1, 0});
    if (bad.num != 0 || bad.den != 0) {
        printf("FAIL zero-denominator case\n");
        fail = 1;
    }

    printf(fail ? "FAIL\n" : "ALL OK\n");
    return fail;
}
