// examples/log-analyzer/src/model.rs —— 数据模型层：日志行解析成的结构化记录
// 来源：languages/rs/ph06-cargo-module/06-cargo-module.md 第 6 章示例 1
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build（在 examples/log-analyzer/ 目录内执行）
// 运行：cargo run
// 验证状态：已验证（rustc 1.92.0）

#[derive(Debug, Clone, PartialEq)]
pub struct Record {
    pub ts: u64,        // 时间戳（Unix 秒）
    pub level: String,  // INFO / WARN / ERROR
    pub message: String,
}
