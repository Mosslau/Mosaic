//! sol-03：criterion 基准 —— Vec / HashMap / BTreeMap 在相同负载下的对比。
//!
//! 每个规模一个 group，三种容器各自测量「批量插入 + 一半 key 查找」的总时间。
//! 通过 `Throughput::Elements(n)` 声明负载。教学采样调小便于快速跑完。
//!
//! ## 本机实测样例（cargo 1.92.0, macOS arm64, 教学采样配置）
//!
//! ```text
//! insert_and_lookup/vec_binary_search/10000   time: 847 µs    thrpt: 11.8 Melem/s
//! insert_and_lookup/btreemap/10000            time: 702 µs    thrpt: 14.3 Melem/s
//! insert_and_lookup/hashmap/10000             time: 268 µs    thrpt: 37.3 Melem/s
//! insert_and_lookup/vec_binary_search/100000  time: 9.88 ms   thrpt: 10.1 Melem/s
//! insert_and_lookup/btreemap/100000           time: 7.76 ms   thrpt: 12.9 Melem/s
//! insert_and_lookup/hashmap/100000            time: 3.15 ms   thrpt: 31.7 Melem/s
//! ```
//!
//! HashMap 快 BTreeMap ~2.5x、快 Vec+binary_search ~3x；Vec 排序插入的常数
//! 成本让它在「一次建表多次查询」里也不如 BTreeMap——教科书结论在数据上成立，
//! 但别忘了 HashMap 的常数来自散列，key 越复杂差距越小（主文档 3.6 讨论）。

use std::hint::black_box;
use std::time::Duration;

use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};
use sol_03_collections_compare::{op_btree, op_hashmap, op_vec, sample_pairs};

fn bench_collections(c: &mut Criterion) {
    let mut group = c.benchmark_group("insert_and_lookup");
    for &n in &[10_000usize, 100_000] {
        let pairs = sample_pairs(n);
        group.throughput(Throughput::Elements(n as u64));

        group.bench_with_input(BenchmarkId::new("vec_binary_search", n), &pairs, |b, ps| {
            b.iter(|| black_box(op_vec(black_box(ps))))
        });
        group.bench_with_input(BenchmarkId::new("btreemap", n), &pairs, |b, ps| {
            b.iter(|| black_box(op_btree(black_box(ps))))
        });
        group.bench_with_input(BenchmarkId::new("hashmap", n), &pairs, |b, ps| {
            b.iter(|| black_box(op_hashmap(black_box(ps))))
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
    targets = bench_collections
}
criterion_main!(benches);
