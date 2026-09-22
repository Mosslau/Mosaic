//! measure：日志聚合优化的「先测量」入口 —— 双版本时间 + p50/p95 + 分配次数对照。
//!
//! 用法：`measure [总行数，默认 200_000]`。批大小固定 2000 行/批，p50/p95 是
//! 「每批处理延迟」的分布（跨 ~100 批），能反映处理管线的稳定时延而不只是最好值。
//!
//! 输出三块：
//!   1. 每版「总耗时 / 分配次数 / 分配字节」；
//!   2. 每批处理延迟的 p50/p95（同一份输入、同一聚合语义）；
//!   3. 两版报告的语义一致性校验（相等即优化未破坏正确性）。

use std::time::{Duration, Instant};

use log_aggregator::agg::{BaselineAgg, OptimizedAgg};
use log_aggregator::counting::{reset, snapshot};
use log_aggregator::line::sample_lines;
use log_aggregator::Report;

/// 批大小：p50/p95 的统计单位（2000 行/批）。
const BATCH: usize = 2_000;

/// 就地排序后取 p 分位（毫秒）。
fn percentile_ms(times: &mut [Duration], p: f64) -> f64 {
    if times.is_empty() {
        return 0.0;
    }
    times.sort_unstable();
    let idx = ((p * times.len() as f64).ceil() as usize).clamp(1, times.len()) - 1;
    times[idx].as_secs_f64() * 1e3
}

/// 基线版全程测量：返回 (报告, 批延迟, (分配次数, 分配字节))。
/// 按批 feed 并记录每批耗时；分配计数 reset 一次包住全程。
fn measure_baseline(lines: &[String]) -> (Report, Vec<Duration>, (usize, usize)) {
    reset();
    let mut agg = BaselineAgg::new();
    let mut batch_times = Vec::with_capacity(lines.len() / BATCH + 1);
    for chunk in lines.chunks(BATCH) {
        let t0 = Instant::now();
        for line in chunk {
            agg.feed(line);
        }
        batch_times.push(t0.elapsed());
    }
    (agg.finish(), batch_times, snapshot())
}

/// 优化版全程测量：返回同构三元组。借用限制：lines 必须活过本函数全程。
fn measure_optimized(lines: &[String]) -> (Report, Vec<Duration>, (usize, usize)) {
    reset();
    let mut agg = OptimizedAgg::new();
    let mut batch_times = Vec::with_capacity(lines.len() / BATCH + 1);
    for chunk in lines.chunks(BATCH) {
        let t0 = Instant::now();
        for line in chunk {
            agg.feed(line);
        }
        batch_times.push(t0.elapsed());
    }
    (agg.finish(), batch_times, snapshot())
}

fn main() {
    let n: usize = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(200_000);
    println!("== log-aggregator measure ==");
    println!(
        "输入: {n} 行日志, 批大小 {BATCH} 行/批 ({} 批)\n",
        n / BATCH
    );

    let lines = sample_lines(n);

    let (rep_base, mut bt_base, alloc_base) = measure_baseline(&lines);
    let (rep_opt, mut bt_opt, alloc_opt) = measure_optimized(&lines);

    let (bn, bb) = alloc_base;
    let (on, ob) = alloc_opt;
    let b50 = percentile_ms(&mut bt_base, 0.50);
    let b95 = percentile_ms(&mut bt_base, 0.95);
    let o50 = percentile_ms(&mut bt_opt, 0.50);
    let o95 = percentile_ms(&mut bt_opt, 0.95);
    println!("┌──────────┬──────────────┬────────────┬────────────┬───────────┐");
    println!("│ 版本     │ 分配次数     │ 分配字节   │ p50(批 ms) │ p95(批 ms)│");
    println!("├──────────┼──────────────┼────────────┼────────────┼───────────┤");
    println!("│ 基线版   │ {bn:>12} │ {bb:>10} │ {b50:>10.3} │ {b95:>9.3} │");
    println!("│ 优化版   │ {on:>12} │ {ob:>10} │ {o50:>10.3} │ {o95:>9.3} │");
    println!("└──────────┴──────────────┴────────────┴────────────┴───────────┘");

    let times_x = bn as f64 / on.max(1) as f64;
    let p50_x = b50 / o50.max(1e-9);
    println!("\n分配次数下降: {times_x:.0}x   单批 p50 延迟下降: {p50_x:.1}x");

    assert_eq!(
        rep_base, rep_opt,
        "基线版与优化版报告必须一致 —— 优化不能改变语义"
    );
    println!(
        "语义校验: 两版报告完全一致 ({} 服务 / {} 行 / {} 脏行)",
        rep_opt.services.len(),
        rep_opt.total_lines(),
        rep_opt.bad_lines
    );
    println!("\n说明: 分配计数发生在全局分配器层, 包含 BTreeMap/延迟 Vec 的一切堆活动; 单批延迟越稳 p50/p95 越接近。");
}
