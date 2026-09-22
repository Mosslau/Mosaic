//! ex03：分配热点定位 —— WAL 回放的两条路径在「分配计数 × 耗时」上的对照。
//!
//! 流程：构造 N 条 record 的日志 → 用全局计数分配器分别夹住两条回放路径 →
//! 打印各自的 `(分配次数, 分配字节, 耗时)`。教学点：
//! 有些优化（borrow 代替 to_vec）在时间维度上差异小、在分配维度上差异巨大——
//! 分配次数往往是延迟尖峰（分配器锁、page fault）的先兆，是 ph22 的首要测量对象。

mod counting;
mod wal;

use std::env;
use std::hint::black_box;
use std::time::Instant;

use counting::{reset, snapshot};
use wal::{records, Op, WalWriter};

/// 构造 n 条、key 定长 klen、value 定长 vlen 的日志字节。
fn build_log(n: usize, klen: usize, vlen: usize) -> Vec<u8> {
    let mut w = WalWriter::new();
    let key: Vec<u8> = vec![b'k'; klen];
    let value: Vec<u8> = vec![b'v'; vlen];
    for seq in 0..n as u64 {
        w.append(seq, Op::Put, &key, &value);
    }
    w.as_bytes().to_vec()
}

/// Path A：零拷贝回放。record 全程借用日志缓冲，理论上零分配。
fn replay_borrowed(log: &[u8]) -> u64 {
    let mut sum = 0u64;
    for item in records(log) {
        let rec = item.expect("合法日志");
        sum = sum
            .wrapping_add(rec.sequence)
            .wrapping_add(black_box(rec.key.len()) as u64)
            .wrapping_add(black_box(rec.value.len()) as u64);
    }
    sum
}

/// Path B：回放 + 转 owned 收集（模拟引擎落地前要持有 key/value 建索引）。
fn replay_owned(log: &[u8]) -> u64 {
    let mut index: Vec<(Vec<u8>, Vec<u8>)> = Vec::new();
    for item in records(log) {
        let rec = item.expect("合法日志");
        // 两条 to_vec：每次都给 key/value 各分配一次堆内存
        index.push((black_box(rec.key.to_vec()), black_box(rec.value.to_vec())));
    }
    // 只保留长度信息（避免把整个 index 打印出去），结果必须"被用掉"
    black_box(index.len()) as u64
}

fn main() {
    let n: usize = env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(50_000);
    let (klen, vlen) = (16usize, 64usize);
    let log = build_log(n, klen, vlen);
    let log_bytes = log.len();
    println!("日志规模: {n} 条 record, {log_bytes} 字节 (key={klen}B value={vlen}B)\n");

    // Path A 测量窗口
    reset();
    let t0 = Instant::now();
    let sum_a = black_box(replay_borrowed(black_box(&log)));
    let dt_a = t0.elapsed();
    let (n_a, b_a) = snapshot();

    // Path B 测量窗口
    reset();
    let t0 = Instant::now();
    let sum_b = black_box(replay_owned(black_box(&log)));
    let dt_b = t0.elapsed();
    let (n_b, b_b) = snapshot();

    let ms = |d: std::time::Duration| d.as_secs_f64() * 1e3;
    println!(
        "Path A  零拷贝回放  : 分配 {n_a:>8} 次 / {b_a:>10} B  耗时 {:>10.2} ms  sum={sum_a}",
        ms(dt_a)
    );
    println!(
        "Path B  转 owned 收集: 分配 {n_b:>8} 次 / {b_b:>10} B  耗时 {:>10.2} ms  sum={sum_b}",
        ms(dt_b)
    );
    if b_a == 0 {
        println!(
            "Path A 全程零分配(借用的胜利); Path B 为收集 {n} 条 record 付出了 {b_b} B 堆分配,"
        );
        println!(
            "  平均每条 {:.1} 次分配(2 次 to_vec + Vec 扩容分摊)。",
            n_b as f64 / n as f64
        );
    }
    println!(
        "\n说明: 分配发生在 allocator 层, 与业务代码改动无关, 计数包含 Vec 扩容等一切堆分配。"
    );
}
