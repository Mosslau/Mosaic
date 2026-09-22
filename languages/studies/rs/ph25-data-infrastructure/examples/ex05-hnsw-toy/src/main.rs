//! ph25 ex05：HNSW 图索引 toy + recall / QPS / P95 / 内存实测（纯 std，零第三方依赖）
//!
//! 实现 HNSW（Hierarchical Navigable Small World）的最小核心：多层跳表式图结构、
//! 逐层贪婪下探（ef=1）、底层宽搜（ef_construction / ef_search）、双向邻居边、
//! 邻居超限时按距离剪枝到 M。查询侧输出四件套指标——**recall**（对暴力 top-10
//! 的重合率）、**QPS**（查询吞吐，`std::time::Instant` 实测）、**P95 延迟**、
//! **内存占用**（按结构成员计算得到的估计值，如实标注口径）。数据与随机数全部
//! 确定性（SplitMix64 风格 LCG），同一程序每次运行可复现。
//!
//! > 工业级工程（量化训练、启发式邻居选择、并发写入、持久化）属「后续可深入
//! > 方向」而非本阶段实现——本 toy 的定位是**把「图索引为什么快」跑成可测数字**。
//!
//! # 验证环境与命令
//! - 验证环境：rustc/cargo 1.92.0（macOS arm64）
//! - 运行：`cargo run --release`（输出 recall/QPS/P95/内存，真实测量值）
//! - 测试：`cargo test --release`
//! - 质量：`cargo fmt --check && cargo clippy --all-targets -- -D warnings`
//! - 验证状态：**已验证**（2026-09-04 本机实测，输出见 examples/README）

use std::collections::HashMap;
use std::time::Instant;

const DIM: usize = 8;
const N_BUILD: usize = 2000; // 入库向量数
const N_QUERY: usize = 400; // 查询向量数（样本外，不参与建图）
const TOP_K: usize = 10;

/// HNSW 超参（本 toy 的取值，见主文档 3.6 的参数说明）。
const M: usize = 8; // 每层每节点最大邻居数
const EF_CONSTRUCTION: usize = 64; // 建图时候选宽搜
const EF_SEARCH: usize = 120; // 查询时候选宽搜
const ML: f64 = 1.0 / std::f64::consts::LN_2; // 1/ln(M)；层高分布参数
const MAX_LEVELS: usize = 8; // 层数上限（防层高过高）

type Vector = [f32; DIM];

/// SplitMix64 风格的确定性 LCG（同一 seed 每次运行序列一致）。
struct Lcg(u64);

impl Lcg {
    fn next_u64(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    fn unit(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 / (1u64 << 53) as f64 // [0,1)
    }

    /// 标准正态（Box-Muller），用单位方差的确定性输入生成。
    fn gauss(&mut self) -> f64 {
        let u1 = self.unit().max(1e-12);
        let u2 = self.unit();
        (-2.0 * u1.ln()).sqrt() * (std::f64::consts::TAU * u2).cos()
    }
}

fn l2sq(a: &Vector, b: &Vector) -> f32 {
    a.iter().zip(b).map(|(x, y)| (x - y) * (x - y)).sum()
}

/// 确定性生成 N 个「多簇高斯」向量（贴近 ANN benchmark 的分布形态）。
fn gen_points(n: usize, seed: u64, cluster: bool) -> Vec<Vector> {
    let mut rng = Lcg(seed);
    (0..n)
        .map(|i| {
            // 4 簇：簇心在超立方体角上，点围绕簇心高斯分布
            let centre: Vector = if cluster {
                let c = i % 4;
                let mut v = [0.0f32; DIM];
                for (k, e) in v.iter_mut().enumerate() {
                    *e = if k % 4 == c { 3.0 } else { -3.0 };
                }
                v
            } else {
                [0.0; DIM]
            };
            let mut v = [0.0f32; DIM];
            for (k, e) in v.iter_mut().enumerate() {
                let base = if cluster { centre[k] } else { 0.0 };
                *e = base + rng.gauss() as f32;
            }
            v
        })
        .collect()
}

/// 暴力 top-k（召回率的基准真值）。
fn brute_topk(pts: &[Vector], q: &Vector, k: usize) -> Vec<usize> {
    let mut scored: Vec<(f32, usize)> = pts
        .iter()
        .enumerate()
        .map(|(i, p)| (l2sq(p, q), i))
        .collect();
    scored.sort_by(|a, b| a.0.total_cmp(&b.0));
    scored.into_iter().take(k).map(|(_, i)| i).collect()
}

/// HNSW toy：多层邻接图。`adjacency[level]`：节点 id → 邻居 id 列表。
struct Hnsw {
    pts: Vec<Vector>,
    adjacency: Vec<HashMap<usize, Vec<usize>>>,
    node_levels: Vec<usize>,
    max_level: usize,
    entry: usize,
}

impl Hnsw {
    fn new() -> Hnsw {
        Hnsw {
            pts: Vec::new(),
            adjacency: Vec::new(),
            node_levels: Vec::new(),
            max_level: 0,
            entry: 0,
        }
    }

