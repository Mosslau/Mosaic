// examples/log-workspace/crates/log-aggregator/src/lib.rs —— 库：依赖 log-parser 做聚合
// 来源：languages/rs/ph06-cargo-module/06-cargo-module.md 第 6 章示例 5
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库，path 依赖 log-parser
// 编译：cargo build --workspace（在 examples/log-workspace/ 目录内执行）
// 测试：cargo test -p log-aggregator
// 验证状态：已验证（rustc 1.92.0）

use log_parser::LogLine;
use std::collections::BTreeMap;

pub fn count_by_level(lines: &[LogLine]) -> BTreeMap<String, usize> {
    let mut counts = BTreeMap::new();
    for line in lines {
        *counts.entry(line.level.clone()).or_insert(0) += 1;
    }
    counts
}

#[cfg(test)]
mod tests {
    use super::*;
    use log_parser::LogLine;

    fn line(level: &str) -> LogLine {
        LogLine { ts: 0, level: level.to_string(), message: "m".to_string() }
    }

    #[test]
    fn counts_sorted_by_level() {
        let lines = vec![line("ERROR"), line("INFO"), line("ERROR")];
        let counts = count_by_level(&lines);
        // BTreeMap 按键排序：ERROR < INFO
        let levels: Vec<_> = counts.into_iter().collect();
        assert_eq!(levels, vec![("ERROR".to_string(), 2), ("INFO".to_string(), 1)]);
    }
}
