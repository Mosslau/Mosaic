//! 练习 4 参考实现：criterion 对比「优化前 vs 优化后」。
//!
//! 优化前 v1：把日志整体解析成**拥有数据**的快照（每条 record 的 key/value 各自
//! `to_vec()`），这是「解析完再慢慢用」的直觉写法——每条两次分配；
//! 优化后 v2：流式借用，record 只活在迭代器里、key/value 是借用的切片。
//!
//! 这条基准回答 ph19 主文档留给 ph20 的问题：**零拷贝真的比逐次复制快吗**、
//! 快多少、在什么数据量下差距显现。跑完看 `time`/`thrpt` 两列即可：
//! 同一尺寸下 v2 应显著快于 v1（尤其小 value 大 record 数场景）。
//!
//! ## 噪声控制
//!
//! `config()` 调小了 warm-up / measurement / sample_size（教学演示提速）。
//! 严谨结论请放宽回 criterion 默认（warm-up 3s、measurement 5s、sample_size 100），
//! 并保持机器空闲、连跑两次取第二次。
//!
//! ## 回归阈值（CI 判红/判绿）
//!
//! criterion 输出里 `change` 一行是相对基线的估计区间，`p` 是显著性；要自动判失败
//! 需要把 change 区间与阈值比较（criterion 未内置阈值参数，常见做法是解析输出或
//! 配合 cargo-criterion）。最小闭环见 Cargo.toml 注释的 `--save-baseline`/`--baseline`。

use std::hint::black_box;
use std::time::Duration;

use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};

use record_parser::{records, Op, WalError, WalWriter};

fn build_log(n: usize, vlen: usize) -> Vec<u8> {
    let mut w = WalWriter::new();
    let value = vec![b'x'; vlen];
    for seq in 0..n as u64 {
        w.append(seq, Op::Put, format!("key-{seq:05}").as_bytes(), &value);
    }
    w.as_bytes().to_vec()
}

/// v1（优化前）：整体快照 —— 每条 record 的 key/value 都拷成拥有数据。
fn v1_naive_snapshot(log: &[u8]) -> Result<usize, WalError> {
    let mut snapshot: Vec<(u64, Vec<u8>, Vec<u8>)> = Vec::new();
    for item in records(log) {
        let rec = item?;
        snapshot.push((rec.sequence, rec.key.to_vec(), rec.value.to_vec()));
    }
    // 让快照真正被“消费”，防止整个函数被优化掉
    Ok(black_box(snapshot.len()))
}

/// v2（优化后）：零拷贝借用 —— 流式迭代，不产生任何记录级分配。
fn v2_zero_copy_stream(log: &[u8]) -> Result<usize, WalError> {
    let mut n = 0usize;
    for item in records(log) {
        let rec = item?;
        black_box(rec.key);
        black_box(rec.value);
        n += 1;
    }
    Ok(n)
}

fn bench_v1_vs_v2(c: &mut Criterion) {
    let mut group = c.benchmark_group("snapshot_vs_stream");
    for &(n, vlen) in &[(1_000usize, 16usize), (5_000, 128), (20_000, 128)] {
        let log = build_log(n, vlen);
        group.throughput(Throughput::Bytes(log.len() as u64));
        group.bench_with_input(
            BenchmarkId::new("v1_naive_snapshot", format!("{n}x{vlen}B")),
            &log,
            |b, log| b.iter(|| v1_naive_snapshot(black_box(log)).expect("合法日志")),
        );
        group.bench_with_input(
            BenchmarkId::new("v2_zero_copy_stream", format!("{n}x{vlen}B")),
            &log,
            |b, log| b.iter(|| v2_zero_copy_stream(black_box(log)).expect("合法日志")),
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
    targets = bench_v1_vs_v2
}
criterion_main!(benches);
