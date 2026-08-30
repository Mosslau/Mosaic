// project/log-analyzer/crates/log-cli/src/main.rs —— CLI 层：命令行入口与输出（依赖 parser + aggregator）
// 来源：languages/rs/ph06-cargo-module/project/log-analyzer（阶段项目源码）
// 用法：cargo run -p log-cli [日志文件路径]；缺省读取样例 sample.log
// 错误路径优雅报错（eprintln + 退出码 1），不用裸 unwrap
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库，path 依赖 log-parser / log-aggregator
// 编译：cargo build --workspace（在 project/log-analyzer/ 目录内执行）
// 运行：cargo run -p log-cli [文件]
// 验证状态：已验证（rustc 1.92.0）

use log_aggregator::{count_by_level, count_by_source, error_rate, top_sources};
use log_parser::parse_all;

fn main() {
    let path = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "sample.log".to_string());
    let content = match std::fs::read_to_string(&path) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("读取 {} 失败: {}", path, e);
            std::process::exit(1);
        }
    };

    let lines = parse_all(&content);
    println!("总条数: {}", lines.len());

    let by_level = count_by_level(&lines);
    let level_str: Vec<String> = by_level
        .iter()
        .map(|(level, n)| format!("{}: {}", level, n))
        .collect();
    println!("按级别统计: {}", level_str.join(", "));

    let by_source = count_by_source(&lines);
    let source_str: Vec<String> = by_source
        .iter()
        .map(|(src, n)| format!("{}: {}", src, n))
        .collect();
    println!("按来源统计: {}", source_str.join(", "));

    if let Some(rate) = error_rate(&lines) {
        println!("Error 占比: {:.1}%", rate);
    }

    let top = top_sources(&lines, 3);
    let top_str: Vec<String> = top
        .iter()
        .map(|(src, n)| format!("{}: {}", src, n))
        .collect();
    println!("Top 来源: {}", top_str.join(", "));
}
