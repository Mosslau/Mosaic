// project/main.cpp —— ph18 综合项目：向量距离计算性能对比（L2 暴力扫描）
// 对应 roadmap §18 推荐项目「向量距离计算性能对比」。
// 目标：在同一个 128 维 float 向量库上实现「全量 L2 距离 + 取最近邻」的四种写法，
// 用一致的测时框架产出每百万次距离计算的耗时与吞吐表，先测量再谈优化：
//   ① 朴素标量（单累加器）：正确性基线
//   ② 4 路独立累加器：拆依赖链（examples/ex05 ③ 的手法）
//   ③ NEON intrinsics（arm64）：布局连续 + 并行度同时到位（x86 下退化为 ②）
// 距离语义对全部实现一致：∑(q_i - c_i)²，逐向量取最小；跨实现最近邻索引必须相同。
// 教学边界：本项目只做「同一布局上的实现技术对比」；AoS/SoA 布局维度的对比与
// 细节已由 examples/ex05 覆盖（见主文档 3.8），多线程分块见 README 扩展方向。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++（C++20）
// 编译：make  （或单行：clang++ -std=c++20 -O3 -Wall -Wextra main.cpp -o build/vec_bench）
// 运行：make run 或 ./build/vec_bench   测试：make test 或 ./build/vec_bench --selftest
// 验证状态：已验证（双编译器 -O3 实测：编译零警告、make test 全绿退出码 0）
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <random>
#include <string>
#include <vector>

#if defined(__aarch64__)
#include <arm_neon.h>
#endif

