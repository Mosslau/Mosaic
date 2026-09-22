// project/src/main.rs —— ph12 阶段项目：异步采集器（std 版）
// 需求：并发拉取多个数据源状态，超时重试并汇总结果（roadmap ph12 推荐项目）。
// 设计：每个数据源一个采集线程（线程 = 并发的执行体），经 mpsc 通道把结果发回
//       主线程；主线程带**全局超时**收集（recv_timeout 按剩余时限递减），每个源
//       内部做**最多 retries 次重试**；最后汇总为 成功 / 重试耗尽失败 / 超时未返回。
// 诚实标注：真实网络 I/O（TCP/HTTP）的系统化编程属于 ph13 文件、网络与系统编程
//           阶段；本项目的「数据源」用延迟 + 故障注入模拟，骨架（并发 + 超时 +
//           重试 + 汇总）与真实采集器一致。tokio 异步网络版见 examples/tokio/ex09。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings src/main.rs -o /tmp/proj
// 运行：/tmp/proj
// 测试：rustc --edition 2021 -D warnings --test src/main.rs -o /tmp/proj_test && /tmp/proj_test
// 验证状态：已验证（编译零警告；6 个单元测试全部通过；运行输出为实测）

use std::collections::HashSet;
use std::sync::mpsc::{self, RecvTimeoutError};
use std::thread;
use std::time::{Duration, Instant};

// ===== 数据源定义 =====
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct Source {
    name: &'static str,
    latency_ms: u64, // 一次「网络请求」的延迟（模拟）
    fail_until: u32, // 前 fail_until 次探测都失败（模拟故障注入；0 = 永不失败）
}

// ===== 单次采集（模拟请求）：延迟 + 可能失败 =====
fn fetch(source: &Source, attempt: u32) -> Result<String, String> {
    thread::sleep(Duration::from_millis(source.latency_ms)); // 模拟网络往返
    if attempt <= source.fail_until {
        Err(format!("连接失败（第 {attempt} 次探测）"))
    } else {
        Ok(format!("{} 状态正常", source.name))
    }
}

// ===== 单个源的采集线程：最多 retries 次重试，结果经通道发回 =====
fn collect_one(source: &Source, retries: u32, tx: mpsc::Sender<(String, Result<String, String>)>) {
    let mut last_err = String::new();
    for attempt in 1..=retries {
        match fetch(source, attempt) {
            Ok(v) => {
                let _ = tx.send((source.name.to_string(), Ok(v))); // 主线程可能已放弃（超时），忽略 send 错误
                return;
            }
            Err(e) => last_err = e,
        }
    }
    let _ = tx.send((source.name.to_string(), Err(last_err))); // 重试耗尽：报失败
}

// ===== 汇总 =====
#[derive(Debug, PartialEq, Eq)]
struct CollectionReport {
    ok: Vec<(String, String)>,     // 成功：(源名, 状态文本)
    failed: Vec<(String, String)>, // 重试耗尽后失败：(源名, 错误)
    timed_out: Vec<String>,        // 全局超时仍未返回的源名
    elapsed: Duration,
}

fn summarize(
    all_names: &[&str],
    done: Vec<(String, Result<String, String>)>,
    elapsed: Duration,
) -> CollectionReport {
    let mut ok = Vec::new();
    let mut failed = Vec::new();
    for (name, res) in done {
        match res {
            Ok(v) => ok.push((name, v)),
            Err(e) => failed.push((name, e)),
        }
    }
    let reported: HashSet<&str> = ok
        .iter()
        .chain(failed.iter())
        .map(|(n, _)| n.as_str())
        .collect();
    let timed_out = all_names
        .iter()
        .filter(|n| !reported.contains(**n))
        .map(|s| s.to_string())
        .collect();
    CollectionReport { ok, failed, timed_out, elapsed }
}

// ===== 并发采集：所有源同时启动，主线程按全局时限收集 =====
fn run_collection(sources: &[Source], retries: u32, global_timeout: Duration) -> CollectionReport {
    let (tx, rx) = mpsc::channel();
    let mut handles = Vec::new();
    let start = Instant::now();

    for s in sources {
        let tx = tx.clone();
        let s = *s;
        handles.push(thread::spawn(move || collect_one(&s, retries, tx)));
    }
    drop(tx); // 主线程不再持有 Sender

    // 全局超时：每次 recv 只等「剩余时限」，到点整体放弃
    let deadline = start + global_timeout;
    let mut done = Vec::new();
    loop {
        let now = Instant::now();
        if now >= deadline {
            break; // 全局超时：未返回的源记入 timed_out
        }
        match rx.recv_timeout(deadline - now) {
            Ok(r) => done.push(r),
            Err(RecvTimeoutError::Timeout) => break,
            Err(RecvTimeoutError::Disconnected) => break, // 所有采集线程都发完了
        }
    }
    let elapsed = start.elapsed(); // 采集窗口耗时（超时判定时点），不含线程收尾
    for h in handles {
        let _ = h.join(); // 收尾：等线程退出（迟到的消息已被丢弃）
    }

    let names: Vec<&str> = sources.iter().map(|s| s.name).collect();
    summarize(&names, done, elapsed)
}

