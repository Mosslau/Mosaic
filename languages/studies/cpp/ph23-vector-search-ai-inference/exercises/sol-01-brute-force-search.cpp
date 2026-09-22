// sol-01-brute-force-search.cpp —— 练习 1 参考实现：flat 检索类 + top-k 最大堆
// 对应 roadmap §23「实现 brute-force vector search」。与 examples/ex02 的分工：
//   ex02 是"过程式 + 固定数据集"的教学骨架；本解做成带 add/search 的类，
//   自定义数据集与边界断言（练习要求不照抄 ex02）。
// 关键设计：
//   ① 连续行主序矩阵（Per.19：距离计算顺序访问最友好）+ 独立 id 向量；
//   ② top-k = 容量 k 的最大堆：堆顶是"当前第 k 差"，新距离更小就替换；
//   ③ 距离评估计数（可观测"暴力检索到底算了几次距离"）。
// 资源管理：纯 std::vector 持有（R.11）。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -O2 -Wall -Wextra sol-01-brute-force-search.cpp -o /tmp/ph23-sol01 && /tmp/ph23-sol01
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

class flat_index {
public:
    struct hit {
        std::uint64_t id;
        float dist2;
    };

    explicit flat_index(std::size_t dim) : dim_(dim) {}

    void add(std::uint64_t id, const std::vector<float>& v) {
        if (v.size() != dim_) throw std::invalid_argument("dim mismatch");
        ids_.push_back(id);
        for (const float x : v) data_.push_back(x);
    }

    std::size_t size() const { return ids_.size(); }

    // 暴力 top-k：返回 (id, 平方 L2)，由近到远；dist_evals 输出距离评估次数
    std::vector<hit> search(const std::vector<float>& q, std::size_t k,
                            std::size_t* dist_evals) const {
        if (q.size() != dim_) throw std::invalid_argument("dim mismatch");
        if (ids_.empty()) return {};
        if (k == 0) return {};
        const std::size_t kk = std::min(k, ids_.size());   // 边界：k 大于库容量

        using elt = std::pair<float, std::uint64_t>;
        std::priority_queue<elt> worst_first;              // 堆顶 = 当前第 k 差
        std::size_t evals = 0;
        for (std::size_t i = 0; i < ids_.size(); ++i) {
            const float* row = data_.data() + i * dim_;
            float s = 0.0f;
            for (std::size_t d = 0; d < dim_; ++d) {
                const float t = row[d] - q[d];
                s += t * t;
            }
            ++evals;
            if (worst_first.size() < kk) {
                worst_first.push({s, ids_[i]});
            } else if (s < worst_first.top().first) {
                worst_first.pop();
                worst_first.push({s, ids_[i]});
            }
        }
        if (dist_evals) *dist_evals = evals;

        std::vector<hit> out;
        out.reserve(worst_first.size());
        while (!worst_first.empty()) {
            out.push_back({worst_first.top().second, worst_first.top().first});
            worst_first.pop();
        }
        std::reverse(out.begin(), out.end());              // 由近到远
        return out;
    }

private:
    std::size_t dim_;
    std::vector<std::uint64_t> ids_;
    std::vector<float> data_;                              // ids_.size()×dim_ 行主序
};

namespace {

// 全排序 ground truth
std::vector<flat_index::hit> truth(const flat_index& idx, const std::vector<float>& q) {
    std::size_t evals = 0;
    return idx.search(q, static_cast<std::size_t>(-1), &evals);
}

std::vector<float> rvec(std::size_t dim, std::mt19937& rng) {
    std::uniform_real_distribution<float> uni(-1.0f, 1.0f);
    std::vector<float> v(dim);
    for (auto& x : v) x = uni(rng);
    return v;
}

void check(bool ok, const char* what) {
    if (!ok) throw std::runtime_error(std::string("ASSERT FAILED: ") + what);
}

}  // namespace

int main() {
    constexpr std::size_t dim = 24;
    constexpr std::size_t n = 3000;
    constexpr std::size_t k = 15;

    std::mt19937 rng(12345u);
    flat_index idx(dim);
    for (std::size_t i = 0; i < n; ++i) {
        idx.add(9000 + i, rvec(dim, rng));   // 从 9000 起的 id，验证 id 映射不被行号污染
    }

    // [1] 正确性：3 个 query 与全排序 ground truth 逐位对照
    for (int qi = 0; qi < 3; ++qi) {
        const auto q = rvec(dim, rng);
        const auto gt = truth(idx, q);
        const auto got = idx.search(q, k, nullptr);
        check(got.size() == k, "top-k 个数");
        for (std::size_t j = 0; j < k; ++j) {
            check(got[j].id == gt[j].id, "id 与 ground truth 一致");
            check(std::fabs(got[j].dist2 - gt[j].dist2) < 1e-3f, "距离一致");
        }
    }
    std::cout << "[1] 3 个 query 的 top-" << k << " 与全排序 ground truth 完全一致 ✓\n";

    // [2] 边界：k 大于库容量 → 返回全部；空库 → 不崩溃
    {
        const auto q = rvec(dim, rng);
        const auto all = idx.search(q, n + 100, nullptr);
        check(all.size() == n, "k>N 时返回全部");
        flat_index empty(dim);
        check(empty.search(q, 5, nullptr).empty(), "空库查询返回空");
        std::cout << "[2] k>N 返回全部 " << all.size() << " 条；空库查询安全 ✓\n";
    }

    // [3] 距离评估次数 == 库条数（暴力检索的可观测成本，给练习 4 当对照基线）
    {
        const auto q = rvec(dim, rng);
        std::size_t evals = 0;
        (void)idx.search(q, 5, &evals);
        check(evals == n, "每次 query 恰好评估 N 次距离");
        std::cout << "[3] 暴力检索距离评估次数 = 库条数 " << evals << "（100% 全扫）✓\n";
    }

    std::cout << "ph23-sol01 OK\n";
    return 0;
}
