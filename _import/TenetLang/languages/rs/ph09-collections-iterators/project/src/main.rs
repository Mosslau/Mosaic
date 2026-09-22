// 来源：languages/rs/ph09-collections-iterators/project/ —— roadmap 推荐项目"日志数据聚合器"
// 说明：过滤异常记录并计算错误分布、延迟分布和来源统计。零第三方依赖，单文件，含单元测试。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 src/main.rs -o /tmp/proj
// 运行：/tmp/proj
// 测试：rustc --edition 2021 --test src/main.rs -o /tmp/proj_test && /tmp/proj_test
// 验证状态：已验证（编译零警告，12 个单元测试全部通过）

use std::collections::HashMap;

/// 一条日志：来源、级别、耗时（毫秒）
#[derive(Debug, PartialEq)]
struct LogEntry {
    source: String,
    level: String,
    latency_ms: u32,
}

/// 把日志文本解析成条目：逐行过滤（空行、`#` 注释、格式非法行都跳过），
/// 行格式：`<来源> <级别> <耗时毫秒>`，例如 `api ERROR 512`。
fn parse_log(text: &str) -> Vec<LogEntry> {
    text.lines()
        .map(str::trim)
        .filter(|line| !line.is_empty() && !line.starts_with('#'))
        .filter_map(parse_line)
        .collect()
}

/// 解析单行；格式非法返回 None（filter_map 直接跳过）。
fn parse_line(line: &str) -> Option<LogEntry> {
    let mut parts = line.split_whitespace();
    let source = parts.next()?;
    let level = parts.next()?;
    let latency = parts.next()?;
    if parts.next().is_some() {
        return None; // 多于三段视为格式非法
    }
    Some(LogEntry {
        source: source.to_string(),
        level: level.to_string(),
        latency_ms: latency.parse().ok()?,
    })
}

/// 异常判定：非 INFO 级别，或延迟超过 500ms。
fn is_abnormal(e: &LogEntry) -> bool {
    e.level != "INFO" || e.latency_ms > 500
}

/// 错误分布：按级别分组计数（entry API）。
fn error_distribution(logs: &[LogEntry]) -> HashMap<&str, u32> {
    let mut by_level: HashMap<&str, u32> = HashMap::new();
    for e in logs {
        *by_level.entry(e.level.as_str()).or_insert(0) += 1;
    }
    by_level
}

/// 延迟分档：<=100ms / 101ms-1s / >1s。
fn latency_bucket(ms: u32) -> &'static str {
    match ms {
        0..=100 => "<=100ms",
        101..=1000 => "101ms-1s",
        _ => ">1s",
    }
}

/// 延迟分布：map 把延迟映射到分档标签，再分组计数。
fn latency_distribution(logs: &[LogEntry]) -> HashMap<&'static str, u32> {
    let mut dist: HashMap<&'static str, u32> = HashMap::new();
    for e in logs {
        *dist.entry(latency_bucket(e.latency_ms)).or_insert(0) += 1;
    }
    dist
}

/// 来源统计：每个来源的异常条数与平均延迟（fold 聚合，累加器是 HashMap<&str, (条数, 总延迟)>）。
fn source_stats(logs: &[LogEntry]) -> HashMap<&str, (u32, u64)> {
    logs.iter().fold(HashMap::new(), |mut acc, e| {
        let stat = acc.entry(e.source.as_str()).or_insert((0, 0));
        stat.0 += 1;
        stat.1 += e.latency_ms as u64;
        acc
    })
}

/// 来源统计转排序报表：(来源, 条数, 平均延迟)，按条数降序。
fn sorted_report(stats: HashMap<&str, (u32, u64)>) -> Vec<(String, u32, f64)> {
    let mut rows: Vec<(String, u32, f64)> = stats
        .into_iter()
        .map(|(src, (cnt, total))| {
            (src.to_string(), cnt, total as f64 / cnt as f64)
        })
        .collect();
    rows.sort_by(|a, b| b.1.cmp(&a.1));
    rows
}

