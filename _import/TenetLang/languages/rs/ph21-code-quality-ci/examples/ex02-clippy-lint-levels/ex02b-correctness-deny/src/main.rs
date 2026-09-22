//! ex02b correctness 组：`eq_op`（自我比较）默认 deny，裸跑 cargo clippy 就直接 error。
//!
//! 文件头声明（教学性覆盖 + 运行前提）：本文件**故意包含一个真实 bug 模式**
//! （变量与自己比较），用于演示 correctness 组「不需要 -D warnings 就拦截」。
//! 只建议在解释 clippy 时运行：`cargo clippy --bin ex02b-correctness-deny`。
//!
//! 本机实测（cargo/clippy 1.92.0）：
//!   error: equal expressions as operands to `==`
//!   --> src/main.rs:行
//!    = note: `#[deny(clippy::eq_op)]` on by default
//! 注意：这是 clippy 的 deny；普通 `cargo build` / `cargo test` 不受影响。

/// 返回 crc 是否与期望一致。故意写成 expected == expected（应为 actual），
/// clippy 的 eq_op 会在编译期拦住这种「粘贴变量名时把自己跟自己比」的 typo。
fn crc_matches(expected: u32, _actual: u32) -> bool {
    expected == expected
}

fn main() {
    println!("{}", crc_matches(0x1234_5678, 0x9ABC_DEF0));
}
