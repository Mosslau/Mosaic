//! record-test-suite 基准：同一被测对象的两条使用路径对比（零拷贝 vs 快照）。
//! 参数扫描：record 数 × value 宽度。噪声控制调小采样便于本仓库演示跑完，
//! 正式结论放宽回 criterion 默认；基线对比命令见 Cargo.toml 注释。

use std::hint::black_box;
use std::time::Duration;

use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};

use record_test_suite::{records, Op, WalError, WalWriter};

fn build_log(n: usize, vlen: usize) -> Vec<u8> {
    let mut w = WalWriter::new();
    let value = vec![b'v'; vlen];
    for seq in 0..n as u64 {
        w.append(seq, Op::Put, format!("key-{seq:05}").as_bytes(), &value);
    }
    w.as_bytes().to_vec()
}

/// 路径 1（快照）：解析成拥有数据后使用——每次 key/value 各分配一次。
fn snapshot_parse(log: &[u8]) -> Result<usize, WalError> {
    let mut snap: Vec<(u64, Vec<u8>, Vec<u8>)> = Vec::with_capacity(log.len() / 64);
    for item in records(log) {
        let rec = item?;
        snap.push((rec.sequence, rec.key.to_vec(), rec.value.to_vec()));
    }
    Ok(black_box(snap.len()))
}

/// 路径 2（零拷贝借用）：记录活在迭代器里，key/value 是借用切片。
fn borrowed_parse(log: &[u8]) -> Result<usize, WalError> {
    let mut n = 0usize;
    for item in records(log) {
        let rec = item?;
        black_box(rec.key);
        black_box(rec.value);
        n += 1;
    }
    Ok(n)
}

fn bench_parse_paths(c: &mut Criterion) {
    let mut group = c.benchmark_group("parse_paths_snapshot_vs_borrowed");
    for &(n, vlen) in &[(1_000usize, 16usize), (5_000, 128), (20_000, 256)] {
        let log = build_log(n, vlen);
        group.throughput(Throughput::Bytes(log.len() as u64));
        group.bench_with_input(
            BenchmarkId::new("snapshot_owned", format!("{n}x{vlen}B")),
            &log,
            |b, log| b.iter(|| snapshot_parse(black_box(log)).expect("合法日志")),
        );
        group.bench_with_input(
            BenchmarkId::new("borrowed_zero_copy", format!("{n}x{vlen}B")),
            &log,
            |b, log| b.iter(|| borrowed_parse(black_box(log)).expect("合法日志")),
        );
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
    targets = bench_parse_paths
}
criterion_main!(benches);