namespace {

constexpr std::size_t kDim = 128;                 // 128 维向量
using Vec = std::array<float, kDim>;

using Clock = std::chrono::steady_clock;

int g_failures = 0;

void check(bool ok, const std::string& what) {
    std::cout << (ok ? "[通过] " : "[失败] ") << what << '\n';
    if (!ok) {
        ++g_failures;
    }
}

// ---- 语料与查询集：确定性伪随机，便于跨实现、跨机器复现 ----
std::vector<float> make_corpus(std::size_t n) {
    std::vector<float> corpus(n * kDim);
    std::mt19937 rng(11);
    std::uniform_real_distribution<float> dist(0.0f, 1.0f);
    for (float& v : corpus) {
        v = dist(rng);
    }
    return corpus;
}

std::vector<Vec> make_queries(std::size_t q) {
    std::vector<Vec> queries(q);
    std::mt19937 rng(22);
    std::uniform_real_distribution<float> dist(0.0f, 1.0f);
    for (Vec& query : queries) {
        for (float& v : query) {
            v = dist(rng);
        }
    }
    return queries;
}

// 每次测量前递增的探针：让每轮查询向量微移 1e-4，结果逐轮变化 → 编译器无法把
// 整个距离循环外提（LICM/CSE 防护）。增量足够小，不改变最近邻归属。
std::size_t g_sample = 0;

void perturb(std::vector<Vec>& queries) {
    const std::size_t q = g_sample % queries.size();
    const std::size_t d = (g_sample / queries.size()) % kDim;
    queries[q][d] += 1.0e-4f;
    ++g_sample;
}

// ---- 实现①：朴素标量，单 float 累加器（顺序依赖链） ----
void impl_scalar(const float* corpus, std::size_t n,
                 const std::vector<Vec>& queries,
                 std::vector<std::size_t>& best_idx, std::vector<float>& best_sq) {
    for (std::size_t q = 0; q < queries.size(); ++q) {
        const float* query = queries[q].data();
        std::size_t min_i = 0;
        float min_sq = 1e30f;
        for (std::size_t i = 0; i < n; ++i) {
            const float* c = corpus + i * kDim;
            float sq = 0.0f;
            for (std::size_t d = 0; d < kDim; ++d) {
                const float diff = query[d] - c[d];
                sq += diff * diff;  // 每维都等上一个加法完成：吞吐受算数延迟限制
            }
            if (sq < min_sq) {
                min_sq = sq;
                min_i = i;
            }
        }
        best_idx[q] = min_i;
        best_sq[q] = min_sq;
    }
}

// ---- 实现②：4 路独立 float 累加器（打断依赖链，纯标量改写） ----
void impl_unroll4(const float* corpus, std::size_t n,
                  const std::vector<Vec>& queries,
                  std::vector<std::size_t>& best_idx, std::vector<float>& best_sq) {
    for (std::size_t q = 0; q < queries.size(); ++q) {
        const float* query = queries[q].data();
        std::size_t min_i = 0;
        float min_sq = 1e30f;
        for (std::size_t i = 0; i < n; ++i) {
            const float* c = corpus + i * kDim;
            float s0 = 0.0f, s1 = 0.0f, s2 = 0.0f, s3 = 0.0f;
            std::size_t d = 0;
            for (; d + 4 <= kDim; d += 4) {
                float df = query[d] - c[d];
                s0 += df * df;
                df = query[d + 1] - c[d + 1];
                s1 += df * df;
                df = query[d + 2] - c[d + 2];
                s2 += df * df;
                df = query[d + 3] - c[d + 3];
                s3 += df * df;
            }
            float sq = (s0 + s1) + (s2 + s3);
            for (; d < kDim; ++d) {
                const float diff = query[d] - c[d];
                sq += diff * diff;
            }
            if (sq < min_sq) {
                min_sq = sq;
                min_i = i;
            }
        }
        best_idx[q] = min_i;
        best_sq[q] = min_sq;
    }
}

#if defined(__aarch64__)
// ---- 实现③：NEON intrinsics——8 宽双累加器，一次处理 8 维 ----
void impl_neon(const float* corpus, std::size_t n,
               const std::vector<Vec>& queries,
               std::vector<std::size_t>& best_idx, std::vector<float>& best_sq) {
    for (std::size_t q = 0; q < queries.size(); ++q) {
        const float* query = queries[q].data();
        std::size_t min_i = 0;
        float min_sq = 1e30f;
        for (std::size_t i = 0; i < n; ++i) {
            const float* c = corpus + i * kDim;
            float32x4_t acc0 = vdupq_n_f32(0.0f);
            float32x4_t acc1 = vdupq_n_f32(0.0f);
            std::size_t d = 0;
            for (; d + 8 <= kDim; d += 8) {
                const float32x4_t qa = vld1q_f32(query + d);
                const float32x4_t ca = vld1q_f32(c + d);
                const float32x4_t qb = vld1q_f32(query + d + 4);
                const float32x4_t cb = vld1q_f32(c + d + 4);
                const float32x4_t da = vsubq_f32(qa, ca);
                const float32x4_t db = vsubq_f32(qb, cb);
                acc0 = vmlaq_f32(acc0, da, da);
                acc1 = vmlaq_f32(acc1, db, db);
            }
            const float32x4_t acc = vaddq_f32(acc0, acc1);
            float lane[4];
            vst1q_f32(lane, acc);
            float sq = (lane[0] + lane[1]) + (lane[2] + lane[3]);
            for (; d < kDim; ++d) {
                const float diff = query[d] - c[d];
                sq += diff * diff;  // 尾数标量兜底（128 是 8 的倍数，正常为空）
            }
            if (sq < min_sq) {
                min_sq = sq;
                min_i = i;
            }
        }
        best_idx[q] = min_i;
        best_sq[q] = min_sq;
    }
}
#else
// x86-64 退路：无 NEON 时与 ② 等价（布局与依赖链结论不变）。
void impl_neon(const float* corpus, std::size_t n,
               const std::vector<Vec>& queries,
               std::vector<std::size_t>& best_idx, std::vector<float>& best_sq) {
    impl_unroll4(corpus, n, queries, best_idx, best_sq);
}
#endif

using ImplFn = void (*)(const float* corpus, std::size_t n,
                        const std::vector<Vec>& queries,
                        std::vector<std::size_t>& best_idx, std::vector<float>& best_sq);

// ---- 一致的测时框架：预热 + 多轮取最优；每轮微扰查询集防 LICM ----
struct BenchResult {
    const char* name;
    double ms;
    std::vector<std::size_t> best_idx;
    std::vector<float> best_sq;
};

BenchResult bench_one(const char* name, ImplFn fn, const float* corpus, std::size_t n,
                      const std::vector<Vec>& queries_base, int samples) {
    g_sample = 0;                     // 各实现的扰动序列一致 → 末轮输入可跨实现比对
    std::vector<Vec> worker = queries_base;  // 本实现的私有查询集副本
    std::vector<std::size_t> idx(queries_base.size());
    std::vector<float> sq(queries_base.size());

    fn(corpus, n, worker, idx, sq);  // 预热 + 触发缓存/频率稳定

    double best_ms = 1e300;
    for (int s = 0; s < samples; ++s) {
        perturb(worker);  // 微扰在计时区外，但结果随轮次不同 → 无跨样本外提
        const auto t0 = Clock::now();
        fn(corpus, n, worker, idx, sq);
        const auto t1 = Clock::now();
        best_ms = std::min(best_ms, std::chrono::duration<double, std::milli>(t1 - t0).count());
    }
    // idx/sq 保留最后一轮的结果：各实现按同一扰动序列执行，可直接跨实现比对。
    return BenchResult{name, best_ms, std::move(idx), std::move(sq)};
}

bool near(float a, float b) {
    return std::fabs(a - b) < 1e-4 + 1e-3 * std::max(1.0f, std::fabs(b));
}

// 跨实现一致性：最近邻索引必须逐查询相同，距离值在容差内一致。
void compare_results(const char* a_name, const BenchResult& a,
                     const char* b_name, const BenchResult& b) {
    bool ok = true;
    std::size_t first_bad = 0;
    for (std::size_t q = 0; q < a.best_idx.size(); ++q) {
        if (a.best_idx[q] != b.best_idx[q] || !near(a.best_sq[q], b.best_sq[q])) {
            ok = false;
            first_bad = q;
            break;
        }
    }
    std::string what = std::string(a_name) + " 与 " + b_name + " 最近邻结果一致";
    if (!ok) {
        what += "（首个不一致：查询 " + std::to_string(first_bad) + "）";
    }
    check(ok, what);
}

}  // namespace

