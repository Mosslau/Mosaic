// exercises/sol-04-hnsw-toy-metrics.rs —— 练习 4 参考实现：图索引 toy 输出 recall/QPS/P95/内存
// 对应 roadmap §25 练习「实现 HNSW toy version 并输出 recall / QPS 指标」与主文档 3.6。
// 简化声明：实现「单层图（NSW 式）」作为 HNSW 的最小可测子集——每条新边连到
// 已有点里最近的 M 个（双向、超限按距离剪枝），查询做**可变宽度束搜索**
// （beam width = ef：每轮保留 ef 个最近候选继续展开；ef 大 → 探测更多、更准更慢）。
// 指标全为真实测量：recall 对暴力 top-k、QPS/P95 来自 `std::time::Instant`、
// 内存按结构成员计算估计。数据与随机数确定性（LCG），每次运行可复现。
// 验证环境：rustc/cargo 1.92.0（macOS arm64）。编译/运行/测试：
//   rustc --edition 2021 -D warnings sol-04-hnsw-toy-metrics.rs -o /tmp/ph25-sol04 && /tmp/ph25-sol04
//   rustc --edition 2021 -D warnings --test sol-04-hnsw-toy-metrics.rs -o /tmp/ph25-sol04-t && /tmp/ph25-sol04-t
// 验证状态：已验证（rustc 1.92.0，aarch64-apple-darwin）。

use std::collections::BTreeSet;
use std::time::Instant;

const DIM: usize = 6;
const N_BUILD: usize = 800;
const N_QUERY: usize = 100;
const TOP_K: usize = 5;
const M: usize = 12; // 每节点邻居上限
const EF_NARROW: usize = 6; // 窄束搜索宽度
const EF_WIDE: usize = 60; // 宽束搜索宽度

type Vector = [f32; DIM];

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
        (self.next_u64() >> 11) as f64 / (1u64 << 53) as f64
    }
    fn gauss(&mut self) -> f64 {
        let u1 = self.unit().max(1e-12);
        let u2 = self.unit();
        (-2.0 * u1.ln()).sqrt() * (std::f64::consts::TAU * u2).cos()
    }
}

fn gen_points(n: usize, seed: u64) -> Vec<Vector> {
    let mut rng = Lcg(seed.wrapping_mul(0x9E3779B97F4A7C15));
    (0..n)
        .map(|i| {
            let c = i % 3; // 3 簇
            let mut v = [0.0f32; DIM];
            for (k, e) in v.iter_mut().enumerate() {
                let base = if k % 3 == c { 2.5 } else { -2.5 };
                *e = base + rng.gauss() as f32;
            }
            v
        })
        .collect()
}

fn l2sq(a: &Vector, b: &Vector) -> f32 {
    a.iter().zip(b).map(|(x, y)| (x - y) * (x - y)).sum()
}

fn brute_topk(pts: &[Vector], q: &Vector) -> Vec<usize> {
    let mut scored: Vec<(f32, usize)> = pts
        .iter()
        .enumerate()
        .map(|(i, p)| (l2sq(p, q), i))
        .collect();
    scored.sort_by(|a, b| a.0.total_cmp(&b.0));
    scored.into_iter().take(TOP_K).map(|(_, i)| i).collect()
}

/// 单层小世界图：`adj[node]` 是邻居列表（无顺序要求）。
struct Graph {
    pts: Vec<Vector>,
    adj: Vec<Vec<usize>>,
    edges: usize,
}

impl Graph {
    fn build(pts: Vec<Vector>) -> Graph {
        let mut g = Graph { pts: Vec::with_capacity(pts.len()), adj: Vec::new(), edges: 0 };
        for p in pts {
            let id = g.pts.len();
            g.pts.push(p);
            g.adj.push(Vec::new());
            if id == 0 {
                continue;
            }
            // 找已有点里最近的 M 个，双向连边并各自剪枝到 M
            let mut cand: Vec<(f32, usize)> =
                (0..id).map(|j| (l2sq(&p, &g.pts[j]), j)).collect();
            cand.sort_by(|a, b| a.0.total_cmp(&b.0));
            let nn: Vec<usize> = cand.into_iter().take(M).map(|(_, j)| j).collect();
            for nb in nn {
                g.add_edge(id, nb);
            }
        }
        g
    }

    fn add_edge(&mut self, a: usize, b: usize) {
        if !self.adj[a].contains(&b) {
            self.adj[a].push(b);
            self.edges += 1;
        }
        if !self.adj[b].contains(&a) {
            self.adj[b].push(a);
        }
        self.prune(a);
        self.prune(b);
    }

    fn prune(&mut self, node: usize) {
        if self.adj[node].len() <= M {
            return;
        }
        let pt = self.pts[node];
        let mut scored: Vec<(f32, usize)> = self.adj[node]
            .iter()
            .map(|&nb| (l2sq(&pt, &self.pts[nb]), nb))
            .collect();
        scored.sort_by(|a, b| a.0.total_cmp(&b.0));
        self.adj[node] = scored.into_iter().take(M).map(|(_, nb)| nb).collect();
    }

