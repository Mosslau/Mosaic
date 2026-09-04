// sol-03-distance-bench-simd.cpp —— 练习 3 参考实现：距离函数 benchmark + SIMD 优化
// 对应 roadmap §23「为距离计算写 benchmark 并尝试 SIMD 优化」。
// 与 examples/ex03 的分工：ex03 用 128 维、展示"三形态对比方法论"；本解**故意用非 4 倍数
// 维度 150**，验证手写 NEON 的"向量主体 + 标量尾部"收尾正确性（越界/漏算都逃不过断言），
// 并要求同一基准函数提供 double 参考实现做精度锚点。
// 正确性断言：double 参考 vs 标量 vs NEON 逐元素（前 64 对）相对误差 < 1e-5；
//   若尾部收尾写错（如忘记最后 2 维），NEON 结果必然偏离参考 → 断言当场失败。
// 编译运行（三种形态，观察同份代码不同构建）：
//   1) 标量基线 + 手写 NEON:
//        clang++ -std=c++20 -O2 -Wall -Wextra sol-03-distance-bench-simd.cpp -o /tmp/ph23-sol03o2 && /tmp/ph23-sol03o2
//   2) 同代码 -O2 + Homebrew clang 交叉核对:
//        /opt/homebrew/opt/llvm/bin/clang++ -std=c++20 -O2 -Wall -Wextra sol-03-distance-bench-simd.cpp -o /tmp/ph23-sol03hb && /tmp/ph23-sol03hb
//   3) 自动向量化形态（-O3 -ffast-math 允许重结合 → 标量循环被 LLVM 向量化）:
//        clang++ -std=c++20 -O3 -ffast-math sol-03-distance-bench-simd.cpp -o /tmp/ph23-sol03o3 && /tmp/ph23-sol03o3
//   x86 说明：把手写段换成 AVX2（_mm256_load_ps/_mm256_fmadd_ps），编译加 -mavx2 -mfma；
//   本机 arm64 不验证该命令。
// 验证状态：已验证（三种形态零警告、断言全绿；Apple clang 21.0.0 与 Homebrew clang 21.1.8）

#include <arm_neon.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdio>
#include <cstdlib>
#include <vector>

namespace dbench {

// —— 三种实现 ——
float l2_scalar(const float* a, const float* b, std::size_t dim) {  // 串行依赖链
    float sum = 0.0f;
    for (std::size_t i = 0; i < dim; ++i) {
        const float d = a[i] - b[i];
        sum += d * d;
    }
    return sum;
}

double l2_double(const float* a, const float* b, std::size_t dim) {  // 精度锚点
    double sum = 0.0;
    for (std::size_t i = 0; i < dim; ++i) {
        const double d = static_cast<double>(a[i]) - static_cast<double>(b[i]);
        sum += d * d;
    }
    return sum;
}

#if defined(__ARM_NEON)
float l2_neon(const float* a, const float* b, std::size_t dim) {
    float32x4_t acc = vdupq_n_f32(0.0f);
    std::size_t i = 0;
    // 主体：一次 4 维。dim=150 → 走 37 轮 = 148 维
    for (; i + 4 <= dim; i += 4) {
        const float32x4_t va = vld1q_f32(a + i);
        const float32x4_t vb = vld1q_f32(b + i);
        const float32x4_t d = vsubq_f32(va, vb);
        acc = vfmaq_f32(acc, d, d);
    }
    // 水平归约
    const float32x2_t lo = vget_low_f32(acc);
    const float32x2_t hi = vget_high_f32(acc);
    const float32x2_t s = vpadd_f32(lo, hi);
    float r = vget_lane_f32(vpadd_f32(s, s), 0);
    // 尾部：150 - 148 = 2 维 —— 若忘记这段，结果会差"最后 2 维"，断言立刻抓住
    for (; i < dim; ++i) {
        const float d = a[i] - b[i];
        r += d * d;
    }
    return r;
}
#else
#error "NEON 段仅适用于 arm64；x86 请按文件头注释换 AVX2"
#endif

volatile float g_sink = 0.0f;

template <typename Fn>
double bench(Fn fn, const float* x, const float* y, std::size_t dim, std::size_t rows,
             std::size_t reps, const char* name) {
    constexpr int k_rounds = 7;
    for (int r = 0; r < 2; ++r)
        for (std::size_t i = 0; i < rows; ++i) g_sink += fn(x + i * dim, y + i * dim, dim);
    std::vector<double> samples;
    samples.reserve(k_rounds);
    const std::size_t ops = rows * reps;
    for (int r = 0; r < k_rounds; ++r) {
        const auto t0 = std::chrono::steady_clock::now();
        for (std::size_t t = 0; t < reps; ++t)
            for (std::size_t i = 0; i < rows; ++i) g_sink += fn(x + i * dim, y + i * dim, dim);
        const auto t1 = std::chrono::steady_clock::now();
        const double ns = std::chrono::duration<double, std::nano>(t1 - t0).count();
        samples.push_back(ns / static_cast<double>(ops));
    }
    std::sort(samples.begin(), samples.end());
    const double med = samples[k_rounds / 2];
    std::printf("%-12s 中位 %8.2f ns/op   %6.2f GFLOPS/s\n", name, med,
                (2.0 * static_cast<double>(dim)) / (med * 1e-9) / 1e9);
    return med;
}

}  // namespace dbench