// --selftest：小规模快速一致性自检（时间短、可作 CI 信号）
int run_selftest() {
    const std::size_t n = 4'000;
    const std::size_t q = 4;
    const std::vector<float> corpus = make_corpus(n);
    const std::vector<Vec> queries = make_queries(q);

    const std::vector<std::pair<const char*, ImplFn>> impls = {
        {"scalar", impl_scalar}, {"unroll4", impl_unroll4}, {"neon", impl_neon}};

    std::vector<std::size_t> idx(q);
    std::vector<float> sq(q);
    std::vector<Vec> worker = queries;
    std::vector<BenchResult> results;
    for (const auto& [name, fn] : impls) {
        fn(corpus.data(), n, worker, idx, sq);  // 自测不做扰动与计时，只验语义
        results.push_back(BenchResult{name, 0.0, idx, sq});
    }
    compare_results(results[0].name, results[0], results[1].name, results[1]);
    compare_results(results[0].name, results[0], results[2].name, results[2]);

    std::cout << (g_failures == 0 ? "自测通过，退出码 0\n" : "自测失败\n");
    return g_failures == 0 ? 0 : 1;
}

int main(int argc, char** argv) {
    if (argc > 1 && std::string(argv[1]) == "--selftest") {
        return run_selftest();
    }
    if (argc > 1 && std::string(argv[1]) == "--help") {
        std::cout << "用法：./build/vec_bench [--selftest | --help]\n"
                  << "  默认：全量基准（100k 向量 × 6 查询 × 128 维，~3s）\n"
                  << "  --selftest：小规模一致性自检（CI 用）\n";
        return 0;
    }

    const std::size_t n = 100'000;
    const std::size_t q = 6;
    const std::vector<float> corpus = make_corpus(n);
    const std::vector<Vec> queries = make_queries(q);

    std::cout << "向量距离基准：corpus " << n << " × dim " << kDim << "，查询 "
              << q << " 个（每次运行计算 " << n * q << " 个距离）\n\n";

    const std::vector<std::pair<const char*, ImplFn>> impls = {
        {"① scalar（单累加器）", impl_scalar},
        {"② unroll4（4 路累加）", impl_unroll4},
        {"③ neon（NEON 8 宽）", impl_neon}};

    std::vector<BenchResult> results;
    for (const auto& [name, fn] : impls) {
        results.push_back(bench_one(name, fn, corpus.data(), n, queries, /*samples=*/3));
    }

    const double scalar_ms = results[0].ms;
    std::cout << "实现                    耗时(ms)    M dist/s   相对 ①\n";
    for (const BenchResult& r : results) {
        const double mega = static_cast<double>(n * q) / (r.ms * 1e3);  // 百万距离/秒
        std::cout << r.name << "  " << std::to_string(r.ms).substr(0, 8) << "   "
                  << std::to_string(mega).substr(0, 6) << "      "
                  << std::to_string(scalar_ms / r.ms).substr(0, 5) << "x\n";
    }
    std::cout << '\n';

    // 跨实现一致性（bench_one 末轮各实现输入相同）
    compare_results(results[0].name, results[0], results[1].name, results[1]);
    compare_results(results[0].name, results[0], results[2].name, results[2]);

    // 性能方向性断言（scalar→unroll 差距是数量级，噪声不可能翻转；NEON 档用
    // 宽松上界——若编译器把 unroll4 自动向量化到与 NEON 同速，本身也是教学点）
    check(results[1].ms < results[0].ms, "实测：4 路累加快于单累加器");
    check(results[2].ms < results[1].ms * 1.15,
          "实测：NEON 不慢于 4 路标量（通常明显更快）");

    std::cout << (g_failures == 0 ? "全部通过，退出码 0\n" : "存在失败\n");
    return g_failures == 0 ? 0 : 1;
}