fn main() {
    let text = "\
# 模拟日志：来源 级别 耗时(ms)
api ERROR 512
db ERROR 3200
cache ERROR 88
api WARN 240
api INFO 12
db INFO 3
cache INFO 1
api INFO 1500
";

    // 解析 + 过滤异常：一条迭代器链完成"读入 → 解析 → 过滤"
    let abnormal: Vec<LogEntry> = parse_log(text)
        .into_iter()
        .filter(is_abnormal)
        .collect();
    println!("异常记录 {} 条", abnormal.len());

    // 错误分布（按级别）
    let by_level = error_distribution(&abnormal);
    let mut levels: Vec<(&str, u32)> = by_level.into_iter().collect();
    levels.sort_by(|a, b| b.1.cmp(&a.1));
    println!("错误分布: {levels:?}");

    // 延迟分布（按分档）
    let lat_dist = latency_distribution(&abnormal);
    let mut buckets: Vec<(&str, u32)> = lat_dist.into_iter().collect();
    buckets.sort_by(|a, b| b.1.cmp(&a.1));
    println!("延迟分布: {buckets:?}");

    // 来源统计（条数 + 平均延迟，按条数降序）
    println!("来源统计:");
    for (src, cnt, avg) in sorted_report(source_stats(&abnormal)) {
        println!("  {src}: 异常 {cnt} 条, 平均延迟 {avg:.1}ms");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_skips_comments_and_empty_lines() {
        let logs = parse_log("# comment\n\napi INFO 1\n");
        assert_eq!(logs.len(), 1);
        assert_eq!(logs[0].source, "api");
    }

    #[test]
    fn parse_skips_malformed_lines() {
        let logs = parse_log("api INFO\napi INFO 12 extra\napi WAT 12\napi INFO 100\n");
        // 三段不足（2 段）与多于三段（4 段）的行被跳过；
        // "api WAT 12" 的级别是合法字符串、耗时可解析，照常解析
        assert_eq!(logs.len(), 2);
        assert_eq!(logs[0].level, "WAT");
        assert_eq!(logs[1].latency_ms, 100);
    }

    #[test]
    fn parse_reads_all_fields() {
        let logs = parse_log("api ERROR 512\n");
        assert_eq!(logs[0].source, "api");
        assert_eq!(logs[0].level, "ERROR");
        assert_eq!(logs[0].latency_ms, 512);
    }

    #[test]
    fn info_within_500ms_is_normal() {
        let e = LogEntry { source: "api".into(), level: "INFO".into(), latency_ms: 12 };
        assert!(!is_abnormal(&e));
    }

    #[test]
    fn info_over_500ms_is_abnormal() {
        let e = LogEntry { source: "api".into(), level: "INFO".into(), latency_ms: 1500 };
        assert!(is_abnormal(&e));
    }

    #[test]
    fn non_info_is_abnormal_even_if_fast() {
        let e = LogEntry { source: "cache".into(), level: "ERROR".into(), latency_ms: 88 };
        assert!(is_abnormal(&e));
    }

    #[test]
    fn latency_bucket_boundaries() {
        assert_eq!(latency_bucket(0), "<=100ms");
        assert_eq!(latency_bucket(100), "<=100ms");
        assert_eq!(latency_bucket(101), "101ms-1s");
        assert_eq!(latency_bucket(1000), "101ms-1s");
        assert_eq!(latency_bucket(1001), ">1s");
    }

    #[test]
    fn error_distribution_counts_by_level() {
        let logs = parse_log("api ERROR 1\ndb ERROR 2\napi WARN 3\ncache INFO 4\n");
        let dist = error_distribution(&logs);
        assert_eq!(dist.get("ERROR"), Some(&2));
        assert_eq!(dist.get("WARN"), Some(&1));
        assert_eq!(dist.get("INFO"), Some(&1));
    }

    #[test]
    fn latency_distribution_buckets_entries() {
        let logs = parse_log("a ERROR 50\nb ERROR 500\nc ERROR 2000\n");
        let dist = latency_distribution(&logs);
        assert_eq!(dist.get("<=100ms"), Some(&1));
        assert_eq!(dist.get("101ms-1s"), Some(&1));
        assert_eq!(dist.get(">1s"), Some(&1));
    }

    #[test]
    fn source_stats_count_and_average() {
        let logs = parse_log("api ERROR 100\napi WARN 300\ndb ERROR 500\n");
        let stats = source_stats(&logs);
        let (cnt, total) = stats.get("api").copied().unwrap_or((0, 0));
        assert_eq!((cnt, total), (2, 400)); // 平均 200
        assert_eq!(stats.get("db").copied(), Some((1, 500)));
    }

    #[test]
    fn sorted_report_orders_by_count_desc() {
        let mut stats: HashMap<&str, (u32, u64)> = HashMap::new();
        stats.insert("api", (3, 600));
        stats.insert("db", (1, 3200));
        stats.insert("cache", (2, 88));
        let rows = sorted_report(stats);
        let counts: Vec<u32> = rows.iter().map(|r| r.1).collect();
        assert_eq!(counts, vec![3, 2, 1]);
    }

    #[test]
    fn empty_logs_yield_empty_reports() {
        let logs = parse_log("# nothing here\n\n");
        assert!(logs.is_empty());
        assert!(error_distribution(&logs).is_empty());
        assert!(latency_distribution(&logs).is_empty());
        assert!(source_stats(&logs).is_empty());
    }
}
