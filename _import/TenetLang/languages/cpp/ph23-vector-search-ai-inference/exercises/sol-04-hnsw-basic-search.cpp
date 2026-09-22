// sol-04-hnsw-basic-search.cpp —— 练习 4 参考实现：给定邻接图上的 ef 搜索 + 距离评估计量
// 对应 roadmap §23「实现 HNSW 的节点、邻接表和基础搜索流程」。与 examples/ex04 的分工：
//   ex04 是"完整 toy HNSW"（随机层高插入 + 多层图构建 + 搜索端到端）；
//   本解**跳过建图**（邻接用精确 kNN 预构建成"层 0 图"），聚焦 HNSW 搜索的核心机制——
//   候选集（最近者先扩展）+ 结果集（只留 ef 个最近）两个堆怎么配合、什么时候能停，
//   以及"图搜索把距离评估次数压到 N 的多少分之一"。
// 关键机制：
//   ① ef_search 循环：取候选堆顶 c（当前最近未扩展点）；若 c 比结果集最差还远 → 停
//      （因为候选堆是"距 query 近的先出"，此后只会更远，再扩展无意义）；
//   ② 否则扩展 c 的邻接表，对未访问邻居算距离，够格就进"结果集 + 候选集"；
//   ③ 计量每次 dist2 调用 = 距离评估次数（图搜索成本的直接观测）。
// 资源管理：纯 std::vector（R.11）。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -O2 -Wall -Wextra sol-04-hnsw-basic-search.cpp -o /tmp/ph23-sol04 && /tmp/ph23-sol04
// 验证状态：已验证（零警告、断言全绿、退出码 0）

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <queue>
#include <random>
#include <stdexcept>
#include <utility>
#include <vector>

namespace {

using node_id = std::uint32_t;

struct hit {
    node_id id;
    float dist;
};

class knn_graph {
public:
    knn_graph(const std::vector<std::vector<float>>& db, std::size_t neighbors)
        : db_(db), adj_(db.size()) {
        // 精确 kNN 建"层 0 图"（练习说明：构造不是本练习重点，用全对全粗建即可）
        std::vector<float> row_best;
        for (std::size_t i = 0; i < db_.size(); ++i) {
            std::vector<std::pair<float, std::size_t>> all;
            all.reserve(db_.size());
            for (std::size_t j = 0; j < db_.size(); ++j) {
                if (i == j) continue;
                all.push_back({dist2(db_[i].data(), db_[j].data()), j});
            }
            std::partial_sort(all.begin(), all.begin() + static_cast<std::ptrdiff_t>(neighbors),
                              all.end());
            for (std::size_t t = 0; t < neighbors; ++t)
                adj_[i].push_back(static_cast<node_id>(all[t].second));
        }
    }

    // ef 搜索：entry 为起点，返回 ef 个最近（排序后取 top），evals 输出距离评估次数
    std::vector<hit> ef_search(const std::vector<float>& q, node_id entry, std::size_t ef,
                               std::size_t* evals) const {
        std::vector<bool> visited(db_.size(), false);
        std::size_t e = 0;

        auto closer_first = [](const hit& x, const hit& y) { return x.dist > y.dist; };   // 候选：最小堆
        std::priority_queue<hit, std::vector<hit>, decltype(closer_first)> cand(closer_first);
        auto farther_first = [](const hit& x, const hit& y) { return x.dist < y.dist; };  // 结果：最大堆
        std::priority_queue<hit, std::vector<hit>, decltype(farther_first)> res(farther_first);

        auto touch = [&](node_id n) {
            ++e;
            const float d = dist2(db_[n].data(), q.data());
            if (res.size() < ef || d < res.top().dist) {
                res.push({n, d});
                if (res.size() > ef) res.pop();
            }
            return d;
        };

        visited[entry] = true;
        const float d0 = touch(entry);
        cand.push({entry, d0});

        while (!cand.empty()) {
            const hit cur = cand.top();
            cand.pop();
            if (cur.dist > res.top().dist) break;   // ★ 终止条件：最近的未扩展点已比结果集最差还远
            for (const node_id nb : adj_[cur.id]) {
                if (visited[nb]) continue;
                visited[nb] = true;
                const float d = dist2(db_[nb].data(), q.data());
                ++e;
                if (res.size() < ef || d < res.top().dist) {
                    res.push({nb, d});
                    if (res.size() > ef) res.pop();
                    cand.push({nb, d});
                }
            }
        }
        std::vector<hit> out;
        while (!res.empty()) {
            out.push_back(res.top());
            res.pop();
        }
        std::sort(out.begin(), out.end(),
                  [](const hit& a, const hit& b) { return a.dist < b.dist; });
        if (evals) *evals = e;
        return out;
    }