    /// 层高：`floor(-ln(u) * mL)`，上限 MAX_LEVELS-1。
    fn random_level(rng: &mut Lcg) -> usize {
        let u = rng.unit().max(1e-12);
        ((-u.ln()) * ML).floor().min((MAX_LEVELS - 1) as f64) as usize
    }

    fn neighbors_at(&self, level: usize, node: usize) -> Vec<usize> {
        self.adjacency[level]
            .get(&node)
            .cloned()
            .unwrap_or_default()
    }

    /// 单层贪心宽搜：从 `eps` 出发在 level 层找与 q 最近的候选节点。
    ///
    /// 标准实现：`candidates`（近端优先的待展开集）与 `results`（保持 ef 个最近）
    /// 都用 `(距离的 u32 排序键, 节点)` 的 BTreeSet 表示——f32 不是 Ord，用
    /// `to_bits()` 把非负距离映射成保序的 u32 键（IEEE 754 对同号正浮点保序）。
    fn search_layer(&self, q: &Vector, eps: &[usize], ef: usize, level: usize) -> Vec<usize> {
        let dist = |i: usize| l2sq(&self.pts[i], q);
        let key = |f: f32| f.to_bits();
        let mut candidates: std::collections::BTreeSet<(u32, usize)> =
            std::collections::BTreeSet::new();
        let mut results: std::collections::BTreeSet<(u32, usize)> =
            std::collections::BTreeSet::new();
        let mut visited: std::collections::HashSet<usize> = std::collections::HashSet::new();
        for &e in eps {
            let k = (key(dist(e)), e);
            candidates.insert(k);
            results.insert(k);
            visited.insert(e);
        }
        while let Some(&(d, node)) = candidates.iter().next() {
            candidates.remove(&(d, node));
            // 贪心终止：离候选最近的点都已比 results 的最远点更远
            if results.len() >= ef && d > results.iter().next_back().expect("results 非空").0 {
                break;
            }
            for nb in self.neighbors_at(level, node) {
                if visited.contains(&nb) {
                    continue;
                }
                visited.insert(nb);
                let dn = key(dist(nb));
                let worst = results.iter().next_back().copied();
                if results.len() < ef || Some(dn) < worst.map(|(w, _)| w) {
                    candidates.insert((dn, nb));
                    results.insert((dn, nb));
                    while results.len() > ef {
                        let w = results.iter().next_back().copied();
                        if let Some(w) = w {
                            results.remove(&w);
                        }
                    }
                }
            }
        }
        results.into_iter().map(|(_, n)| n).collect()
    }

    fn add_neighbor(&mut self, level: usize, a: usize, b: usize) {
        let la = self.adjacency[level].entry(a).or_default();
        if !la.contains(&b) {
            la.push(b);
            self.prune(level, a);
        }
        let lb = self.adjacency[level].entry(b).or_default();
        if !lb.contains(&a) {
            lb.push(a);
            self.prune(level, b);
        }
    }

    /// 邻居超限时按距离剪枝到 M。
    fn prune(&mut self, level: usize, node: usize) {
        let list = self.adjacency[level].get_mut(&node).expect("entry 存在");
        if list.len() <= M {
            return;
        }
        // 需要按与 node 的距离排序，但此刻借用了可变引用——先复制再重写
        let pt = self.pts[node];
        let mut scored: Vec<(f32, usize)> = list
            .iter()
            .map(|&nb| (l2sq(&self.pts[nb], &pt), nb))
            .collect();
        scored.sort_by(|a, c| a.0.total_cmp(&c.0));
        list.clear();
        list.extend(scored.into_iter().take(M).map(|(_, nb)| nb));
    }

