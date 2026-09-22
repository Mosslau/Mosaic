// exercises/sol-01-split-project/src/lib.rs —— 练习 1 参考实现：模块树唯一入口
// 拆分自 exercises/ex01-single-source.rs（行为一致），依赖方向 main -> service -> parser -> model
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build（在 sol-01-split-project/ 目录内执行）
// 运行：cargo run
// 测试：cargo test
// 验证状态：已验证（rustc 1.92.0）

pub mod model;
pub mod parser;
pub mod service;
