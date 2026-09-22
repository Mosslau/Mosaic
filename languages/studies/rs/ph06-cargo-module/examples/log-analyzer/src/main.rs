// examples/log-analyzer/src/main.rs —— 二进制 crate 入口：main -> service -> parser -> model 单向依赖
// 来源：languages/rs/ph06-cargo-module/06-cargo-module.md 第 6 章示例 1
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build（在 examples/log-analyzer/ 目录内执行）
// 运行：cargo run
// 测试：cargo test
// 验证状态：已验证（rustc 1.92.0）

use log_analyzer::{parser, service};

fn main() {
    let records = parser::parse_all("1700000000 INFO boot ok\n1700000001 WARN slow query");
    println!("总记录数: {}", records.len());
    println!("按级别统计: {:?}", service::aggregate(&records));
}
