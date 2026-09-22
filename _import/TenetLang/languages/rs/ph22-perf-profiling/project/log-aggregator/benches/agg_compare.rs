//! criterion 基准：基线聚合 vs 优化聚合（时间 + 吞吐）。
//!
//! 每组基准在「同一份输入」上跑：iter 内每次新建聚合器、喂完全部行、finish，
//! 黑盒消费结果防止死代码消除。通过 `Throughput::Elements` 声明行数，报告同时
//! 给出每次调用耗时与行/秒吞吐。教学配置调小采样便于快速跑完（正式回归放宽）。
//!
//! 回归检测用法（CI/脚本）：
//!   cargo bench -- --save-baseline v1     # 存档当前
//!   # ...修改实现后...
//!   cargo bench -- --baseline v1          # 输出 change 估计与显著性

use std::hint::black_box;
use std::time::Duration;

use criterion::{criterion_group, criterion_main, Criterion, Throughput};
use log_aggregator::agg::{BaselineAgg, OptimizedAgg};
use log_aggregator::line::sample_lines;

fn bench_aggregate(c: &mut Criterion) {
    let mut group = c.benchmark_group("aggregate");
    for &n in &[5_000usize, 50_000] {
        let lines = sample_lines(n);
        group.throughput(Throughput::Elements(n as u64));

        group.bench_function(format!("baseline_{n}lines"), |b| {
            b.iter(|| {
                let mut agg = BaselineAgg::new();
                for line in black_box(&lines) {
                    agg.feed(line);
                }
                black_box(agg.finish().total_lines())
            })
        });

        group.bench_function(format!("optimized_{n}lines"), |b| {
            b.iter(|| {
                let mut agg = OptimizedAgg::new();
                for line in black_box(&lines) {
                    agg.feed(line);
                }
                black_box(agg.finish().total_lines())
            })
        });
    }
    group.finish();
}

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
    targets = bench_aggregate
}
criterion_main!(benches);