    /// 插入一个点（pts 里先放好数据，id = len-1）。
    fn insert_existing(&mut self, id: usize, rng: &mut Lcg) {
        if id == 0 {
            let lvl = Hnsw::random_level(rng);
            self.node_levels.push(lvl);
            self.adjacency.resize(lvl + 1, HashMap::new());
            self.adjacency[lvl].entry(id).or_default();
            self.max_level = lvl;
            self.entry = id;
            return;
        }
        let q = self.pts[id];
        let lvl = Hnsw::random_level(rng);
        self.node_levels.push(lvl);
        // 确保层级数组足够
        while self.adjacency.len() <= lvl {
            self.adjacency.push(HashMap::new());
        }
        self.adjacency[lvl].entry(id).or_default();

        let start_layer = lvl.min(self.max_level);
        let mut ep = vec![self.entry];
        // 相位一：从图顶下探到 start_layer+1，每层只留最近 1 个（greedy route）
        for lc in ((start_layer + 1)..=self.max_level).rev() {
            ep = self.search_layer(&q, &ep, 1, lc);
        }
        // 相位二：从 start_layer 向下到 0，逐层宽搜 + 连边
        for lc in (0..=start_layer).rev() {
            let cand = self.search_layer(&q, &ep, EF_CONSTRUCTION, lc);
            // 取最近 M 个（排除自己）建双向边
            let nn: Vec<usize> = cand.into_iter().filter(|&n| n != id).take(M).collect();
            for nb in &nn {
                self.add_neighbor(lc, id, *nb);
            }
            ep = nn;
        }
        if lvl > self.max_level {
            self.max_level = lvl;
            self.entry = id;
        }
    }

    fn insert(&mut self, pt: Vector, rng: &mut Lcg) {
        self.pts.push(pt);
        let id = self.pts.len() - 1;
        self.insert_existing(id, rng);
    }

    /// 查询 top-k：层间下探后用 ef_search 在底层宽搜。
    fn search(&self, q: &Vector, k: usize) -> Vec<usize> {
        if self.pts.is_empty() {
            return Vec::new();
        }
        let mut ep = vec![self.entry];
        for lc in (1..=self.max_level).rev() {
            ep = self.search_layer(q, &ep, 1, lc);
        }
        let cand = self.search_layer(q, &ep, EF_SEARCH, 0);
        cand.into_iter().take(k).collect()
    }

