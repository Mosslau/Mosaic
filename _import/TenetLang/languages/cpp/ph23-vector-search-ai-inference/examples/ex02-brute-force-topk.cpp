// ex02-brute-force-topk.cpp —— 暴力 topK 检索：全库线性扫 + 有序 top-k，附 QPS 实测
// 对应 ph23 主文档 3.2 与 roadmap §23「实现 brute-force vector search / 距离 benchmark」。
// 教学点：
//   ① 暴力检索（flat scan）的结构：对每一条库内向量算距离 → 维护当前 top-k；
//      "全库扫一遍、人人有机会"——召回率恒为 1.0（精确检索），代价是 O(N·D) 每查询；
//   ② top-k 维护用"容量 k 的最大堆"（堆顶 = 当前最差入选者），比全排序省内存与比较；
//   ③ 与 ground truth（std::partial_sort 全排序）逐位对照，验证 top-k 实现正确；
//   ④ 工程注意：距离计算是唯一热点 → 为 SIMD/内存布局优化留接口（ex03 接续）；
//      数据按"矩阵连续布局"（N×D 行主序）存放 → 逐行顺序访问，缓存友好；
//   ⑤ 实测输出 QPS / 平均单查询微秒（数据规模可复现；机器无关结论看加速比不看重数）。
// 资源管理：纯 std::vector（R.11），随机种子固定保证可复现。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -O2 -Wall -Wextra ex02-brute-force-topk.cpp -o /tmp/ph23-ex02 && /tmp/ph23-ex02
// 验证状态：已验证（零警告、断言全绿、退出码 0）

#include <algorithm>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <queue>
#include <random>
#include <vector>

namespace brute {

struct hit {            // 一条检索结果：id + 分数
    std::uint32_t id;
    float score;        // 越小越近（本示例统一用平方 L2）
};

// —— 核心：单 query 的 top-k ——
// 小顶堆换成"容量 k 的最大堆"：堆顶是当前第 k 差的候选，来了更好的就换掉它。
std::vector<hit> topk_l2(const float* db, std::size_t n, std::size_t dim,
                         const float* q, std::size_t k) {
    using pq_elt = std::pair<float, std::uint32_t>;  // (距离, id)，默认大顶堆在距离上
    std::priority_queue<pq_elt> pq;                  // 距离最大的在堆顶 → 可"淘汰最差"
    for (std::uint32_t i = 0; i < static_cast<std::uint32_t>(n); ++i) {
        const float* row = db + static_cast<std::size_t>(i) * dim;
        float s = 0.0f;
        for (std::size_t d = 0; d < dim; ++d) {
            const float t = row[d] - q[d];
            s += t * t;
        }
        if (pq.size() < k) {
            pq.push({s, i});
        } else if (s < pq.top().first) {
            pq.pop();
            pq.push({s, i});
        }
    }
    std::vector<hit> out;
    out.reserve(pq.size());
    while (!pq.empty()) {
        out.push_back({pq.top().second, pq.top().first});
        pq.pop();
    }
    std::reverse(out.begin(), out.end());  // 由近到远
    return out;
}

}  // namespace brute

int main() {
    using namespace brute;
    // —— 数据规模：可复现；单机演示用，非 benchmark 结论的绝对值依据 ——
    constexpr std::size_t dim = 64;
    constexpr std::size_t n = 5000;      // 库内向量数
    constexpr std::size_t nq = 200;      // 查询数
    constexpr std::size_t k = 10;

    std::mt19937 rng(7u);
    std::normal_distribution<float> gauss(0.0f, 1.0f);

    std::vector<float> db(n * dim);
    for (auto& x : db) x = gauss(rng);
    std::vector<float> qs(nq * dim);
    for (auto& x : qs) x = gauss(rng);

    // [1] 正确性对照：取一个 query，与"全排序 ground truth"逐位比对
    {
        const float* q = qs.data();
        std::vector<std::pair<float, std::size_t>> all;
        all.reserve(n);
        for (std::size_t i = 0; i < n; ++i) {
            const float* row = db.data() + i * dim;
            float s = 0.0f;
            for (std::size_t d = 0; d < dim; ++d) {
                const float t = row[d] - q[d];
                s += t * t;
            }
            all.push_back({s, i});
        }
        std::partial_sort(all.begin(), all.begin() + static_cast<std::ptrdiff_t>(k), all.end());
        const auto got = topk_l2(db.data(), n, dim, q, k);
        if (got.size() != k) throw std::runtime_error("topk size");
        for (std::size_t j = 0; j < k; ++j) {
            if (got[j].id != all[j].second || std::abs(got[j].score - all[j].first) > 1e-3f) {
                throw std::runtime_error("topk mismatch at " + std::to_string(j));
            }
        }
        std::cout << "[1] top-k 与全排序 ground truth 完全一致（top-1 id=" << got[0].id
                  << ", dist=" << got[0].score << "）✓\n";
    }

    // [2] 批量检索 + QPS 实测（-O2 编译；数字为参考值，加速比看 ex03）
    {
        const auto t0 = std::chrono::steady_clock::now();
        std::size_t total_ids = 0;  // 用掉结果防止编译器消去（Per.6：不优化没数据支持）
        for (std::size_t qi = 0; qi < nq; ++qi) {
            const auto r = topk_l2(db.data(), n, dim, qs.data() + qi * dim, k);
            total_ids += r.front().id;
        }
        const auto t1 = std::chrono::steady_clock::now();
        const double us = std::chrono::duration<double, std::micro>(t1 - t0).count();
        const double per_q_us = us / static_cast<double>(nq);
        const double qps = static_cast<double>(nq) * 1e6 / us;
        std::cout << "[2] brute force n=" << n << " dim=" << dim << " topk=" << k << ", "
                  << nq << " 次查询: 平均 " << per_q_us << " µs/query, " << qps << " QPS"
                  << " (总校验和 " << total_ids << ")\n";
    }

    // [3] topk 的堆大小对比：全排序 vs top-k 堆扫描的比较次数只是数量级概念，
    //     此处用同一个 query 重跑 k=1..50，展示堆的 top-k 维护代价随 k 增长平缓。
    {
        const float* q = qs.data();
        for (std::size_t kk : {1u, 10u, 50u}) {
            const auto r = topk_l2(db.data(), n, dim, q, kk);
            std::cout << "[3] k=" << kk << " → top-1 id=" << r.front().id
                      << " dist=" << r.front().score << '\n';
        }
    }

    std::cout << "ph23-ex02 OK\n";
    return 0;
}
