// sol-02-distance-triple.cpp —— 练习 2 参考实现：手写三种距离 + 数学性质断言
// 对应 roadmap §23「实现 L2 / cosine / inner product 三种距离计算」。
// 与 examples/ex01 的分工：ex01 讲"检索排序语义"；本解聚焦"数学性质验证"，
//   并故意构造"长度悬殊但方向相同"的向量演示 cosine 相对 IP 的长度不变性。
// 手写循环（练习要求不准用 std::inner_product）。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -O2 -Wall -Wextra sol-02-distance-triple.cpp -o /tmp/ph23-sol02 && /tmp/ph23-sol02
// 验证状态：已验证（零警告、断言全绿、退出码 0）

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace d3 {

using vec = std::vector<float>;

// —— 三种距离手写循环（各自独立，便于对照实现与讲解） ——

// L2 距离：√(∑(a-b)²)。几何意义 = 两点间直线长度。返回平方也可（排序等价）。
float l2(const vec& a, const vec& b) {
    if (a.size() != b.size()) throw std::invalid_argument("dim mismatch");
    float s = 0.0f;
    for (std::size_t i = 0; i < a.size(); ++i) {
        const float d = a[i] - b[i];
        s += d * d;
    }
    return std::sqrt(s);
}

// 内积 IP：∑a·b。代数意义 = |a||b|cosθ；同时编码"方向"与"长度"。
float ip(const vec& a, const vec& b) {
    if (a.size() != b.size()) throw std::invalid_argument("dim mismatch");
    float s = 0.0f;
    for (std::size_t i = 0; i < a.size(); ++i) s += a[i] * b[i];
    return s;
}

// 余弦相似度：IP(a,b) / (|a||b|)。只对"方向夹角"敏感，∈ [-1, 1]。
float cos_sim(const vec& a, const vec& b) {
    if (a.size() != b.size()) throw std::invalid_argument("dim mismatch");
    float na = 0.0f, nb = 0.0f, ab = 0.0f;
    for (std::size_t i = 0; i < a.size(); ++i) {
        ab += a[i] * b[i];
        na += a[i] * a[i];
        nb += b[i] * b[i];
    }
    if (na == 0.0f || nb == 0.0f) throw std::invalid_argument("zero vector");
    return ab / (std::sqrt(na) * std::sqrt(nb));
}

void check(bool ok, const std::string& what) {
    if (!ok) throw std::runtime_error("ASSERT FAILED: " + what);
}
void check_rel(float x, float y, float tol, const std::string& what) {
    if (std::fabs(x - y) > tol * std::max(1.0f, std::fabs(y)))
        throw std::runtime_error("ASSERT FAILED(rel): " + what);
}

}  // namespace d3

int main() {
    using namespace d3;
    const vec u{1.0f, 0.0f, 0.0f};      // 单位向量：方向 = x 轴
    const vec v{0.0f, 1.0f, 0.0f};      // 与之垂直
    const vec w{0.6f, 0.8f, 0.0f};      // 与 u 夹角 ~53°

    // [1] 几何性质断言
    check(l2(u, u) < 1e-6f, "L2(a,a)==0");
    check(l2(u, v) - std::sqrt(2.0f) < 1e-5f, "L2(u,v)==sqrt2");
    check(cos_sim(u, u) > 1.0f - 1e-6f, "cos(a,a)==1");
    check(std::fabs(cos_sim(u, v)) < 1e-6f, "cos(垂直)==0");
    check(std::fabs(cos_sim(u, w) - 0.6f) < 1e-5f, "cos(夹角53°)=0.6");

    // [2] 恒等式 |a-b|² = |a|²+|b|²-2a·b（两边都手写循环，验证两条实现路径一致）
    {
        const vec a{1.0f, -2.0f, 3.0f, 0.5f};
        const vec b{-1.5f, 2.0f, 1.0f, -2.5f};
        const float lhs = l2(a, b) * l2(a, b);
        const float rhs = ip(a, a) + ip(b, b) - 2.0f * ip(a, b);
        check_rel(lhs, rhs, 1e-4f, "恒等式 |a-b|²=|a|²+|b|²-2a·b");
        std::cout << "[2] 恒等式成立: " << lhs << " == " << rhs << " ✓\n";
    }

    // [3] 归一化后 IP == cosine（cos(a,b) == IP(â,b̂)）
    {
        const vec a{3.0f, 4.0f, 0.0f};        // 长度 5
        const vec b{-1.0f, 0.0f, 2.0f};
        auto normalize = [](const vec& x) {
            const float n = std::sqrt(ip(x, x));
            vec y(x.size());
            for (std::size_t i = 0; i < x.size(); ++i) y[i] = x[i] / n;
            return y;
        };
        const float c1 = cos_sim(a, b);
        const float c2 = ip(normalize(a), normalize(b));
        check_rel(c1, c2, 1e-5f, "归一化后 IP == cosine");
        std::cout << "[3] cos(a,b)=" << c1 << " ≈ IP(â,b̂)=" << c2 << " ✓\n";
    }

    // [4] 长度敏感性演示：u 与"方向同 u、长度×10"的长向量
    {
        vec long_u(u);
        for (auto& x : long_u) x *= 10.0f;    // 方向不变，长度×10
        const float ip_val = ip(u, long_u);   // 10（被长度放大）
        const float cos_val = cos_sim(u, long_u);  // 1.0（方向相同，不受长度影响）
        std::cout << "[4] 方向相同、长度×10: IP=" << ip_val << "（长度放大） vs cos="
                  << cos_val << "（方向唯一）—— 排序时 IP 偏好长向量，cosine 不会\n";
        check(std::fabs(cos_val - 1.0f) < 1e-6f, "cos 对长度不变");
        check(std::fabs(ip_val - 10.0f) < 1e-5f, "IP 正比于长度");
    }

    std::cout << "ph23-sol02 OK\n";
    return 0;
}
