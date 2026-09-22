// examples/log-analyzer/src/service.rs —— 聚合服务层：对 Record 做统计（只依赖 model）
// 来源：languages/rs/ph06-cargo-module/06-cargo-module.md 第 6 章示例 1
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build（在 examples/log-analyzer/ 目录内执行）
// 运行：cargo run
// 测试：cargo test
// 验证状态：已验证（rustc 1.92.0）

use crate::model::Record;
use std::collections::HashMap;

pub fn aggregate(records: &[Record]) -> HashMap<String, usize> {
    let mut by_level = HashMap::new();
    for r in records {
        *by_level.entry(r.level.clone()).or_insert(0) += 1;
    }
    by_level
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::Record;

    fn record(ts: u64, level: &str) -> Record {
        Record { ts, level: level.to_string(), message: "m".to_string() }
    }

    #[test]
    fn aggregate_counts_by_level() {
        let records = vec![record(1, "INFO"), record(2, "INFO"), record(3, "ERROR")];
        let by_level = aggregate(&records);
        assert_eq!(by_level.get("INFO"), Some(&2));
        assert_eq!(by_level.get("ERROR"), Some(&1));
        assert_eq!(by_level.get("WARN"), None);
    }

    #[test]
    fn aggregate_empty_input() {
        assert!(aggregate(&[]).is_empty());
    }
}