// ===== 报告打印 =====
fn print_report(report: &CollectionReport) {
    println!("== 异步采集器报告 ==");
    println!(
        "成功 {} 个 / 重试耗尽失败 {} 个 / 超时未返回 {} 个（总耗时 {:?}）",
        report.ok.len(),
        report.failed.len(),
        report.timed_out.len(),
        report.elapsed
    );
    for (name, v) in &report.ok {
        println!("  ✔ {name}: {v}");
    }
    for (name, e) in &report.failed {
        println!("  ✘ {name}: {e}（重试耗尽）");
    }
    for name in &report.timed_out {
        println!("  ⏱ {name}: 全局超时未返回");
    }
}

fn main() {
    // 5 个模拟数据源：延迟与故障各不相同（fail_until = 前 N 次探测失败）
    let sources = [
        Source { name: "db-primary", latency_ms: 120, fail_until: 2 },      // 重试 2 次后成功（360ms）
        Source { name: "cache-node", latency_ms: 60, fail_until: 0 },       // 一次成功（60ms）
        Source { name: "search", latency_ms: 200, fail_until: 1 },          // 重试 1 次后成功（400ms，超时限）
        Source { name: "metrics", latency_ms: 30, fail_until: 0 },          // 一次成功（30ms）
        Source { name: "legacy-billing", latency_ms: 150, fail_until: 99 }, // 一直失败（450ms，超时限）
    ];
    const RETRIES: u32 = 3;
    const GLOBAL_TIMEOUT: Duration = Duration::from_millis(380);

    let report = run_collection(&sources, RETRIES, GLOBAL_TIMEOUT);
    print_report(&report);
}

// ===== 单元测试（不含真实计时依赖：测试用 latency 0 / 宽松时限） =====
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fetch_ok_when_past_fail_until() {
        let s = Source { name: "x", latency_ms: 0, fail_until: 0 };
        assert_eq!(fetch(&s, 1).unwrap(), "x 状态正常");
    }

    #[test]
    fn fetch_fails_before_fail_until() {
        let s = Source { name: "x", latency_ms: 0, fail_until: 2 };
        assert_eq!(fetch(&s, 1).unwrap_err(), "连接失败（第 1 次探测）");
        assert_eq!(fetch(&s, 2).unwrap_err(), "连接失败（第 2 次探测）");
    }

    #[test]
    fn collect_one_succeeds_after_retries() {
        let s = Source { name: "retry-ok", latency_ms: 0, fail_until: 2 };
        let (tx, rx) = mpsc::channel();
        collect_one(&s, 3, tx); // 第 1、2 次失败，第 3 次成功
        let (name, res) = rx.recv_timeout(Duration::from_millis(500)).unwrap();
        assert_eq!(name, "retry-ok");
        assert_eq!(res.unwrap(), "retry-ok 状态正常");
    }

    #[test]
    fn collect_one_reports_failure_when_retries_exhausted() {
        let s = Source { name: "down", latency_ms: 0, fail_until: 99 };
        let (tx, rx) = mpsc::channel();
        collect_one(&s, 2, tx); // 2 次都失败
        let (name, res) = rx.recv_timeout(Duration::from_millis(500)).unwrap();
        assert_eq!(name, "down");
        assert_eq!(res.unwrap_err(), "连接失败（第 2 次探测）");
    }

    #[test]
    fn summarize_classifies_ok_failed_timed_out() {
        let names = ["a", "b", "c"];
        let done = vec![
            ("a".to_string(), Ok("a 状态正常".to_string())),
            ("b".to_string(), Err("连接失败（第 3 次探测）".to_string())),
        ];
        let r = summarize(&names, done, Duration::from_millis(10));
        assert_eq!(r.ok.len(), 1);
        assert_eq!(r.failed.len(), 1);
        assert_eq!(r.timed_out, vec!["c".to_string()]);
        assert_eq!(r.elapsed, Duration::from_millis(10));
    }

    #[test]
    fn run_collection_all_succeed_within_timeout() {
        let sources = [
            Source { name: "a", latency_ms: 0, fail_until: 0 },
            Source { name: "b", latency_ms: 0, fail_until: 0 },
            Source { name: "c", latency_ms: 0, fail_until: 0 },
        ];
        let r = run_collection(&sources, 2, Duration::from_secs(5));
        assert_eq!(r.ok.len(), 3);
        assert!(r.failed.is_empty());
        assert!(r.timed_out.is_empty());
    }
}
