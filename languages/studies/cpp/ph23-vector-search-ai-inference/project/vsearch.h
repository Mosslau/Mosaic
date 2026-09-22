// vsearch.h —— ph23 project：SIMD 加速的 brute-force 向量检索库 + 快照持久化（接口层）
// 对应 roadmap §23「推荐项目」落地选择：brute-force vector search（工程化）+ SIMD 距离计算
//   + 向量索引持久化 demo 三合一。其余推荐项目去向见 project/README。
// 设计要点：
//   - 纯接口头文件；实现（距离内核/快照格式/NEON 路径）全部在 vsearch.cpp，调用方不感知；
//   - 快照格式与 examples/ex06 同源（ph22 SSTable 心智：定长 header + id 表 + 行主序矩阵
//     + 整文件校验尾；写 = temp + fsync + rename），本头只暴露 save/load；
//   - 资源管理：pimpl 用 std::unique_ptr（R.20），数据全 std::vector（R.11）；
//   - 线程安全：单线程使用（与 ph22 project 同教学口径，README 注明）。
// 时间语义：search 单次查询 O(N·D)（精确检索，召回恒为 1），瓶颈=距离内核 → SIMD 目标。
#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace vsearch {

enum class metric { l2 = 0, ip = 1, cosine = 2 };

struct result {
    std::int64_t id;
    float score;   // 用户面语义：l2 → 平方 L2（越小越近）；ip/cosine → 相似度（越大越近）
};

class flat_index {
public:
    flat_index(std::size_t dim, metric m);
    ~flat_index();
    flat_index(const flat_index&) = delete;
    flat_index& operator=(const flat_index&) = delete;
    flat_index(flat_index&&) noexcept;
    flat_index& operator=(flat_index&&) noexcept;

    void add(std::int64_t id, const std::vector<float>& v);
    std::size_t size() const noexcept;
    std::size_t dim() const noexcept;
    const char* metric_name() const noexcept;
    std::size_t memory_bytes() const noexcept;   // 内存账本：向量数据 + id 表 + 范数 + 结构开销

    std::vector<result> search(const std::vector<float>& q, std::size_t k) const;

    void save(const std::string& path) const;          // 快照：temp + fsync + rename
    static flat_index load(const std::string& path);   // 载入 + 整文件校验

private:
    struct impl;
    std::unique_ptr<impl> p_;
};

}  // namespace vsearch
