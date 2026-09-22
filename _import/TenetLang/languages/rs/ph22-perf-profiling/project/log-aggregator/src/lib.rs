//! log-aggregator 库：日志解析 + 两种聚合器 + 报告 + 计数分配器。
//!
//! 模块划分见 Cargo.toml 头注释。本 crate 同时是 criterion 基准（benches/）
//! 与 measure 命令行（src/bin/measure.rs）的被测对象。

pub mod agg;
pub mod counting;
pub mod line;
pub mod report;

pub use agg::{BaselineAgg, OptimizedAgg};
pub use line::{parse_line, sample_lines, LineError, LogLine};
pub use report::{Report, ServiceStat};
