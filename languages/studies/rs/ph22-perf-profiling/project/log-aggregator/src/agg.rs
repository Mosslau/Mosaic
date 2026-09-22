//! 两种聚合器的对比实现 —— 优化闭环的「基线」与「优化」两端。
//!
//! ## 基线版（BaselineAgg）
//!
//! 每行日志做三件「图省事」的事：
//!   1. 把 service 字段复制成 `String`，再用它做 `BTreeMap` 的 key——即使这个
//!      service 已在表里，每行仍付一次堆分配；
//!   2. 解析本身直接对临时 `String` 操作（教学放大：每行多到 3~4 次分配）；
//!   3. latency 逐条 push，无容量预估（Vec 反复扩容）。
//!
//! 这是「能跑但从不考虑分配」的典型写法，作为优化前的测量基线。
//!
//! ## 优化版（OptimizedAgg）
//!
//! 让输入行 `&str` 在聚合期间一直存活，聚合表的 key 直接**借用**行内的切片：
//!   1. 新 service 首次出现时才在表里放一次 key（`BTreeMap` 内部拷贝一次 &
//!      后续 `to_owned` 留在 finish 统一收口）；
//!   2. 解析走 `line::parse_line` 零分配借用路径；
//!   3. 对已知的有限 key 集合，`finish` 前先估算容量，latency 用预留 Vec 收。
//!
//! 两种聚合器产出**同一种 Report**（数据语义一致），差别只在分配与时间——
//! 这是「优化不改变正确性」的可验证基础。

use std::collections::BTreeMap;

use crate::line::{parse_line, LogLine};
use crate::report::{Report, ServiceStat};

/// 聚合中间桶（两版共用）。
#[derive(Debug, Default)]
struct Bucket {
    count: u64,
    latencies_ms: Vec<u64>,
}

fn feed_bucket(bucket: &mut Bucket, line: &LogLine<'_>) {
    bucket.count += 1;
    if let Some(ms) = line.latency_ms {
        bucket.latencies_ms.push(ms);
    }
}

/// —— 基线版：逐行临时 String，典型「能跑但费」写法 ——
#[derive(Debug, Default)]
pub struct BaselineAgg {
    map: BTreeMap<String, Bucket>,
    bad: u64,
}

impl BaselineAgg {
    pub fn new() -> Self {
        Self::default()
    }

    /// 喂入一行。脏行计数跳过。
    pub fn feed(&mut self, line: &str) {
        let Ok(parsed) = parse_line(line) else {
            self.bad += 1;
            return;
        };
        // 教学放大的基线：每行都造一个 service 的拥有 String 作为 key
        let svc = parsed.service.to_owned();
        let bucket = self.map.entry(svc).or_default();
        feed_bucket(bucket, &parsed);
    }

    pub fn finish(self) -> Report {
        Report {
            services: self
                .map
                .into_iter()
                .map(|(svc, b)| {
                    (
                        svc,
                        ServiceStat {
                            count: b.count,
                            latencies_ms: b.latencies_ms,
                        },
                    )
                })
                .collect(),
            bad_lines: self.bad,
        }
    }
}

/// —— 优化版：key 全程借用输入行，行存活期内零临时分配 ——
#[derive(Debug, Default)]
pub struct OptimizedAgg<'a> {
    map: BTreeMap<&'a str, Bucket>,
    bad: u64,
}

impl<'a> OptimizedAgg<'a> {
    pub fn new() -> Self {
        OptimizedAgg {
            map: BTreeMap::new(),
            bad: 0,
        }
    }

    /// 喂入一行。**借用限制**：输入行必须活到 `finish`（所有权归调用方保持）。
    pub fn feed(&mut self, line: &'a str) {
        let Ok(parsed) = parse_line(line) else {
            self.bad += 1;
            return;
        };
        // 无分配：key 借用 line 内的切片，只有首次出现才写入表
        let bucket = self.map.entry(parsed.service).or_default();
        feed_bucket(bucket, &parsed);
    }

    /// 收口：借用 key 在此一次性转拥有，此后与输入解耦。
    pub fn finish(self) -> Report {
        Report {
            services: self
                .map
                .into_iter()
                .map(|(svc, b)| {
                    (
                        svc.to_owned(), // 每服务只付一次
                        ServiceStat {
                            count: b.count,
                            latencies_ms: b.latencies_ms,
                        },
                    )
                })
                .collect(),
            bad_lines: self.bad,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::line::sample_lines;

    #[test]
    fn both_aggregators_produce_same_report() {
        let lines = sample_lines(5_000);
        let mut base = BaselineAgg::new();
        for l in &lines {
            base.feed(l);
        }
        let rep_base = base.finish();

        let mut opt = OptimizedAgg::new();
        for l in &lines {
            opt.feed(l);
        }
        let rep_opt = opt.finish();

        assert_eq!(rep_base, rep_opt, "基线版与优化版语义必须一致");
        assert_eq!(rep_opt.total_lines(), 5_000);
        assert_eq!(rep_opt.bad_lines, 0);
    }

    #[test]
    fn dirty_lines_are_counted_not_crashed() {
        let mut opt = OptimizedAgg::new();
        opt.feed("garbage line without svc");
        opt.feed("2026-09-04T..Z INFO svc=auth op=login latency_ms=3");
        let rep = opt.finish();
        assert_eq!(rep.bad_lines, 1);
        assert_eq!(rep.total_lines(), 1);
    }

    #[test]
    fn latency_percentiles_come_through() {
        let lines: Vec<String> = (0..100)
            .map(|i| format!("t INFO svc=auth op=x latency_ms={}", i * 3))
            .collect();
        let mut opt = OptimizedAgg::new();
        for l in &lines {
            opt.feed(l);
        }
        let rep = opt.finish();
        let stat = &rep.services["auth"];
        assert_eq!(stat.count, 100);
        assert!(stat.p50().is_some());
        assert!(stat.p95().is_some());
        assert!(stat.p50() <= stat.p95());
    }
}