    std::size_t size() const { return db_.size(); }
    const std::vector<float>& vec(node_id i) const { return db_[i]; }
    std::size_t degree(node_id i) const { return adj_[i].size(); }

private:
    float dist2(const float* a, const float* b) const {
        float s = 0.0f;
        for (std::size_t d = 0; d < db_[0].size(); ++d) {
            const float t = a[d] - b[d];
            s += t * t;
        }
        return s;
    }
    const std::vector<std::vector<float>>& db_;
    std::vector<std::vector<node_id>> adj_;
};

void check(bool ok, const char* what) {
    if (!ok) throw std::runtime_error(std::string("ASSERT FAILED: ") + what);
}

}  // namespace

int main() {
    constexpr std::size_t dim = 16;
    constexpr std::size_t n = 4000;
    constexpr std::size_t nq = 100;
    constexpr std::size_t k = 10;

    std::mt19937 rng(555u);
    std::uniform_real_distribution<float> uni(0.0f, 1.0f);
    std::vector<std::vector<float>> db(n);
    for (auto& v : db) {
        v.resize(dim);
        for (auto& x : v) x = uni(rng);
    }
    std::vector<std::vector<float>> qs(nq);
    for (auto& q : qs) {
        q.resize(dim);
        for (auto& x : q) x = uni(rng);
    }

    knn_graph g(db, /*neighbors=*/8);
    std::cout << "[0] 建图完成: n=" << n << ", 每节点层0出度=" << g.degree(0)
              << "（该图作为「层0邻接」固定输入，下面只做搜索）\n";

    // ground truth + 三种 ef 的 (recall, 平均评估次数)
    struct row {
        std::size_t ef;
        double recall;
        double avg_evals;
    };
    std::vector<row> rows;
    for (const std::size_t ef : {1u, 8u, 64u}) {
        double recall_sum = 0.0, evals_sum = 0.0;
        for (std::size_t qi = 0; qi < nq; ++qi) {
            const auto& q = qs[qi];
            // ground truth（全扫）
            std::vector<std::pair<float, std::size_t>> all;
            for (std::size_t i = 0; i < n; ++i) {
                const auto& v = db[i];
                float s = 0.0f;
                for (std::size_t d = 0; d < dim; ++d) {
                    const float t = v[d] - q[d];
                    s += t * t;
                }
                all.push_back({s, i});
            }
            std::sort(all.begin(), all.end());

            std::size_t evals = 0;
            const auto hits = g.ef_search(q, static_cast<node_id>(qi % n), ef, &evals);
            std::size_t inter = 0;
            for (const auto& h : hits) {
                for (std::size_t j = 0; j < k; ++j) {
                    if (h.id == all[j].second) {
                        ++inter;
                        break;
                    }
                }
            }
            recall_sum += static_cast<double>(inter) / static_cast<double>(k);
            evals_sum += static_cast<double>(evals);
        }
        rows.push_back({ef, recall_sum / nq, evals_sum / nq});
        std::printf("[1] ef=%3zu: recall@10=%.4f, 平均距离评估 %8.1f 次 (= 全库 %.2f%%)\n",
                    ef, rows.back().recall, rows.back().avg_evals,
                    rows.back().avg_evals / n * 100.0);
    }

    // 断言
    check(rows[0].avg_evals < static_cast<double>(n) / 5.0,
          "ef=1 的评估次数应远小于 N（否则搜索退化成扫描）");
    check(rows[2].recall >= rows[0].recall - 1e-9, "recall 随 ef 不降");
    check(rows[2].recall > 0.8, "ef=64 召回应 > 0.8（kNN 图足够密）");
    check(rows[2].avg_evals < static_cast<double>(n),
          "图搜索评估次数应小于暴力全扫 N");
    std::cout << "[2] 断言: ef=1 评估 << N ✓; recall 随 ef 单调不减 ✓; ef=64 召回>0.8 ✓; "
                 "图搜索评估 < N ✓\n";
    std::cout << "ph23-sol04 OK\n";
    return 0;
}
