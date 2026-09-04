//! 聚合报告与百分位统计。

use std::collections::BTreeMap;

/// 一个服务维度的统计桶。
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ServiceStat {
    /// 命中行数。
    pub count: u64,
    /// 收集到的 latency_ms 原始值。
    pub latencies_ms: Vec<u64>,
}

impl ServiceStat {
    /// 中位数延迟（毫秒）。无样本返回 None。
    pub fn p50(&self) -> Option<u64> {
        self.percentile(0.50)
    }

    /// P95 延迟（毫秒）。无样本返回 None。
    pub fn p95(&self) -> Option<u64> {
        self.percentile(0.95)
    }

    /// 线性插值百分位（nearest-rank）：排序后取 `ceil(p*n)` 位置。
    pub fn percentile(&self, p: f64) -> Option<u64> {
        if self.latencies_ms.is_empty() {
            return None;
        }
        let mut sorted = self.latencies_ms.clone();
        sorted.sort_unstable();
        let idx = ((p * sorted.len() as f64).ceil() as usize).clamp(1, sorted.len()) - 1;
        Some(sorted[idx])
    }
}

/// 一次聚合的最终报告（拥有数据，与输入行生命周期解耦）。
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Report {
    /// 按服务聚合。
    pub services: BTreeMap<String, ServiceStat>,
    /// 无法解析而被跳过的脏行数。
    pub bad_lines: u64,
}

impl Report {
    /// 总有效行数。
    pub fn total_lines(&self) -> u64 {
        self.services.values().map(|s| s.count).sum()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn stat(vals: &[u64]) -> ServiceStat {
        ServiceStat {
            count: vals.len() as u64,
            latencies_ms: vals.to_vec(),
        }
    }

    #[test]
    fn percentile_nearest_rank() {
        let s = stat(&[1, 2, 3, 4]);
        assert_eq!(s.p50(), Some(2)); // ceil(0.5*4)=2 → 第 2 个（1-based）
        assert_eq!(s.p95(), Some(4));
        assert_eq!(stat(&[]).p50(), None);
    }

    #[test]
    fn report_sums() {
        let mut r = Report::default();
        r.services.insert("kv".into(), stat(&[10, 20]));
        r.services.insert("auth".into(), stat(&[5]));
        assert_eq!(r.total_lines(), 3);
    }
}
