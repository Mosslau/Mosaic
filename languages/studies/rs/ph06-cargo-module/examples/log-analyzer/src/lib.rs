// examples/log-analyzer/src/lib.rs —— 模块树唯一入口：声明 model/parser/service 三个模块
// 来源：languages/rs/ph06-cargo-module/06-cargo-module.md 第 6 章示例 1
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build（在 examples/log-analyzer/ 目录内执行）
// 运行：cargo run
// 验证状态：已验证（rustc 1.92.0）

pub mod model;
pub mod parser;
pub mod service;
