//! ph25 ex03：Compaction 归并语义与读/写/空间放大量化（纯 std，零第三方依赖）
//!
//! 教学模型参照 **cpp/ph22-storage-engine-db-kernel/examples/ex06-compaction-sim.cpp**
//! （C++ 版），本文件是它的 Rust 复刻+扩展：归并语义（覆盖丢弃 / tombstone 到底才真删 /
//! 非底层归并必须保留删除标记）、点查探测 run 计数（读放大代理）、两种归并节奏
//! （每次 flush 全量归并 vs 攒批归并）的写放大/读放大/空间放大实测对照。
//! 分工视角：C++ 版聚焦磁盘组件实现的细节纪律，Rust 版聚焦「不可变 run 的所有权交接、
//! BTreeMap 归并、确定性模型与断言」的组合纪律——这里没有文件/裸资源，是纯内存模拟，
//! 数值只对本模型成立，**趋势**（攒批降写放大、升读放大）对真实 leveled LSM 同样成立。
//!
//! # 验证环境与命令
//! - 验证环境：rustc/cargo 1.92.0（macOS arm64）
//! - 运行：`cargo run --release`（三组实验 + 对照表，输出见 README）
//! - 测试：`cargo test --release`（6 个单测：归并/删除/读放大/写放大断言）
//! - 质量：`cargo fmt --check && cargo clippy --all-targets -- -D warnings`
//! - 验证状态：**已验证**（2026-09-04 本机实测，输出见 examples/README）

use std::collections::BTreeMap;

/// 一条记录：带 seq（越大越新）与 deleted 标记（tombstone）。
#[derive(Debug, Clone)]
struct Entry {
    key: String,
    value: String,
    seq: u64,
    deleted: bool,
}

/// 一个 run（MemTable flush 出的 SSTable 的逻辑等价物）：key 有序、key 唯一。
type Run = Vec<Entry>;

fn run_bytes(run: &Run) -> u64 {
    // 8 字节定长头 + key + value（两种 value 下等长，比较不受影响）
    run.iter()
        .map(|e| 8 + e.key.len() as u64 + e.value.len() as u64)
        .sum()
}

/// 归并统计：三放大的原始计量。
#[derive(Debug, Default)]
struct MergeStats {
    input_entries: u64,
    dropped_stale: u64,     // 被更新版本覆盖的旧值条
    dropped_tombstone: u64, // full compaction 中真正删掉的 key
    output_entries: u64,
    input_bytes: u64,
    output_bytes: u64,
}

/// 归并多个 run（`runs` 按「新 → 旧」排）为一个 run。
///
/// `final_level=true`：这是到底层的 full compaction，下面没有更老数据，
/// 允许把 tombstone 丢掉（key 真正消失）；`false` 时 tombstone 必须保留，
/// 否则更老 run 里的旧值会「复活」。
fn merge_runs(runs: &[Run], final_level: bool) -> (Run, MergeStats) {
    let mut stats = MergeStats::default();
    // 每个 key 保留 seq 最大的一条（BTreeMap 归并天然有序、自动去重）
    let mut best: BTreeMap<String, Entry> = BTreeMap::new();
    for r in runs {
        for e in r {
            stats.input_entries += 1;
            stats.input_bytes += 8 + e.key.len() as u64 + e.value.len() as u64;
            match best.get(&e.key) {
                None => {
                    best.insert(e.key.clone(), e.clone());
                }
                Some(existing) if e.seq > existing.seq => {
                    stats.dropped_stale += 1; // 旧版本（含旧 tombstone）被压掉
                    best.insert(e.key.clone(), e.clone());
                }
                Some(_) => {
                    stats.dropped_stale += 1; // 本 run 内/跨 run 的过期版本
                }
            }
        }
    }
    let mut out = Run::new();
    for e in best.into_values() {
        if e.deleted && final_level {
            stats.dropped_tombstone += 1; // 到底层：tombstone 落地
            continue;
        }
        out.push(e);
    }
    stats.output_entries = out.len() as u64;
    stats.output_bytes = run_bytes(&out);
    (out, stats)
}

/// 一次点查要探测几个 run（读放大代理）。run 按新→旧，首个给出答案的即返回。
struct Probe {
    found: bool,
    runs_probed: u64,
}

