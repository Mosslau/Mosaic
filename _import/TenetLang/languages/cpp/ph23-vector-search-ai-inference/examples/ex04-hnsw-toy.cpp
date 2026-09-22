// ex04-hnsw-toy.cpp —— toy HNSW：分层图索引的插入 + 贪心/ef 搜索 + 召回率对照
// 对应 ph23 主文档 3.4 与 roadmap §23「实现 HNSW 的节点、邻接表和基础搜索流程」。
// 教学点：
//   ① 结构心智：HNSW = "跳表的图版"——高层邻居稀疏（长程跳），层 0 邻居密集（精确收尾）；
//      每层都是"当前节点的一小撮最近邻构成的图"；
//   ② 插入：随机给新节点分一个层高 L（几何分布），从全局入口在 L 以上的层"贪心下潜"
//      （只朝最近邻走一步），在 L..0 层各做一次"ef 搜索"取候选，就近连 M 条边并回连；
//   ③ 搜索：上层贪心下潜到层 0 → 在层 0 做 efSearch（结果集 + 候选集双向收紧）→ 排序取 top-k；
//   ④ 参数语义：M（每层出度，越大图越密、召回越高、内存越大）、efConstruction（建图搜索宽度，
//      影响建图质量）、efSearch（查询宽度，影响召回 vs 延迟）；三者是"召回率-内存-延迟"三角；
//   ⑤ 与暴力检索对照输出 recall@k——注意这是 toy（无启发式剪枝、无并发），只演示形态与趋势。
//      真实 Faiss/HNSWlib 还有 neighbor selection heuristic、层数上限、mul 参数等工程细节。
// 资源管理：全部 std::vector/unique_ptr 容器持有（R.11），无裸 new/delete。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -O2 -Wall -Wextra ex04-hnsw-toy.cpp -o /tmp/ph23-ex04 && /tmp/ph23-ex04
// 验证状态：已验证（零警告、断言全绿、退出码 0；召回率实测见运行输出）

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <queue>
#include <random>
#include <stdexcept>
#include <vector>

namespace hnsw_toy {

using node_id = std::uint32_t;

// —— 图索引本体 ——
class hnsw {
public:
    hnsw(std::size_t dim, std::size_t m, std::size_t ef_construction, std::size_t ef_search,
         std::uint32_t seed)
        : dim_(dim),
          m_(m),
          ef_c_(ef_construction),
          ef_s_(ef_search),
          max_level_(16),          // 层高上限（几何分布的截断）
          rng_(seed) {}

    std::size_t size() const { return vectors_.size(); }

    // 插入一条向量（返回节点 id，等于插入顺序）
    std::size_t add(const std::vector<float>& v) {
        if (v.size() != dim_) throw std::invalid_argument("dim mismatch");
        const node_id id = static_cast<node_id>(vectors_.size());
        vectors_.push_back(v);
        const int lvl = pick_level();
        levels_.push_back(lvl);
        layers_.emplace_back(static_cast<std::size_t>(lvl) + 1);

        if (id == 0) {
            entry_ = id;
            return id;
        }
        // 从全局入口开始：先在"高于新节点层高"的各层贪心下潜（ef=1 只走最近邻）
        node_id ep = entry_;
        const int graph_top = static_cast<int>(levels_[entry_]);
        for (int lc = graph_top; lc > lvl; --lc) {
            ep = greedy_step(ep, v.data(), lc);
        }
        // 再从 min(lvl, graph_top) 往下逐层连边
        for (int lc = std::min(lvl, graph_top); lc >= 0; --lc) {
            auto cands = search_layer(ep, v.data(), lc, ef_c_, /*collect*/ true);
            // 就近选 m_ 个候选，与它们双向连边
            std::sort(cands.begin(), cands.end(),
                      [](const auto& a, const auto& b) { return a.dist < b.dist; });
            const std::size_t take = std::min(m_, cands.size());
            for (std::size_t j = 0; j < take; ++j) {
                const node_id c = cands[j].id;
                link(lc, id, c);
            }
            ep = cands.empty() ? ep : cands.front().id;  // 下潜入口更新为当前层最近者
        }
        if (lvl > levels_[entry_]) entry_ = id;          // 成为新的全局入口
        return id;
    }

    // 查询：返回 (id, 平方L2) 按近到远排序的前 k 个
    struct hit {
        node_id id;
        float dist;
    };
    std::vector<hit> search(const std::vector<float>& q, std::size_t k) const {
        if (q.size() != dim_) throw std::invalid_argument("dim mismatch");
        if (vectors_.empty()) return {};
        node_id ep = entry_;
        const int graph_top = static_cast<int>(levels_[entry_]);
        for (int lc = graph_top; lc > 0; --lc) {
            ep = greedy_step(ep, q.data(), lc);           // 上层只做贪心定位
        }
        auto cands = search_layer(ep, q.data(), 0, ef_s_, /*collect*/ true);
        std::sort(cands.begin(), cands.end(),
                  [](const auto& a, const auto& b) { return a.dist < b.dist; });
        std::vector<hit> out;
        const std::size_t take = std::min(k, cands.size());
        out.reserve(take);
        for (std::size_t j = 0; j < take; ++j) out.push_back({cands[j].id, cands[j].dist});
        return out;
    }

