//! ex06-secret-handling —— secret 注入的最小形态（已验证）。
//!
//! 教学点：secret 不落代码/不落 Cargo.toml/不落日志；从环境变量读取，
//! 读不到就显式失败（而非用空值继续跑），用到但不回显内容。
//!
//! 运行：
//!   cargo run                        # 期望：报「缺少环境变量 CRATES_IO_TOKEN」
//!   CRATES_IO_TOKEN=dummy cargo run  # 期望：输出 token 长度，不回显内容

use std::env;

fn load_secret(name: &str) -> Result<String, String> {
    env::var(name).map_err(|_| format!("缺少环境变量 {name}：请注入，不要写进代码"))
}

fn main() -> Result<(), String> {
    let token = load_secret("CRATES_IO_TOKEN")?; // 读环境，读不到显式失败
    println!("token 已就绪（长度 {}，内容不回显）", token.len());
    Ok(())
}