    /// 多起点束搜索：候选集与结果集都维护最近 ef 个，直到无法改进。
    /// 起点取每条簇的第一个点（i%3==0），保证任何一簇的查询都有近的出发入口——
    /// 这是对「单层图」可导航性不足的补偿（真实 HNSW 用高层稀疏图完成同一件事）。
    /// 距离用 `f32::to_bits()` 转成保序的 u32 键（非负距离对同号浮点保序）。
    fn beam_search(&self, q: &Vector, ef: usize) -> Vec<usize> {
        let dist = |i: usize| l2sq(&self.pts[i], q);
        let key = |f: f32| f.to_bits();
        let mut candidates: BTreeSet<(u32, usize)> = BTreeSet::new();
        let mut results: BTreeSet<(u32, usize)> = BTreeSet::new();
        let mut visited: Vec<bool> = vec![false; self.pts.len()];
        // 每簇首个点作起点（i%3==0：0,1,2 分属 3 簇）
        for s in [0usize, 1, 2] {
            candidates.insert((key(dist(s)), s));
            results.insert((key(dist(s)), s));
            visited[s] = true;
        }
        while let Some(&(d, node)) = candidates.iter().next() {
            candidates.remove(&(d, node));
            if results.len() >= ef && d > results.iter().next_back().expect("结果非空").0 {
                break; // 最近未展开点都比结果集最远点更远 → 贪心停止
            }
            for &nb in &self.adj[node] {
                if visited[nb] {
                    continue;
                }
                visited[nb] = true;
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

    fn memory_bytes(&self) -> usize {
        self.pts.len() * DIM * 4 + self.edges * std::mem::size_of::<usize>() + self.adj.len() * 24
    }
}

/// 对指定 ef 跑一批查询，返回 (recall@TOP_K, QPS, P95_ms)（真实测量）。
fn evaluate(g: &Graph, queries: &[Vector], ef: usize) -> (f64, f64, f64) {
    let mut recall_sum = 0.0f64;
    let mut lats_ms: Vec<f64> = Vec::with_capacity(queries.len());
    let t0_batch = Instant::now();
    for q in queries {
        let truth = brute_topk(&g.pts, q);
        let t0 = Instant::now();
        let found = g.beam_search(q, ef);
        lats_ms.push(t0.elapsed().as_secs_f64() * 1e3);
        let hits = found.iter().filter(|x| truth.contains(x)).count();
        recall_sum += hits as f64 / TOP_K as f64;
    }
    let batch_s = t0_batch.elapsed().as_secs_f64();
    let qps = queries.len() as f64 / batch_s;
    lats_ms.sort_by(|a, b| a.total_cmp(b));
    let p95 = lats_ms[(lats_ms.len() as f64 * 0.95) as usize];
    (recall_sum / queries.len() as f64, qps, p95)
}

fn run_sweep(g: &Graph, queries: &[Vector], ef: usize) -> (f64, f64, f64) {
    evaluate(g, queries, ef)
}

fn main() {
    let pts = gen_points(N_BUILD, 42);
    let queries = gen_points(N_QUERY, 7);
    println!(
        "参数：N_build={N_BUILD} DIM={DIM} M={M} top_k={TOP_K}；查询 {} 个（样本外）",
        queries.len()
    );

    let g = Graph::build(pts);
    println!(
        "构建：图总边数 {}，内存 ≈ {:.1} KiB（按结构成员计算估计）",
        g.edges,
        g.memory_bytes() as f64 / 1024.0
    );

    println!("\n[ef 扫描] recall@5 | QPS | P95(ms) —— 同一张图、同一批查询，只改束宽：");
    for (name, ef) in [("窄束 ef=6", EF_NARROW), ("宽束 ef=60", EF_WIDE)] {
        let (recall, qps, p95) = run_sweep(&g, &queries, ef);
        println!("  {name:10} → recall = {recall:.3}，QPS = {qps:6.0}，P95 = {p95:.2} ms");
    }

    let (r_narrow, _, _) = run_sweep(&g, &queries, EF_NARROW);
    let (r_wide, _, _) = run_sweep(&g, &queries, EF_WIDE);
    assert!(
        r_wide > r_narrow,
        "宽束 recall {} 应显著高于窄束 {}",
        r_wide,
        r_narrow
    );
    println!(
        "\n结论：束宽 {EF_WIDE} 的 recall（{r_wide:.3}）> 束宽 {EF_NARROW} 的 recall（{r_narrow:.3}）——\n      更宽的候选集让搜索覆盖更多区域（recall 高），但每次迭代要维护更大的候选集（更慢）——recall/吞吐权衡由此而来。"
    );
    println!("\n练习 4 参考实现自检通过：recall/QPS/P95/内存四件套真实输出，权衡断言成立");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn wider_beam_has_higher_recall() {
        let pts = gen_points(400, 5);
        let queries = gen_points(40, 9);
        let g = Graph::build(pts);
        let (rn, _, _) = evaluate(&g, &queries, 6);
        let (rw, _, _) = evaluate(&g, &queries, 90);
        assert!(rw > rn, "窄束 {rn} 应低于宽束 {rw}");
        assert!(rw > 0.5, "宽束 recall 应显著高于随机");
    }

    #[test]
    fn memory_grows_with_edges() {
        let small = Graph::build(gen_points(100, 1));
        let big = Graph::build(gen_points(300, 2));
        assert!(big.memory_bytes() > small.memory_bytes());
    }
}