    // 图统计（配合主文档 3.4 的结构讲解）
    struct stats {
        double avg_deg0{0};  // 层 0 平均出度
        double avg_level{0};
        std::size_t max_degree{0};
    };
    stats graph_stats() const {
        stats s;
        std::size_t total_deg = 0, max_deg = 0;
        for (node_id i = 0; i < static_cast<node_id>(vectors_.size()); ++i) {
            const std::size_t d = layers_[i][0].size();
            total_deg += d;
            max_deg = std::max(max_deg, d);
            s.avg_level += static_cast<double>(levels_[i]);
        }
        if (!vectors_.empty()) {
            s.avg_deg0 = static_cast<double>(total_deg) / vectors_.size();
            s.avg_level /= vectors_.size();
            s.max_degree = max_deg;
        }
        return s;
    }

private:
    // 层高：几何分布（P(L≥1)=0.5，逐层减半），截断到 max_level_，层 0 一定有
    int pick_level() {
        int lvl = 0;
        while (lvl < max_level_ &&
               std::uniform_real_distribution<float>(0.0f, 1.0f)(rng_) < 0.5f) {
            ++lvl;
        }
        return lvl;
    }

    float dist2(const node_id a, const float* b) const {
        const float* va = vectors_[a].data();
        float s = 0.0f;
        for (std::size_t d = 0; d < dim_; ++d) {
            const float t = va[d] - b[d];
            s += t * t;
        }
        return s;
    }

    // 单步贪心：在当前层的邻居里找一个更近的（走一步）——上层下潜只用它
    node_id greedy_step(node_id cur, const float* q, int layer) const {
        float best = dist2(cur, q);
        bool improved = true;
        while (improved) {                     // 走到局部最优为止
            improved = false;
            for (const node_id n : layers_[cur][static_cast<std::size_t>(layer)]) {
                const float d = dist2(n, q);
                if (d < best) {
                    best = d;
                    cur = n;
                    improved = true;
                }
            }
        }
        return cur;
    }

    // ef 搜索：返回访问到的节点 + 距离（未排序），是 HNSW 插入与查询共用的核心。
    // visited 在单次调用内去重；结果集按距离收成 ef 个最近——"候选只从最近处扩展"。
    std::vector<hit> search_layer(node_id ep, const float* q, int layer, std::size_t ef,
                                  bool /*collect*/) const {
        std::vector<bool> visited(vectors_.size(), false);
        visited[ep] = true;

        // 候选：最小堆（越近越先扩展）
        auto closer_first = [](const hit& x, const hit& y) { return x.dist > y.dist; };
        std::priority_queue<hit, std::vector<hit>, decltype(closer_first)> candidates(
            closer_first);
        // 结果：最大堆（堆顶 = 当前最差入选者）
        auto farther_first = [](const hit& x, const hit& y) { return x.dist < y.dist; };
        std::priority_queue<hit, std::vector<hit>, decltype(farther_first)> results(
            farther_first);

        candidates.push({ep, dist2(ep, q)});
        results.push({ep, dist2(ep, q)});
        while (!candidates.empty()) {
            const hit cur = candidates.top();
            candidates.pop();
            if (cur.dist > results.top().dist) break;  // 候选越来越远，再扩展无意义
            for (const node_id n : layers_[cur.id][static_cast<std::size_t>(layer)]) {
                if (visited[n]) continue;
                visited[n] = true;
                const float d = dist2(n, q);
                if (results.size() < ef || d < results.top().dist) {
                    results.push({n, d});
                    if (results.size() > ef) results.pop();   // 淘汰最差
                    candidates.push({n, d});
                }
            }
        }
        std::vector<hit> out;
        out.reserve(results.size());
        while (!results.empty()) {
            out.push_back(results.top());
            results.pop();
        }
        return out;
    }

    // 双向连边（层内）：两边都保持容量上限；超容时用"新边更近则换掉最远边"的简化规则。
    // 注：真实 HNSW 用 neighbor selection heuristic 而非纯最近——toy 到此为止。
    void link(int layer, node_id a, node_id b) {
        if (a == b) return;
        const std::size_t cap = (layer == 0) ? m_ * 2 : m_;
        auto& la = layers_[a][static_cast<std::size_t>(layer)];
        auto& lb = layers_[b][static_cast<std::size_t>(layer)];
        push_bounded(la, b, cap, a);
        push_bounded(lb, a, cap, b);
    }

    void push_bounded(std::vector<node_id>& list, node_id cand, std::size_t cap, node_id self) {
        auto it = std::find(list.begin(), list.end(), cand);
        if (it != list.end()) return;                       // 已有该边
        if (list.size() < cap) {
            list.push_back(cand);
            return;
        }
        // 满：找出最远邻居，若 cand 比它近则替换（教学简化，不递归传播）
        node_id far = list.front();
        float far_d = dist2(self, vectors_[far].data());
        for (const node_id n : list) {
            const float d = dist2(self, vectors_[n].data());
            if (d > far_d) {
                far = n;
                far_d = d;
            }
        }
        if (dist2(self, vectors_[cand].data()) < far_d) {
            std::replace(list.begin(), list.end(), far, cand);
        }
    }