int main() {
    using namespace dbench;
    constexpr std::size_t dim = 150;   // 故意非 4 的倍数：练尾部收尾
    constexpr std::size_t rows = 2048; // 2×2048×150×4B ≈ 2.5MB，压 L2 内
    constexpr std::size_t reps = 1024; // 每轮样本 ≈ 2.1M 对

    std::vector<float> x(dim * rows), y(dim * rows);
    for (std::size_t i = 0; i < x.size(); ++i) {
        x[i] = static_cast<float>(std::rand() % 1000) / 100.0f;
        y[i] = static_cast<float>(std::rand() % 1000) / 100.0f;
    }

    // [1] 正确性：double 锚点 vs scalar vs neon（逐对验证前 64 对）
    {
        for (std::size_t i = 0; i < 64; ++i) {
            const float* a = x.data() + i * dim;
            const float* b = y.data() + i * dim;
            const double ref = l2_double(a, b, dim);
            const double sc = static_cast<double>(l2_scalar(a, b, dim));
            const double ne = static_cast<double>(l2_neon(a, b, dim));
            auto rel = [](double v, double r) { return std::fabs(v - r) / std::max(1.0, std::fabs(r)); };
            if (rel(sc, ref) > 1e-5 || rel(ne, ref) > 1e-5)
                throw std::runtime_error("正确性: 尾部收尾疑似写错（参考第 i=" +
                                         std::to_string(i) + " 行）");
        }
        std::printf("[1] 正确性: dim=%zu（非 4 倍数）标量/NEON 与 double 参考一致 ✓\n", dim);
    }

    // [2] 计时（L2 内数据，测计算速度）
    std::printf("[2] dim=%zu rows=%zu（约 %zuKB，L2 内）:\n", dim, rows,
                2 * dim * rows * 4 / 1024);
    const double m_sc = bench(l2_scalar, x.data(), y.data(), dim, rows, reps, "l2_scalar");
    const double m_ne = bench(l2_neon, x.data(), y.data(), dim, rows, reps, "l2_neon");
    std::printf("    加速比 scalar/neon = %.2fx\n", m_sc / m_ne);

    // [3] 把数据规模放大到远超 L2（如 100MB 级），观察 SIMD 加速比被内存带宽"压扁"
    {
        constexpr std::size_t big_rows = 400000;   // 2×400000×150×4B ≈ 480MB
        std::vector<float> bx(big_rows * dim), by(big_rows * dim);
        for (std::size_t i = 0; i < bx.size(); ++i) {
            bx[i] = static_cast<float>(std::rand() % 1000) / 100.0f;
            by[i] = static_cast<float>(std::rand() % 1000) / 100.0f;
        }
        std::printf("[3] 放大到 %zuMB（远超缓存，测内存带宽受限形态）:\n",
                    static_cast<std::size_t>(2 * big_rows * dim * 4 / 1048576));
        // 只跑一轮完整扫描取耗时（数据太大，做 3 轮中位数控制总时长）
        double best_sc = 1e30, best_ne = 1e30;
        for (int r = 0; r < 3; ++r) {
            auto t0 = std::chrono::steady_clock::now();
            for (std::size_t i = 0; i < big_rows; ++i) g_sink += l2_scalar(bx.data() + i * dim, by.data() + i * dim, dim);
            auto t1 = std::chrono::steady_clock::now();
            best_sc = std::min(best_sc, std::chrono::duration<double, std::milli>(t1 - t0).count());
            t0 = std::chrono::steady_clock::now();
            for (std::size_t i = 0; i < big_rows; ++i) g_sink += l2_neon(bx.data() + i * dim, by.data() + i * dim, dim);
            t1 = std::chrono::steady_clock::now();
            best_ne = std::min(best_ne, std::chrono::duration<double, std::milli>(t1 - t0).count());
        }
        std::printf("    全量扫 40 万行: scalar=%.1fms, neon=%.1fms, 加速比=%.2fx"
                    "（远超缓存：是否仍被 SIMD 加速取决于标量侧是否先被内存带宽压制，"
                    "以本行实测为准）\n", best_sc, best_ne, best_sc / best_ne);
    }
    std::printf("ph23-sol03 OK (sink=%f)\n", static_cast<double>(g_sink));
    return 0;
}
