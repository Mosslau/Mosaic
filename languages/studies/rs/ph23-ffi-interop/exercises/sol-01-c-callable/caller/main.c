/* sol-01 的 C 侧验收程序：main.c —— 动态与静态两种链接方式各验一次。
 *
 * 验证环境：Apple clang 21.0.0（macOS arm64）。
 * 命令（在 sol-01-c-callable/ 下执行）：
 *   export PATH="$HOME/.cargo/bin:$PATH"
 *   export CARGO_TARGET_DIR=/tmp/ph23-sol01-target
 *   cargo build --release
 *   # 动态链接
 *   clang -Wall -Wextra -O2 caller/main.c -o /tmp/ph23-sol01-dyn \
 *       -L/tmp/ph23-sol01-target/release -lsol01_math \
 *       -Wl,-rpath,/tmp/ph23-sol01-target/release
 *   # 静态链接
 *   clang -Wall -Wextra -O2 caller/main.c /tmp/ph23-sol01-target/release/libsol01_math.a \
 *       -o /tmp/ph23-sol01-static
 *   /tmp/ph23-sol01-dyn && /tmp/ph23-sol01-static   # 两种都期望退出码 0
 */
#include <stdio.h>

extern long long gcd(long long a, long long b);
extern long long lcm(long long a, long long b);

int main(void) {
    int fail = 0;
    long long g = gcd(1071, 462);
    long long m = lcm(12, 18);
    long long z = lcm(0, 42);
    printf("gcd(1071,462)=%lld lcm(12,18)=%lld lcm(0,42)=%lld\n", g, m, z);
    if (g != 21) fail = 1;
    if (m != 36) fail = 1;
    if (z != 0) fail = 1;
    printf(fail ? "FAIL\n" : "ALL OK\n");
    return fail;
}