    std::size_t dim_;
    std::size_t m_;
    std::size_t ef_c_;
    std::size_t ef_s_;
    int max_level_;
    node_id entry_{0};
    std::vector<std::vector<float>> vectors_;
    std::vector<int> levels_;                       // 每节点层高
    std::vector<std::vector<std::vector<node_id>>> layers_;  // [节点][层]邻居表
    mutable std::mt19937 rng_;
};

}  // namespace hnsw_toy

int main() {
    using namespace hnsw_toy;

    // —— 数据：可复现的均匀随机点 ——
    constexpr std::size_t dim = 16;
    constexpr std::size_t n = 2000;
    constexpr std::size_t nq = 200;
    constexpr std::size_t k = 10;

    std::mt19937 rng(2024u);
    std::uniform_real_distribution<float> uni(0.0f, 1.0f);
    auto rvec = [&] {
        std::vector<float> v(dim);
        for (auto& x : v) x = uni(rng);
        return v;
    };
    std::vector<std::vector<float>> db, qs;
    for (std::size_t i = 0; i < n; ++i) db.push_back(rvec());
    for (std::size_t i = 0; i < nq; ++i) qs.push_back(rvec());

    // —— 建索引 ——
    hnsw index(dim, /*m=*/8, /*ef_c=*/64, /*ef_s=*/48, /*seed=*/1u);
    for (const auto& v : db) index.add(v);
    const auto st = index.graph_stats();
    std::cout << "[1] 建图: n=" << n << " dim=" << dim << ", 层0平均出度=" << st.avg_deg0
              << ", 最大出度=" << st.max_degree << ", 平均层高=" << st.avg_level << '\n';

    // —— 暴力 ground truth（每 query 全扫一遍取最近 k）——
    auto brute = [&](const std::vector<float>& q) {
        std::vector<std::pair<float, std::size_t>> all;
        all.reserve(n);
        for (std::size_t i = 0; i < n; ++i) {
            float s = 0.0f;
            for (std::size_t d = 0; d < dim; ++d) {
                const float t = db[i][d] - q[d];
                s += t * t;
            }
            all.push_back({s, i});
        }
        std::sort(all.begin(), all.end());
        return all;
    };

    // —— 召回率 + 同机暴力对照耗时（同一批 query 都真实计时，不引用他例数据）——
    double recall_sum = 0.0;
    double hnsw_total_us = 0.0;
    double brute_total_us = 0.0;
    for (const auto& q : qs) {
        const auto tb0 = std::chrono::steady_clock::now();
        const auto gt = brute(q);
        const auto tb1 = std::chrono::steady_clock::now();
        brute_total_us += std::chrono::duration<double, std::micro>(tb1 - tb0).count();

        const auto t0 = std::chrono::steady_clock::now();
        const auto hits = index.search(q, k);
        const auto t1 = std::chrono::steady_clock::now();
        hnsw_total_us += std::chrono::duration<double, std::micro>(t1 - t0).count();

        std::size_t inter = 0;
        for (const auto& h : hits) {
            for (std::size_t j = 0; j < k; ++j) {
                if (h.id == gt[j].second) {
                    ++inter;
                    break;
                }
            }
        }
        recall_sum += static_cast<double>(inter) / static_cast<double>(k);
    }
    const double recall = recall_sum / static_cast<double>(nq);
    const double per_us = hnsw_total_us / static_cast<double>(nq);
    const double brute_per_us = brute_total_us / static_cast<double>(nq);
    std::cout << "[2] recall@" << k << " = " << recall * 100.0 << "%"
              << "（n=" << n << ", M=" << 8 << ", efC=64, efS=" << 48 << "）\n";
    std::cout << "[3] 同机同 query 实测: HNSW 平均 " << per_us << " µs/query, "
              << "brute force 平均 " << brute_per_us << " µs/query, "
              << "快 " << brute_per_us / per_us << "x（牺牲的是 100% → " << recall * 100.0
              << "% 召回率）\n";

    // —— 断言：近似的可验证性质（不是固定召回值，而是"高召回"与"不退化"）——
    if (recall < 0.90) {
        throw std::runtime_error("recall too low: toy HNSW 应 > 0.90（调参见主文档 3.4）");
    }
    // 正确性基础：返回的 top-1 距离必须 ≤ 暴力 ground truth 的第 k 远（不劣于全集抽样）
    {
        const auto gt0 = brute(qs[0]);
        const auto h0 = index.search(qs[0], k);
        if (h0.front().dist > gt0[k - 1].first + 1e-3f)
            throw std::runtime_error("hnsw top1 worse than brute top-k bound");
    }
    std::cout << "断言: recall≥0.90 ✓, top-1 不劣于暴力 top-k 界 ✓\n";
    std::cout << "ph23-ex04 OK\n";
    return 0;
}
