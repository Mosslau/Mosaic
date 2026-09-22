// vec_index_core.h —— C++ 核心：brute-force 向量索引（纯 C++，不出任何二进制边界）
// 验证环境：Apple clang 21.0.0（C++20）
// 验证状态：已验证（经 C 包装层 + C 驱动 + Python ctypes 双侧实测）
// 边界声明：这是「玩具级」最近邻库——只做暴力线性扫描 + L2 距离，无 ANN 近似索引、
//           无 SIMD、无持久化、无并发；真实向量库的 HNSW/IVF-PQ/SIMD 属于 roadmap
//           第 23 节向量检索与 AI 推理引擎方向（目录待建）。本项目唯一目的是把
//           ph20 的 C ABI + 绑定纪律在「一个 Python 能调的小向量库」上完整走一遍。
#ifndef VEC_INDEX_CORE_H
#define VEC_INDEX_CORE_H

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <utility>
#include <vector>

namespace vindex {

struct item {
    std::int64_t id;
    std::vector<float> v;
};

struct score_t {
    float dist;  // 平方 L2 距离（squared L2：不做 sqrt，单调序与欧氏距离一致，Faiss 同惯例）
    std::int64_t id;
};

class flat_index {
public:
    explicit flat_index(std::int64_t dim) : dim_(dim) {
        if (dim <= 0) throw std::invalid_argument("dim must be positive");
    }

    void add(std::int64_t id, const float* v, std::int64_t dim) {
        if (v == nullptr) throw std::invalid_argument("null vector");
        if (dim != dim_) throw std::invalid_argument("dim mismatch");
        items_.push_back(item{id, std::vector<float>(v, v + dim_)});
    }

    std::size_t size() const { return items_.size(); }

    std::int64_t dim() const { return dim_; }

    // 暴力扫描：stable_sort 保证等距时按插入序（驱动测试依赖它做确定性断言）
    std::vector<score_t> search(const float* q, std::int64_t dim,
                                std::size_t topk) const {
        if (q == nullptr) throw std::invalid_argument("null query");
        if (dim != dim_) throw std::invalid_argument("dim mismatch");
        if (items_.empty()) throw std::runtime_error("index is empty");

        std::vector<score_t> all;
        all.reserve(items_.size());
        for (const auto& it : items_) {
            float acc = 0.0f;
            for (std::int64_t i = 0; i < dim_; ++i) {
                const float d = it.v[i] - q[i];
                acc += d * d;
            }
            all.push_back(score_t{acc, it.id});
        }
        std::stable_sort(all.begin(), all.end(),
                         [](const score_t& a, const score_t& b) { return a.dist < b.dist; });
        const std::size_t n = topk < all.size() ? topk : all.size();
        all.resize(n);
        return all;
    }

private:
    std::int64_t dim_;
    std::vector<item> items_;
};

}  // namespace vindex

#endif  // VEC_INDEX_CORE_H
