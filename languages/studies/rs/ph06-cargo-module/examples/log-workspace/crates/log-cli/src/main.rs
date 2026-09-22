// examples/log-workspace/crates/log-cli/src/main.rs —— 二进制入口：包名连字符在代码中写为下划线
// 来源：languages/rs/ph06-cargo-module/06-cargo-module.md 第 6 章示例 5
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库，path 依赖 log-parser / log-aggregator
// 编译：cargo build --workspace（在 examples/log-workspace/ 目录内执行）
// 运行：cargo run -p log-cli
// 验证状态：已验证（rustc 1.92.0）

use log_aggregator::count_by_level;
use log_parser::parse_all;

fn main() {
    let lines = parse_all("1700000000 INFO boot ok\n1700000002 ERROR disk full");
    println!("总行数: {}", lines.len());
    println!("按级别统计: {:?}", count_by_level(&lines));
}
