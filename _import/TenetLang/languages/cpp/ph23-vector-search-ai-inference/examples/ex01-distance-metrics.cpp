// ex01-distance-metrics.cpp —— L2 / Inner Product / Cosine 三种距离度量的定义、换算与适用语义
// 对应 ph23 主文档 3.1 与 roadmap §23「实现 L2 / cosine / inner product 三种距离计算」。
// 教学点：
//   ① 三种度量的数学定义与代码形态：L2 是"几何距离"，Inner Product 是"方向×长度"，
//      Cosine 只关心方向（长度归一后与 IP 排序等价）；
//   ② 换算关系：|a-b|^2 = |a|^2 + |b|^2 - 2(a·b)；cos(a,b) = (a·b) / (|a||b|)；
//   ③ "归一化后 L2 与 IP 排序同序"的实证：先 L2 归一化再把两个不同 query 分别按
//      l2 / ip / cos 排序，观察三种排序 top 是否一致；
//   ④ 工程注记：检索"相似度"通常取分数越大越相似（IP/Cosine），L2 越小越近；
//      浮点累积差异用相对误差断言（教学演示不依赖逐位相等）。
// 资源管理：纯 std::vector，无裸指针（cpp-coding-standards R.11）。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -Wall -Wextra ex01-distance-metrics.cpp -o /tmp/ph23-ex01 && /tmp/ph23-ex01
// 验证状态：已验证（零警告、断言全绿、退出码 0）

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <iostream>
#include <numeric>
#include <random>
#include <string>
#include <vector>

namespace dist {

using vec = std::vector<float>;

// —— 三种距离/相似度（输入为两个同维度数组）——
// 平方 L2：∑(a-b)^2。越小越"近"。工程上多返回平方距离省一次 sqrt（排序等价）。
float l2_sq(const vec& a, const vec& b) {
    if (a.size() != b.size()) throw std::invalid_argument("dim mismatch");
    float s = 0.0f;
    for (std::size_t i = 0; i < a.size(); ++i) {
        const float d = a[i] - b[i];
        s += d * d;
    }
    return s;
}

// Inner Product：∑a·b。越大越"相似"。注意它同时奖励"方向对"与"长度长"——
// 这就是为什么不做归一化时，IP 排序会被长向量的"长度分"主导（见 main 对比）。
float inner_product(const vec& a, const vec& b) {
    if (a.size() != b.size()) throw std::invalid_argument("dim mismatch");
    return std::inner_product(a.begin(), a.end(), b.begin(), 0.0f);
}

// Cosine 相似度：(a·b)/(|a||b|)，范围 [-1, 1]，只对"方向"敏感。
// 工程做法通常是"先 L2 归一化再算 IP"（cos = â·b̂），省每次除法。
float cosine(const vec& a, const vec& b) {
    const float na = std::sqrt(std::inner_product(a.begin(), a.end(), a.begin(), 0.0f));
    const float nb = std::sqrt(std::inner_product(b.begin(), b.end(), b.begin(), 0.0f));
    if (na == 0.0f || nb == 0.0f) throw std::invalid_argument("zero vector");
    return inner_product(a, b) / (na * nb);
}

// L2 归一化：v → v/|v|。归一化后：l2_sq(a,b) = 2 - 2·cos(a,b)，
// 即"按 L2 由近到远"等价于"按 Cosine 由大到小"（排序同序）。
vec l2_normalize(const vec& v) {
    const float n = std::sqrt(std::inner_product(v.begin(), v.end(), v.begin(), 0.0f));
    if (n == 0.0f) throw std::invalid_argument("zero vector");
    vec out(v.size());
    for (std::size_t i = 0; i < v.size(); ++i) out[i] = v[i] / n;
    return out;
}

// 冒烟断言：把"断言失败即抛"包成一个小助手（demo 不引第三方测试框架）
void check(bool cond, const std::string& what) {
    if (!cond) throw std::runtime_error("ASSERT FAILED: " + what);
}

}  // namespace dist