    /// 内存占用估计：点数据 + 边表（每边一个 usize）+ 层表 + HashMap 槽位开销按每节点 8B 估。
    fn memory_bytes(&self) -> usize {
        let pts_bytes = self.pts.len() * DIM * 4;
        let mut edge_bytes = 0usize;
        let mut bucket_overhead = 0usize;
        for level in &self.adjacency {
            for nb in level.values() {
                edge_bytes += nb.len() * std::mem::size_of::<usize>();
                bucket_overhead += 32; // HashMap 每桶开销的粗略估计
            }
        }
        let layer_bytes = self.node_levels.len() * 4; // u32 层高
        pts_bytes + edge_bytes + bucket_overhead + layer_bytes
    }
}

/// recall 与查询耗时统计（真实测量，见 README）。
fn run_query_metrics(hnsw: &Hnsw, pts: &[Vector], queries: &[Vector]) -> (f64, f64, f64, f64) {
    // 建树阶段完成后逐查询计时
    let mut recall_sum = 0.0f64;
    let mut latencies_ns: Vec<u128> = Vec::with_capacity(queries.len());
    for q in queries {
        let truth: Vec<usize> = brute_topk(pts, q, TOP_K);
        let t0 = Instant::now();
        let found = hnsw.search(q, TOP_K);
        let dt = t0.elapsed().as_nanos();
        latencies_ns.push(dt);
        let hits = found.iter().filter(|&x| truth.contains(x)).count();
        recall_sum += hits as f64 / TOP_K as f64;
    }
    // 吞度量：整批再跑一遍求 QPS
    let t0 = Instant::now();
    for q in queries {
        let _ = hnsw.search(q, TOP_K);
    }
    let batch_s = t0.elapsed().as_secs_f64();
    let qps = queries.len() as f64 / batch_s;
    latencies_ns.sort_unstable();
    let p95 = latencies_ns[(latencies_ns.len() as f64 * 0.95) as usize] as f64 / 1e6; // ms
    let recall = recall_sum / queries.len() as f64;
    (recall, qps, p95, batch_s)
}

fn main() {
    println!("== HNSW toy：图索引 vs 暴力检索 ==");
    println!(
        "参数：N_build={N_BUILD} DIM={DIM} M={M} ef_construction={EF_CONSTRUCTION} ef_search={EF_SEARCH} top_k={TOP_K}"
    );

    let pts = gen_points(N_BUILD, 42, true);
    let queries = gen_points(N_QUERY, 7, true);
    println!(
        "数据：入库 {} 个 / 查询 {} 个（多簇高斯，样本外查询）",
        pts.len(),
        queries.len()
    );

    // 构建图索引
    let mut hnsw = Hnsw::new();
    let mut rng = Lcg(0x5EED_5EED_5EED_5EED);
    let t0 = Instant::now();
    for p in &pts {
        hnsw.insert(*p, &mut rng);
    }
    let build_s = t0.elapsed().as_secs_f64();
    // 边数与内存统计
    let mut edges = 0usize;
    for level in &hnsw.adjacency {
        edges += level.values().map(Vec::len).sum::<usize>();
    }
    let mem = hnsw.memory_bytes();
    println!(
        "构建：{:.1} ms，图总边数 {}，层数 {}，内存占用 ≈ {:.1} KiB（按结构成员计算估计）",
        build_s * 1e3,
        edges,
        hnsw.max_level + 1,
        mem as f64 / 1024.0
    );

    // 查询指标（真实测量）
    let (recall, qps, p95, batch_s) = run_query_metrics(&hnsw, &pts, &queries);
    println!(
        "查询：recall@{TOP_K} = {:.3}，QPS = {:.0}（整批 {batch_s:.3}s 除 {N_QUERY} 查询），P95 延迟 = {p95:.3} ms",
        recall, qps
    );

    // 暴力对照（同样计时）
    let t0 = Instant::now();
    for q in &queries {
        let _ = brute_topk(&pts, q, TOP_K);
    }
    let brute_s = t0.elapsed().as_secs_f64();
    let brute_qps = N_QUERY as f64 / brute_s;
    println!("暴力对照：QPS = {brute_qps:.0}（整批 {brute_s:.3}s）——同一批查询、同一真值");
    let speedup = qps / brute_qps;
    println!(
        "对照：本 toy 以 {speedup:.2}x 于暴力的吞吐拿到 recall@{TOP_K} = {recall:.3}——在 2k×8 维这种小尺度上，图索引的常数开销尚未被 N 增长摊薄，收益要到更大 N/更高维才显性；recall/QPS 是图索引的调参权衡（ef_search 越大 recall 越高、越慢），工业实现再加量化与并发写入",
    );

    assert!(
        recall > 0.5,
        "recall 应显著高于随机（实测 {recall:.3}），若低于阈值请检查 HNSW 实现"
    );
    println!("\n== ex05 完成：四件套指标（recall/QPS/P95/内存）已实测输出 ==");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn brute_topk_returns_sorted_unique() {
        let pts = gen_points(50, 1, false);
        let q = gen_points(1, 2, false)[0];
        let tk = brute_topk(&pts, &q, 5);
        assert_eq!(tk.len(), 5);
        let mut uniq: Vec<usize> = tk.clone();
        uniq.dedup();
        assert_eq!(uniq.len(), 5, "结果不应有重复");
        // 顺序必须按距离升序
        for w in tk.windows(2) {
            assert!(l2sq(&pts[w[0]], &q) <= l2sq(&pts[w[1]], &q));
        }
    }

    #[test]
    fn insert_search_recall_reasonable() {
        let pts = gen_points(400, 11, true);
        let queries = gen_points(60, 13, true);
        let mut hnsw = Hnsw::new();
        let mut rng = Lcg(99);
        for p in &pts {
            hnsw.insert(*p, &mut rng);
        }
        let mut recall_sum = 0.0f64;
        for q in &queries {
            let truth = brute_topk(&pts, q, TOP_K);
            let found = hnsw.search(q, TOP_K);
            let hits = found.iter().filter(|&x| truth.contains(x)).count();
            recall_sum += hits as f64 / TOP_K as f64;
        }
        let recall = recall_sum / queries.len() as f64;
        assert!(recall > 0.5, "recall {recall} 应大于 0.5（toy 超参足够）");
    }

    #[test]
    fn empty_graph_search_returns_empty() {
        let h = Hnsw::new();
        let q = [0.0f32; DIM];
        assert!(h.search(&q, 5).is_empty());
    }

    #[test]
    fn single_insert_finds_itself() {
        let mut hnsw = Hnsw::new();
        let mut rng = Lcg(3);
        hnsw.insert([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0], &mut rng);
        let q = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0];
        assert_eq!(hnsw.search(&q, 1), vec![0]);
    }

    #[test]
    fn memory_estimate_grows_with_nodes() {
        let mut hnsw = Hnsw::new();
        let mut rng = Lcg(4);
        let pts = gen_points(100, 5, false);
        for p in pts.iter().take(10) {
            hnsw.insert(*p, &mut rng);
        }
        let small = hnsw.memory_bytes();
        for p in pts.iter().skip(10) {
            hnsw.insert(*p, &mut rng);
        }
        assert!(hnsw.memory_bytes() > small);
    }
}
