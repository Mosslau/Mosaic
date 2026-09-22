//! sol-02：减少临时 String 分配 —— naive `format!` vs 复用缓冲。
//!
//! 场景：把一批 `(key, value)` 对渲染成 `key=value` 的**报告行**（行数很大，
//! 但每行只短暂存在、随后丢弃/汇总）。两种策略：
//!
//! - naive：每行 `format!("{key}={value}")` 新建 String，随即消费丢弃；
//! - reuse：一个 `String` 缓冲反复 `clear()` + `write!` 复用容量。
//!
//! 用全局计数分配器夹住两段测量窗口，输出各自的分配次数/字节与耗时。
//! 观察点：分配次数差了几个数量级、时间差却温和——分配的真实代价在
//! 多线程 allocator 争用与内存碎片上，单线程小分配几乎测不出来；
//! 这是「为什么要把分配次数当一等测量指标」的理由（主文档 3.5）。

mod counting;

use std::fmt::Write;
use std::hint::black_box;
use std::time::Instant;

use counting::{reset, snapshot};

/// naive：每行新建 String。
fn render_naive(n: usize) -> usize {
    let mut sink = 0usize;
    for i in 0..n {
        let line = format!("metric_{i}={i}");
        sink = sink.wrapping_add(black_box(line.len()));
    }
    sink
}

/// reuse：复用缓冲，容量够时零分配。
fn render_reuse(n: usize) -> usize {
    let mut sink = 0usize;
    let mut buf = String::with_capacity(32);
    for i in 0..n {
        buf.clear();
        let _ = write!(buf, "metric_{i}={i}");
        sink = sink.wrapping_add(black_box(buf.len()));
    }
    sink
}

fn main() {
    let n: usize = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(500_000);
    println!("== sol-02 减少临时 String 分配 ({n} 行) ==\n");

    reset();
    let t0 = Instant::now();
    let s_naive = render_naive(n);
    let dt_naive = t0.elapsed();
    let (n_naive, b_naive) = snapshot();

    reset();
    let t0 = Instant::now();
    let s_reuse = render_reuse(n);
    let dt_reuse = t0.elapsed();
    let (n_reuse, b_reuse) = snapshot();

    let ms = |d: std::time::Duration| d.as_secs_f64() * 1e3;
    println!(
        "naive format!:  分配 {n_naive:>8} 次 / {b_naive:>10} B   耗时 {:>8.2} ms  sink={s_naive}",
        ms(dt_naive)
    );
    println!(
        "复用 clear+write:分配 {n_reuse:>8} 次 / {b_reuse:>10} B   耗时 {:>8.2} ms  sink={s_reuse}",
        ms(dt_reuse)
    );
    if n_reuse < n_naive {
        println!(
            "\n分配次数下降 {:.0}x；时间仅 {:.1}x —— 单线程小分配在时间上近乎免费，",
            n_naive as f64 / n_reuse.max(1) as f64,
            dt_naive.as_secs_f64() / dt_reuse.as_secs_f64().max(1e-12)
        );
        println!("但分配器锁/缓存局部性在多线程与真实负载下会放大这一差距。");
    }
    assert_eq!(s_naive, s_reuse, "两种写法的输出语义必须一致");
    println!("\n语义校验: 两种写法 sink 一致（输出等长），优化未改变行为。");
}
