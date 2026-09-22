// project/log-analyzer/crates/log-aggregator/src/lib.rs —— 聚合层：对 LogLine 做统计（依赖 log-parser）
// 来源：languages/rs/ph06-cargo-module/project/log-analyzer（阶段项目源码）
// 用 BTreeMap 保证输出有序；空输入用 Option 表达（ph04 Result/Option 基础）
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库，path 依赖 log-parser
// 编译：cargo build --workspace（在 project/log-analyzer/ 目录内执行）
// 测试：cargo test -p log-aggregator
// 验证状态：已验证（rustc 1.92.0）

use log_parser::LogLine;
use std::collections::BTreeMap;

/// 按级别统计条数（BTreeMap 按 Level 的 Ord 排序输出）
pub fn count_by_level(lines: &[LogLine]) -> BTreeMap<log_parser::Level, usize> {
    let mut counts = BTreeMap::new();
    for line in lines {
        *counts.entry(line.level).or_insert(0) += 1;
    }
    counts
}

/// 按来源统计条数（BTreeMap 按来源名排序输出）
pub fn count_by_source(lines: &[LogLine]) -> BTreeMap<String, usize> {
    let mut counts = BTreeMap::new();
    for line in lines {
        *counts.entry(line.source.clone()).or_insert(0) += 1;
    }
    counts
}

/// Error 级别占比（百分比），空输入返回 None
pub fn error_rate(lines: &[LogLine]) -> Option<f64> {
    if lines.is_empty() {
        return None;
    }
    let errors = lines
        .iter()
        .filter(|l| l.level == log_parser::Level::Error)
        .count();
    Some(errors as f64 / lines.len() as f64 * 100.0)
}

/// 日志最多的前 n 个来源（条数降序，条数相同按来源名升序）
pub fn top_sources(lines: &[LogLine], n: usize) -> Vec<(String, usize)> {
    let mut v: Vec<(String, usize)> = count_by_source(lines).into_iter().collect();
    v.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    v.into_iter().take(n).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use log_parser::{Level, LogLine};

    fn line(ts: u64, level: Level, source: &str) -> LogLine {
        LogLine {
            ts,
            level,
            source: source.to_string(),
            message: "m".to_string(),
        }
    }

    fn sample() -> Vec<LogLine> {
        vec![
            line(1, Level::Info, "api-server"),
            line(2, Level::Error, "api-server"),
            line(3, Level::Info, "worker-1"),
            line(4, Level::Error, "worker-1"),
            line(5, Level::Error, "db-layer"),
        ]
    }

    #[test]
    fn count_by_level_sorted_keys() {
        // 只含实际出现过的级别，键按 Ord 升序（Debug < Info < Warn < Error）
        let counts = count_by_level(&sample());
        let keys: Vec<Level> = counts.keys().copied().collect();
        assert_eq!(keys, vec![Level::Info, Level::Error]);
    }

    #[test]
    fn count_by_level_skips_zero() {
        // 说明：BTreeMap 只统计实际出现过的级别，未出现的级别不在 map 中
        let counts = count_by_level(&sample());
        assert_eq!(counts.get(&Level::Info), Some(&2));
        assert_eq!(counts.get(&Level::Error), Some(&3));
        assert_eq!(counts.get(&Level::Debug), None);
        assert_eq!(counts.get(&Level::Warn), None);
    }

    #[test]
    fn count_by_source_aggregates() {
        let counts = count_by_source(&sample());
        assert_eq!(counts.get("api-server"), Some(&2));
        assert_eq!(counts.get("worker-1"), Some(&2));
        assert_eq!(counts.get("db-layer"), Some(&1));
    }

    #[test]
    fn error_rate_computes_percent() {
        // 3 条 Error / 5 条 = 60%
        let rate = error_rate(&sample()).unwrap();
        assert!((rate - 60.0).abs() < 1e-9);
    }

    #[test]
    fn error_rate_no_errors_is_zero() {
        let lines = vec![line(1, Level::Info, "api-server")];
        assert_eq!(error_rate(&lines), Some(0.0));
    }

    #[test]
    fn error_rate_empty_is_none() {
        assert_eq!(error_rate(&[]), None);
    }

    #[test]
    fn top_sources_sorted_and_truncated() {
        let top = top_sources(&sample(), 2);
        assert_eq!(top.len(), 2);
        // 条数均为 2 的 api-server 与 worker-1 按名称升序，db-layer 被截断
        assert_eq!(top[0].0, "api-server");
        assert_eq!(top[1].0, "worker-1");
    }

    #[test]
    fn aggregate_empty_input() {
        assert!(count_by_level(&[]).is_empty());
        assert!(count_by_source(&[]).is_empty());
        assert!(top_sources(&[], 3).is_empty());
    }
}
