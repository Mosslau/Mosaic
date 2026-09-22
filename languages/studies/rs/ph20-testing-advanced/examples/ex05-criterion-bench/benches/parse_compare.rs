//! criterion 基准：同一 WAL 日志的两种解析路径对比。
//!
//! - `borrowed`：零拷贝路径——`records()` 逐条返回**借用输入**的切片，不分配；
//! - `owned`：复制路径——模拟真实引擎落地（ph25 MemTable 需要拥有 key/value），
//!   每条 record 把 key/value `to_vec()` 拷成拥有数据。
//!
//! 这两个实现是同一份解析逻辑的两端「使用姿势」，不是两份解析器：
//! 基准的目的不是证明「哪个解析器快」，而是量化**使用姿势带来的分配代价**——
//! 这正是 ph19「零拷贝 vs 复制」预告里「用 criterion 验证零拷贝真的更快」的落点。
//!
//! ## 噪声控制（对应主文档 3.6）
//!
//! [`config`] 里把 warm-up / measurement / sample_size 调小，便于本仓库教学演示
//! 快速跑完。**正式做回归对比请放宽到默认**（warm-up 3s、measurement 5s、sample_size 100），
//! 并连续跑两次（第一次有编译/预热噪声）。所有基准自动落盘到
//! `target/criterion/` 的 JSON + 可选 HTML 报告，跨次可对比。
//!
//! ## 回归阈值（对应主文档 3.6）
//!
//! criterion 默认只报告「相对上次的变化估计」，要让它**在 CI 上判红/判绿**用基线：
//! 优化前后各存一次基线，再显式对比（命令见 Cargo.toml 注释）。CI 里把对比输出
//! 的 `change` 超阈值视为失败即可——严格阈值判定通常配合 cargo-criterion 或后处理，
//! 本示例演示最小闭环：`--save-baseline` → 改代码 → `--baseline` 对比。

use std::hint::black_box;
use std::time::Duration;

use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};

use ex05_criterion_bench::{records, Op, WalError, WalWriter};

/// 构造一条 N 条 record、value 定长 vlen 的日志。
fn build_log(records: usize, vlen: usize) -> Vec<u8> {
    let mut w = WalWriter::new();
    let value = vec![b'v'; vlen];
    for seq in 0..records as u64 {
        let key = format!("key-{seq:05}");
        w.append(seq, Op::Put, key.as_bytes(), &value);
    }
    w.as_bytes().to_vec()
}

/// 路径 A：零拷贝借用。key/value 始终是借用的切片，全程零分配。
fn replay_borrowed(log: &[u8]) -> Result<usize, WalError> {
    let mut n = 0usize;
    for item in records(log) {
        let rec = item?;
        // 黑盒借用切片：防止编译器把「没用到的读取」优化掉
        let _ = black_box(rec.key);
        let _ = black_box(rec.value);
        n += 1;
    }
    Ok(n)
}

/// 路径 B：复制路径。每次把 key/value 拷成拥有数据（等价于落地前的那一次 to_vec）。
fn replay_owned(log: &[u8]) -> Result<usize, WalError> {
    let mut n = 0usize;
    for item in records(log) {
        let rec = item?;
        let owned_key = black_box(rec.key.to_vec()); // 复制：模拟拥有数据
        let owned_value = black_box(rec.value.to_vec());
        black_box((owned_key.len(), owned_value.len())); // 防优化：结果必须被“用掉”
        n += 1;
    }
    Ok(n)
}

fn bench_replay_paths(c: &mut Criterion) {
    let mut group = c.benchmark_group("replay_borrowed_vs_owned");
    // 记录量 × value 宽度：两个参数同时扫，观察「复制代价」随数据量放大
    for &(records, vlen) in &[(1_000usize, 16usize), (10_000, 256)] {
        let log = build_log(records, vlen);
        group.throughput(Throughput::Bytes(log.len() as u64));
        group.bench_with_input(
            BenchmarkId::new("borrowed_zero_copy", format!("{records}x{vlen}B")),
            &log,
            |b, log| b.iter(|| replay_borrowed(black_box(log)).expect("合法日志")),
        );
        group.bench_with_input(
            BenchmarkId::new("owned_with_copy", format!("{records}x{vlen}B")),
            &log,
            |b, log| b.iter(|| replay_owned(black_box(log)).expect("合法日志")),
        );
    }
    group.finish();
}

/// 噪声控制：教学演示用的小采样配置（详见文件头注释）。
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
    targets = bench_replay_paths
}
criterion_main!(benches);
