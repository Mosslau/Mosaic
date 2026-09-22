//! sol-01：criterion 基准骨架 —— 两个规模 × 两条实现路径。
//!
//! 教学要点都写在注释里：
//! 1. `benchmark_group`：同组测量共享一张对比报告，criterion 给出两两显著性检验；
//! 2. `Throughput::Elements`：声明每轮处理的 key 数 → 报告多一行 elements/s，
//!    与机器无关、可跨机器比较；
//! 3. `black_box` 双端夹住：`iter(|| …black_box(input)… black_box(输出))`
//!    防止编译器把循环消除或把借用路径优化成复制路径；
//! 4. 两个规模：确认「复制代价」随规模线性放大（基准要有分辨力）。
//!
//! 改成自己的热点函数：替换 src/lib.rs 的函数与这里的 `run_*` 两个包装即可。
//!
//! ## 本机实测样例（cargo 1.92.0, macOS arm64, 教学采样配置）
//!
//! ```text
//! key_split_ref_vs_owned/borrowed_ref/10000    time: 72.4 µs   thrpt: 138 Melem/s
//! key_split_ref_vs_owned/owned_copy/10000      time: 680.6 µs  thrpt: 14.7 Melem/s
//! key_split_ref_vs_owned/borrowed_ref/100000   time: 771.9 µs  thrpt: 129.6 Melem/s
//! key_split_ref_vs_owned/owned_copy/100000     time: 6.55 ms   thrpt: 15.3 Melem/s
//! ```
//!
//! 借用路径稳定快 ~9x、吞吐 ~9x，且两个规模比例一致——分配代价是每 key 的
//! 常数项，随规模线性放大（主文档 3.6 的「先测量后下结论」样例）。

use std::hint::black_box;
use std::time::Duration;

use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};
use sol_01_hotspot_bench::{sample_keys, split_key_owned, split_key_ref};

/// 借用路径：每 key 拆字段并黑盒消费结果，返回成功处理数。
fn run_ref(keys: &[String]) -> usize {
    let mut total = 0usize;
    for k in keys {
        if let Some((p, id)) = split_key_ref(k) {
            let _ = black_box((p, id));
            total += 1;
        }
    }
    total
}

/// 复制路径：同样的工作量，但每次多一次/几次堆分配。
fn run_owned(keys: &[String]) -> usize {
    let mut total = 0usize;
    for k in keys {
        if let Some((p, id)) = black_box(split_key_owned(black_box(k))) {
            let _ = black_box((p, id));
            total += 1;
        }
    }
    total
}

fn bench_key_split(c: &mut Criterion) {
    let mut group = c.benchmark_group("key_split_ref_vs_owned");
    for &n in &[10_000usize, 100_000] {
        let keys = sample_keys(n);
        group.throughput(Throughput::Elements(n as u64));
        group.bench_with_input(BenchmarkId::new("borrowed_ref", n), &keys, |b, ks| {
            b.iter(|| black_box(run_ref(black_box(ks))))
        });
        group.bench_with_input(BenchmarkId::new("owned_copy", n), &keys, |b, ks| {
            b.iter(|| black_box(run_owned(black_box(ks))))
        });
    }
    group.finish();
}

/// 教学演示用小采样（正式回归请放宽到默认并连跑两次）。
fn config() -> Criterion {
    Criterion::default()
        .warm_up_time(Duration::from_millis(300))
        .measurement_time(Duration::from_secs(2))
        .sample_size(20)
        .confidence_level(0.95)
}

criterion_group! {
    name = benches;
    config = config();
    targets = bench_key_split
}
criterion_main!(benches);