int main() {
    using namespace dist;
    // 固定随机种子 → 结果可复现
    std::mt19937 rng(42u);
    std::uniform_real_distribution<float> uni(-1.0f, 1.0f);
    auto rand_vec = [&](std::size_t dim) {
        vec v(dim);
        for (auto& x : v) x = uni(rng);
        return v;
    };

    const vec q = rand_vec(8);
    const vec a = rand_vec(8);
    const vec b = rand_vec(8);

    // [1] 三种度量直接计算
    const float l2 = l2_sq(q, a);
    const float ip = inner_product(q, a);
    const float cs = cosine(q, a);
    std::cout << "[1] q·a: l2_sq=" << l2 << " ip=" << ip << " cos=" << cs << '\n';

    // [2] 换算关系（几何恒等式）：
    //    |a-b|^2 = |a|^2 + |b|^2 - 2(a·b)
    {
        const float na = inner_product(a, a);
        const float nb = inner_product(b, b);
        const float rhs = na + nb - 2.0f * inner_product(a, b);
        const float lhs = l2_sq(a, b);
        check(std::fabs(lhs - rhs) < 1e-3f * std::max(1.0f, rhs),
              "l2^2 == |a|^2+|b|^2-2(a·b)");
        std::cout << "[2] 恒等式 |a-b|^2=|a|^2+|b|^2-2(a·b): lhs=" << lhs
                  << " rhs=" << rhs << " ✓\n";
    }

    // [3] 归一化后 IP == Cosine：对同一对向量断言两者接近
    {
        const vec a_hat = l2_normalize(a);
        const vec b_hat = l2_normalize(b);
        const float ip_norm = inner_product(a_hat, b_hat);
        check(std::fabs(ip_norm - cosine(a, b)) < 1e-4f, "cos == ip(a_hat,b_hat)");
        std::cout << "[3] cos(a,b)=" << cosine(a, b) << " ≈ ip(a_hat,b_hat)=" << ip_norm << " ✓\n";
    }

    // [4] 归一化让"IP 排序"与"Cosine 排序"同序（检索语义的关键实验）：
    //     建一个库，观察同一 query 下三种排序的 top-3 是否一致。
    {
        constexpr std::size_t n = 200;
        std::vector<vec> db;
        for (std::size_t i = 0; i < n; ++i) {
            vec v = rand_vec(8);
            // 故意让部分向量"很长"：不归一化时 IP 会偏好它们（长度作弊）
            if (i % 4 == 0) for (auto& x : v) x *= 3.0f;
            db.push_back(v);
        }

        // 对原始库排序（cos 与 ip 会打架：长向量 ip 大但 cos 未必大）
        const vec q2 = rand_vec(8);
        const auto order_by = [&](auto score) {
            std::vector<std::size_t> idx(n);
            std::iota(idx.begin(), idx.end(), 0u);
            // 分数越小越靠前统一处理：l2 用原值，ip/cos 取负
            std::partial_sort(idx.begin(), idx.begin() + 3, idx.end(),
                              [&](std::size_t x, std::size_t y) { return score(x) < score(y); });
            return std::vector<std::size_t>(idx.begin(), idx.begin() + 3);
        };
        const auto top_by_l2 = order_by([&](std::size_t i) { return l2_sq(q2, db[i]); });
        const auto top_by_ip = order_by([&](std::size_t i) { return -inner_product(q2, db[i]); });
        const auto top_by_cos = order_by([&](std::size_t i) { return -cosine(q2, db[i]); });

        auto same = [](const std::vector<std::size_t>& x,
                       const std::vector<std::size_t>& y) { return x == y; };
        std::cout << "[4] 未归一化库 top3 对比: l2=[" << top_by_l2[0] << "," << top_by_l2[1]
                  << "," << top_by_l2[2] << "] ip=[" << top_by_ip[0] << "," << top_by_ip[1]
                  << "," << top_by_ip[2] << "] cos=[" << top_by_cos[0] << "," << top_by_cos[1]
                  << "," << top_by_cos[2] << "]\n";
        check(!same(top_by_l2, top_by_ip) || !same(top_by_ip, top_by_cos),
              "原始库上 ip 与 cos 排序不必相同（长度干扰）——若全同只是运气");

        // 归一化库：l2、ip、cos 三排序应同序
        std::vector<vec> norm_db;
        for (const auto& v : db) norm_db.push_back(l2_normalize(v));
        const vec q_hat = l2_normalize(q2);
        const auto top_nl2 = order_by([&](std::size_t i) { return l2_sq(q_hat, norm_db[i]); });
        const auto top_nip = order_by([&](std::size_t i) { return -inner_product(q_hat, norm_db[i]); });
        const auto top_ncos = order_by([&](std::size_t i) { return -cosine(q_hat, norm_db[i]); });
        std::cout << "[4] 归一化库 top3: l2=[" << top_nl2[0] << "," << top_nl2[1]
                  << "," << top_nl2[2] << "] ip=[" << top_nip[0] << "," << top_nip[1]
                  << "," << top_nip[2] << "] cos=[" << top_ncos[0] << "," << top_ncos[1]
                  << "," << top_ncos[2] << "]\n";
        check(same(top_nl2, top_nip) && same(top_nip, top_ncos),
              "L2 归一化后三种排序同序");
        std::cout << "      归一化后 l2/ip/cos 排序一致 ✓（这正是 Faiss IndexFlatIP + 归一化替代余弦的根据）\n";
    }

    std::cout << "ph23-ex01 OK\n";
    return 0;
}