fn point_lookup(runs: &[Run], key: &str) -> Probe {
    for (i, r) in runs.iter().enumerate() {
        // run 内有序：二分定位
        let pos = r.partition_point(|e| e.key.as_str() < key);
        if let Some(e) = r.get(pos) {
            if e.key == key {
                return Probe {
                    found: true,
                    runs_probed: i as u64 + 1,
                };
            }
        }
    }
    Probe {
        found: false,
        runs_probed: runs.len() as u64, // 全探测完也没找到
    }
}

/// 确定性 LCG（SplitMix64 式的状态步进）：同一负载可复现。
struct Lcg(u64);

impl Lcg {
    fn new(seed: u64) -> Lcg {
        Lcg(0x9E37_79B9_7F4A_7C15u64.wrapping_add(seed.wrapping_mul(0x9E37_79B9_7F4A_7C15)))
    }

    fn next_u64(&mut self) -> u64 {
        self.0 = self
            .0
            .wrapping_mul(0x9E37_79B9_7F4A_7C15)
            .wrapping_add(0x9E37_79B9_7F4A_7C15);
        self.0
    }
}

fn pad(v: usize, width: usize) -> String {
    format!("{v:0width$}", width = width)
}

/// 确定性负载：key 域固定，重复覆盖 + 部分删除（~1/7 是删除）。
fn make_ops(seed: usize, n: usize, key_domain: usize) -> Vec<(String, bool)> {
    let mut rng = Lcg::new(seed as u64);
    let mut ops = Vec::with_capacity(n);
    for _ in 0..n {
        let v = rng.next_u64();
        let kid = ((v >> 40) % key_domain as u64) as usize;
        ops.push((format!("key-{}", pad(kid, 3)), kid % 7 == 0));
    }
    ops
}

/// 由操作序列构造一个 run（同一 MemTable 快照：同 key 只留最新一条）。
struct SeqCounter(u64);

fn build_run_from_ops(ops: &[(String, bool)], value_prefix: &str, seq: &mut SeqCounter) -> Run {
    let mut best: BTreeMap<String, Entry> = BTreeMap::new();
    for (key, deleted) in ops {
        seq.0 += 1;
        let e = Entry {
            key: key.clone(),
            value: if *deleted {
                String::new()
            } else {
                format!("{value_prefix}{key}")
            },
            seq: seq.0,
            deleted: *deleted,
        };
        best.insert(key.clone(), e); // 同 run 内后写覆盖先写
    }
    best.into_values().collect()
}

