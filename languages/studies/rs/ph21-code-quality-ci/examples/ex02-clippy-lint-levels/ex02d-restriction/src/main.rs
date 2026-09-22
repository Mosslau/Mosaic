//! ex02d restriction 组：按团队纪律「逐条开」的禁令 lint 演示。
//!
//! 本机实测（cargo/clippy 1.92.0）：
//!   cargo clippy --bin ex02d-restriction                        → 退出 0，零输出（默认不开）
//!   cargo clippy --bin ex02d-restriction -- -W clippy::unwrap_used
//!       → warning: clippy::unwrap_used：used `unwrap()` on a `Result` value
//!   cargo clippy --bin ex02d-restriction -- -W clippy::indexing_slicing
//!       → warning: clippy::indexing_slicing：indexing may panic
//! 反模式演示（不推荐照抄）：整组 -W clippy::restriction 会喷出几十条禁令
//! （print_stdout/implicit_return/min_ident_chars/…）并额外警告 blanket_clippy_restriction_lints：
//! restriction 不是用来整组启用的（主文档 3.3）。

/// 解析用户输入为数字：unwrap 会让非法输入直接 panic（restriction 的 unwrap_used 拦它）。
/// 生产代码的治理方向是返回 Result + `?`（rust-patterns：生产代码无裸 unwrap）。
fn parse_port(s: &str) -> u16 {
    s.parse().unwrap()
}

/// 取首字节：裸下标对空切片直接 panic（restriction 的 indexing_slicing 拦它）。
/// 治理方向：v.first().copied() 或 get(0)。
fn first_byte(v: &[u8]) -> u8 {
    v[0]
}

fn main() {
    println!("{}", parse_port("8080"));
    println!("{}", first_byte(&[7, 8]));
}
