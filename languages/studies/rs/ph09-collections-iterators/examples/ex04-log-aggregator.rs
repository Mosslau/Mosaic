// 来源：languages/rs/ph09-collections-iterators/09-collections-iterators.md 第 6 章示例 4
// 说明：日志数据聚合器（roadmap 推荐项目的核心实现）——过滤异常、错误分布、延迟分档、来源统计
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 ex04-log-aggregator.rs -o /tmp/ex04
// 运行：/tmp/ex04
// 验证状态：已验证（编译零警告，输出符合预期）

use std::collections::HashMap;

// 一条日志：来源、级别、耗时（毫秒）
#[derive(Debug)]
struct LogEntry {
    source: &'static str,
    level: &'static str,
    latency_ms: u32,
}

fn main() {
    let logs = vec![
        LogEntry { source: "api", level: "ERROR", latency_ms: 512 },
        LogEntry { source: "db", level: "ERROR", latency_ms: 3200 },
        LogEntry { source: "cache", level: "ERROR", latency_ms: 88 },
        LogEntry { source: "api", level: "WARN", latency_ms: 240 },
        LogEntry { source: "api", level: "INFO", latency_ms: 12 },
        LogEntry { source: "db", level: "INFO", latency_ms: 3 },
        LogEntry { source: "cache", level: "INFO", latency_ms: 1 },
    ];

    // 1) 过滤异常记录：非 INFO 级别，或延迟超过 500ms
    // collect 目标是 Vec<&LogEntry>——零拷贝借用，filter 谓词收到 &&LogEntry
    let abnormal: Vec<&LogEntry> = logs
        .iter()
        .filter(|e| e.level != "INFO" || e.latency_ms > 500)
        .collect();
    println!("异常记录 {} 条", abnormal.len());

    // 2) 错误分布：按级别分组计数（entry API，一次哈希查找完成"取到可变引用"）
    let mut by_level: HashMap<&str, u32> = HashMap::new();
    for e in &abnormal {
        *by_level.entry(e.level).or_insert(0) += 1;
    }
    println!("错误分布: {by_level:?}");

    // 3) 延迟分布：map 把延迟映射到分档标签，再分组计数
    let mut lat_dist: HashMap<&str, u32> = HashMap::new();
    for b in abnormal.iter().map(|e| match e.latency_ms {
        ..=100 => "<=100ms",
        101..=1000 => "101ms-1s",
        _ => ">1s",
    }) {
        *lat_dist.entry(b).or_insert(0) += 1;
    }
    println!("延迟分布: {lat_dist:?}");

    // 4) 来源统计：fold 聚合每个来源的异常条数与平均延迟
    // 累加器是 HashMap<&str, (u32, u64)>——闭包修改 entry 后必须返回 acc
    let source_stats: HashMap<&str, (u32, u64)> = abnormal
        .iter()
        .fold(HashMap::new(), |mut acc, e| {
            let stat = acc.entry(e.source).or_insert((0, 0));
            stat.0 += 1;
            stat.1 += e.latency_ms as u64;
            acc
        });
    // 排序输出：HashMap -> 迭代器 -> Vec<(&str, u32, f64)>，按异常条数降序
    let mut rows: Vec<(&str, u32, f64)> = source_stats
        .into_iter()
        .map(|(src, (cnt, total))| (src, cnt, total as f64 / cnt as f64))
        .collect();
    rows.sort_by(|a, b| b.1.cmp(&a.1));
    for (src, cnt, avg) in rows {
        println!("{src}: 异常 {cnt} 条, 平均延迟 {avg:.1}ms");
    }
}