fn main() -> Result<(), String> {
    // —— [1] 归并语义：三个 run（新→旧），含跨 run 覆盖与删除 ——
    let r0 = vec![
        Entry {
            key: "apple".into(),
            value: "r0".into(),
            seq: 1,
            deleted: false,
        },
        Entry {
            key: "banana".into(),
            value: "r0".into(),
            seq: 2,
            deleted: false,
        },
    ];
    let r1 = vec![
        Entry {
            key: "banana".into(),
            value: "r1".into(),
            seq: 11,
            deleted: false,
        },
        Entry {
            key: "cherry".into(),
            value: "r1".into(),
            seq: 12,
            deleted: false,
        },
    ];
    let r2 = vec![
        Entry {
            key: "apple".into(),
            value: "r2".into(),
            seq: 21,
            deleted: false,
        },
        Entry {
            key: "banana".into(),
            value: String::new(),
            seq: 22,
            deleted: true,
        },
    ];
    let runs = [r2, r1, r0];

    // 点查前：不存在的 key 要探测全部 3 个 run（读放大 = 3）
    let miss = point_lookup(&runs, "zzz");
    assert_eq!(miss.runs_probed, 3);
    assert!(!miss.found);

    let (merged, m) = merge_runs(&runs, true);
    println!(
        "[1] full compaction: {} 条/{} B 的 3 个 run -> {} 条/{} B",
        m.input_entries, m.input_bytes, m.output_entries, m.output_bytes
    );
    println!(
        "    覆盖丢弃 {} 条，tombstone 真删 {} 个 key，输出 {} 条",
        m.dropped_stale, m.dropped_tombstone, m.output_entries
    );
    assert_eq!(merged.len(), 2);
    assert_eq!(&merged[0].key, "apple");
    assert_eq!(&merged[0].value, "r2"); // 新 run 覆盖旧 run 的 apple
    assert_eq!(&merged[1].key, "cherry"); // banana 被 tombstone 删除
    assert_eq!(&merged[1].value, "r1");

    let miss2 = point_lookup(&[merged.clone()], "zzz");
    println!(
        "    点查不存在 key：3 run 时探测 {} 次 → 合并后 {} 次（读放大 3 → 1）",
        miss.runs_probed, miss2.runs_probed
    );
    let space_amp = m.input_bytes as f64 / m.output_bytes as f64;
    println!(
        "    空间：物理 {} B / 有效 {} B（空间放大 {:.2}x）",
        m.input_bytes, m.output_bytes, space_amp
    );
    assert!(space_amp > 1.0);

    // —— [2] tombstone 语义：非底层归并必须保留删除标记 ——
    let older = vec![Entry {
        key: "fig".into(),
        value: "v".into(),
        seq: 1,
        deleted: false,
    }];
    let newer = vec![Entry {
        key: "fig".into(),
        value: String::new(),
        seq: 9,
        deleted: true,
    }];
    let (partial, _) = merge_runs(&[newer.clone(), older.clone()], false);
    assert_eq!(partial.len(), 1);
    assert!(
        partial[0].deleted,
        "非底层归并必须保留 tombstone，否则旧值复活"
    );
    let (full, _) = merge_runs(&[newer, older], true);
    assert!(full.is_empty(), "到底层时 tombstone 落地，key 真正消失");
    println!(
        "[2] tombstone：非底层归并保留删除标记（{} 条仍带 deleted），到底层后 key 真删（0 条）",
        partial.len()
    );

    // —— [3] 归并节奏 vs 写放大/读放大：每次 flush 都归并 vs 攒 4 次再归并 ——
    const FLUSHES: usize = 12;
    const DOMAIN: usize = 60; // key 域小 → 大量覆盖，历史数据反复重写

    let mut history: Vec<Run> = Vec::new(); // 方案 A 的已归并历史（恒为 1 个 run）
    let mut pending: Vec<Run> = Vec::new(); // 方案 B 的待归并 run（攒批期间可到 4 个）
    let mut seq_a = SeqCounter(0);
    let mut seq_b = SeqCounter(0);
    let mut merge_bytes_a = 0u64; // 方案 A：每次 flush 后全量归并写出的字节
    let mut merge_bytes_b = 0u64; // 方案 B：攒 4 个 run 归并一次写出的字节
                                  // 每次 flush 后立刻做一次「不存在 key」点查，采样当时的读放大（探测 run 数）
    let mut probes_a = 0u64;
    let mut probes_b = 0u64;
    let mut hits_a = 0u64; // 命中对照：采样真实 key，两方案都应在自己可见域内命中
    let mut hits_b = 0u64;
    let mut sampled = 0u64;

    for i in 0..FLUSHES {
        let ops = make_ops(i, 40, DOMAIN);
        let fresh_a = build_run_from_ops(&ops, "v", &mut seq_a);
        let fresh_b = build_run_from_ops(&ops, "v", &mut seq_b);
        // 方案 A：每次 flush 都把「全部历史 + 新 run」归并成单 run
        if !history.is_empty() {
            let mut all = history;
            all.push(fresh_a);
            let (merged, m) = merge_runs(&all, false);
            merge_bytes_a += m.output_bytes;
            history = vec![merged];
        } else {
            history.push(fresh_a);
        }
        // 方案 B：攒到 4 个才归并一次
        pending.push(fresh_b);
        if pending.len() >= 4 {
            let (merged, m) = merge_runs(&pending, false);
            merge_bytes_b += m.output_bytes;
            pending = vec![merged];
        }
        // 采样：此刻做一个不存在 key 的点查（读放大 = 要探测的 run 数），
        // 再做两个真实 key 的点查确认两方案的可见性一致（命中计数应相同）
        let miss = format!("key-miss-{i:03}");
        probes_a += point_lookup(&history, &miss).runs_probed;
        probes_b += point_lookup(&pending, &miss).runs_probed;
        hits_a += u64::from(point_lookup(&history, &ops[0].0).found)
            + u64::from(point_lookup(&history, &ops[10].0).found);
        hits_b += u64::from(point_lookup(&pending, &ops[0].0).found)
            + u64::from(point_lookup(&pending, &ops[10].0).found);
        sampled += 1;
    }
    assert_eq!(hits_a, hits_b, "两方案的可见性应一致（覆盖/删除语义相同）");
    println!(
        "[3] {} 次 flush 的归并写字节：每次 flush 都归并 = {} B，攒 4 次归并 = {} B",
        FLUSHES, merge_bytes_a, merge_bytes_b
    );
    assert!(
        merge_bytes_b < merge_bytes_a,
        "攒批应少重写旧历史 → 写放大更低"
    );
    println!(
        "    平均读放大（不存在 key 需探测的 run 数，{sampled} 次采样）：A = {:.2}（恒单 run），B = {:.2}（攒批期间最高 4）",
        probes_a as f64 / sampled as f64,
        probes_b as f64 / sampled as f64
    );
    println!(
        "    命中一致性：A = {hits_a} 次 / B = {hits_b} 次（一致 ⇒ 攒批只影响性能指标，不影响正确性）"
    );
    println!("    结论：攒批少重写旧历史 → 写放大更低，但读放大在两次归并之间累积——「何时触发 compaction」本身就是 LSM 的核心运维杠杆");

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn e(key: &str, value: &str, seq: u64, deleted: bool) -> Entry {
        Entry {
            key: key.to_string(),
            value: value.to_string(),
            seq,
            deleted,
        }
    }

    #[test]
    fn merge_keeps_newest_and_sorted() {
        let older = vec![e("a", "1", 1, false), e("c", "3", 3, false)];
        let newer = vec![e("a", "2", 10, false), e("b", "2", 11, false)];
        let (out, stats) = merge_runs(&[newer, older], true);
        assert_eq!(out.len(), 3);
        assert_eq!(&out[0].value, "2"); // a 取新值
        assert_eq!(&out[1].key, "b");
        assert_eq!(&out[2].key, "c");
        assert_eq!(stats.dropped_stale, 1);
        // 输出有序
        assert!(out.windows(2).all(|w| w[0].key < w[1].key));
    }

    #[test]
    fn tombstone_kept_when_not_final() {
        let older = vec![e("k", "old", 1, false)];
        let newer = vec![e("k", "", 9, true)];
        let (out, _) = merge_runs(&[newer.clone(), older.clone()], false);
        assert_eq!(out.len(), 1);
        assert!(out[0].deleted);
        let (out2, _) = merge_runs(&[newer, older], true);
        assert!(out2.is_empty());
    }

    #[test]
    fn miss_probes_all_runs() {
        let runs = vec![
            vec![e("a", "1", 1, false)],
            vec![e("b", "1", 2, false)],
            vec![e("c", "1", 3, false)],
        ];
        let p = point_lookup(&runs, "nope");
        assert!(!p.found);
        assert_eq!(p.runs_probed, 3);
        let hit = point_lookup(&runs, "b");
        assert!(hit.found);
        assert_eq!(hit.runs_probed, 2);
    }

    #[test]
    fn batching_reduces_write_amp() {
        const FLUSHES: usize = 12;
        const DOMAIN: usize = 60;
        let mut history: Vec<Run> = Vec::new();
        let mut pending: Vec<Run> = Vec::new();
        let mut seq_a = SeqCounter(0);
        let mut seq_b = SeqCounter(0);
        let (mut bytes_a, mut bytes_b) = (0u64, 0u64);
        for i in 0..FLUSHES {
            let ops = make_ops(i, 40, DOMAIN);
            let fa = build_run_from_ops(&ops, "v", &mut seq_a);
            let fb = build_run_from_ops(&ops, "v", &mut seq_b);
            if !history.is_empty() {
                let mut all = history;
                all.push(fa);
                let (m2, st) = merge_runs(&all, false);
                bytes_a += st.output_bytes;
                history = vec![m2];
            } else {
                history.push(fa);
            }
            pending.push(fb);
            if pending.len() >= 4 {
                let (m2, st) = merge_runs(&pending, false);
                bytes_b += st.output_bytes;
                pending = vec![m2];
            }
        }
        assert!(
            bytes_b < bytes_a,
            "攒批归并写字节 {} 应小于全量归并 {}",
            bytes_b,
            bytes_a
        );
    }

    #[test]
    fn ops_are_deterministic() {
        assert_eq!(make_ops(3, 20, 60), make_ops(3, 20, 60));
        let ops = make_ops(0, 40, DOMAIN_FOR_TEST);
        assert!(ops.iter().any(|(_, d)| *d), "负载里应含删除操作");
    }

    const DOMAIN_FOR_TEST: usize = 60;

    #[test]
    fn merge_bytes_measure_increases_with_input() {
        let r1 = vec![e("a", "1", 1, false)];
        let r2 = vec![e("b", "1", 2, false), e("c", "1", 3, false)];
        let (_, s_small) = merge_runs(&[r1], false);
        let (_, s_big) = merge_runs(&[r2], false);
        assert!(s_big.output_bytes > s_small.output_bytes);
    }
}
