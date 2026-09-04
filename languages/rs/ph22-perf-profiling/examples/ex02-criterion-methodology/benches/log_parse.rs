//! ex02：criterion 系统方法论基准 —— 借用 vs 复制解析路径，扫「行数 × 路径」二维。
//!
//! ## 相比 ph20 ex05 的升级点（方法论层面）
//!
//! 1. **benchmark_group + BenchmarkId**：一个 group 内按 `规模 × 路径` 展开 4 个
//!    测量点，criterion 报告共享同一张比较表（group 内两两对比的显著性检验）；
//! 2. **Throughput**：声明每次迭代的字节数，报告同时给「每次调用耗时」与
//!    「吞吐 MB/s」，让不同规模的结果可跨机器比较；
//! 3. **回归基线（命令层，README 演示）**：`--save-baseline v1` 存档当前实现，
//!    改代码后 `--baseline v1` 对比，criterion 输出 `change` 行（相对变化 + 显著性
//!    p 值）——这是把基准从「报告」升级为「回归检测」的最小闭环（CI 判红口径见 README）。
//!
//! ## 噪声控制
//!
//! [`config`] 把 warm-up / measurement / sample_size 调小便于本仓库快速跑完；
//! 正式做回归请放宽到默认（warm-up 3s / measurement 5s / sample_size 100）并连跑
//! 两次（首轮含预热）。所有测量落盘 `target/criterion/`，跨次可比。

use std::hint::black_box;
use std::time::Duration;

use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};

use ex02_criterion_methodology::{parse_borrowed, parse_owned, sample_lines};

/// 对全部行做借用解析并黑盒消费结果，返回处理行数（防编译器消除整段遍历）。
fn run_borrowed(lines: &[String]) -> usize {
    let mut n = 0usize;
    for line in lines {
        let p = parse_borrowed(line).expect("样例行必然合法");
        black_box((p.service, p.op));
        n += 1;
    }
    n
}

/// 对全部行做复制解析：每行 4 次 to_string 分配是测量的重点。
fn run_owned(lines: &[String]) -> usize {
    let mut n = 0usize;
    for line in lines {
        let p = parse_owned(line).expect("样例行必然合法");
        black_box((p.service.as_str(), p.op.as_str()));
        n += 1;
    }
    n
}

fn bench_log_parse(c: &mut Criterion) {
    let mut group = c.benchmark_group("log_parse_borrow_vs_owned");
    // 扫两个规模：看「复制代价」是否随数据量线性放大
    for &n in &[1_000usize, 10_000] {
        let lines = sample_lines(n);
        let total_bytes: usize = lines.iter().map(String::len).sum();
        group.throughput(Throughput::Bytes(total_bytes as u64));

        group.bench_with_input(
            BenchmarkId::new("borrowed", format!("{n}lines")),
            &lines,
            |b, ls| b.iter(|| black_box(run_borrowed(black_box(ls)))),
        );
        group.bench_with_input(
            BenchmarkId::new("owned", format!("{n}lines")),
            &lines,
            |b, ls| b.iter(|| black_box(run_owned(black_box(ls)))),
        );
    }
    group.finish();
}

/// 教学演示用的小采样配置（正式回归请放宽，见文件头注释）。
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
    targets = bench_log_parse
}
criterion_main!(benches);
