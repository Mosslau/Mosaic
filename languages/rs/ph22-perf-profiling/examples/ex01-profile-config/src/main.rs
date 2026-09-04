//! ex01：同一 crate × 三种 [profile] 的「编译/运行/体积」对比主程序。
//!
//! 用法：先分别构建三个档，再运行各档二进制（路径区分档位）：
//! `target/release/ex01-profile-config [迭代次数] [标签]`。
//! 程序打印迭代次数、总耗时与校验和 acc（三档算法相同，acc 应一致 =
//! 「跑的确实是同一份源码」的自检）；**编译时间与二进制大小由外部命令测**
//! （见 Cargo.toml 与 README 的对照脚本）。
//!
//! 为什么标签由命令行传入而不是编译期自报：cargo 只在 build script 环境暴露
//! `PROFILE`，且对继承式自定义 profile 它恒为 `release`/`debug`——拿不到
//! `release-lto` 这样的自定义档名（这是 cargo 的已知限制，示例如实绕开）。

use std::env;
use std::hint::black_box;
use std::time::Instant;

fn main() {
    // 默认 1 亿次跨 crate 调用（arm64 上约 0.1~0.2s/档 @5e7）；第一个参数覆盖
    let n: u64 = env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(100_000_000);
    // 标签只是打印用，真正区分档位的是「运行哪个 target/<profile>/ 下的二进制」
    let tag = env::args()
        .nth(2)
        .unwrap_or_else(|| "(未传标签)".to_owned());

    let start = Instant::now();
    let mut acc = 0u64;
    // black_box 每次喂入变化输入，防止编译器把整条循环折叠成常量
    for i in 0..n {
        acc ^= black_box(hotcore::mix(black_box(i)));
    }
    let elapsed_ms = start.elapsed().as_secs_f64() * 1e3;

    println!(
        "profile={tag:<18} iterations={n:<12} elapsed={elapsed_ms:>10.2} ms  acc=0x{acc:016x}"
    );
}
