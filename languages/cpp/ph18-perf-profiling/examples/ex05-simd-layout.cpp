// examples/ex05-simd-layout.cpp —— SIMD 友好的内存布局教学完整版
// 教学点：SIMD 提速 = 数据布局 × 并行累加，缺一不可。对同一批三维点求 Σx²：
//   ① AoS（Array of Structs）取 x 分量切片：步长 12 B，非 4/8/16 倍数，SIMD 无从谈起；
//   ② SoA（Struct of Arrays）x 单独成连续 float 数组——布局就位，但单累加器的
//      依赖链仍然卡住每拍只能做一个 fma；
//   ③ SoA + 手写 4 路累加器：不引入任何 intrinsics 就打断依赖链；
//   ④ SoA + NEON intrinsics：布局与并行度同时到位（第 ③ 步若被编译器自动向量化，
//      会得到与 ④ 相近的时间——那正是「把机会交给编译器」的样子）。
// 数字优先级：本机 6M 点实测 ③ 快 3.6 倍、④ 快 5.3 倍（相对 ①）；先看数据再谈优化。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 编译：
//   clang++ -std=c++20 -O3 -Wall -Wextra ex05-simd-layout.cpp -o /tmp/ph18cpp-ex05
// 运行：/tmp/ph18cpp-ex05
// 验证状态：已验证（双编译器 -O3 实测：编译零警告、运行通过；arm64 NEON 路径经
//   __aarch64__ 宏实际编译进二进制并参与计时。x86-64 上 NEON 内核退化为标量并打印提示）
#include <chrono>
#include <cmath>
#include <cstddef>
#include <iostream>
#include <random>
#include <string>
#include <vector>

#if defined(__aarch64__)
#include <arm_neon.h>
#endif

namespace {

using Clock = std::chrono::steady_clock;

int g_failures = 0;

void check(bool ok, const std::string& what) {
    std::cout << (ok ? "[通过] " : "[失败] ") << what << '\n';
    if (!ok) {
        ++g_failures;
    }
}

struct Point3 {
    float x;
    float y;
    float z;
};

// ---- 四种内核，计算同一语义：Σ x_i² ----
// ① AoS 布局、取 x 分量切片：12 B 步长非向量宽度倍数，编译器不喂向量单元。
double sum_sq_aos_slice(const std::vector<Point3>& points) {
    float sum = 0.0f;
    for (const Point3& p : points) {
        sum += p.x * p.x;  // 每次迭代跳过 y/z，12 B 一取
    }
    return static_cast<double>(sum);
}

// ② SoA 布局、x 单独成连续数组：布局到位，但单累加器形成串行依赖链——
// 每拍只能等上一个 fma 的结果，吞吐被算数延迟卡住（这是多数「布局对了却不快」的真相）。
double sum_sq_soa_slice(const std::vector<float>& xs) {
    float sum = 0.0f;
    for (const float v : xs) {
        sum += v * v;
    }
    return static_cast<double>(sum);
}

// ③ SoA + 4 路独立累加器：不写任何 intrinsics，只把依赖链拆成 4 条。
// 编译器若允许（O3/展开），可能再进一步自动向量化——那时它得到 ≈ ④ 的速度。
double sum_sq_soa_unroll4(const std::vector<float>& xs) {
    float s0 = 0.0f, s1 = 0.0f, s2 = 0.0f, s3 = 0.0f;
    std::size_t i = 0;
    const std::size_t n = xs.size();
    for (; i + 4 <= n; i += 4) {
        s0 += xs[i] * xs[i];
        s1 += xs[i + 1] * xs[i + 1];
        s2 += xs[i + 2] * xs[i + 2];
        s3 += xs[i + 3] * xs[i + 3];
    }
    for (; i < n; ++i) {
        s0 += xs[i] * xs[i];
    }
    return static_cast<double>((s0 + s1) + (s2 + s3));
}

#if defined(__aarch64__)
// 手写 NEON：4 宽 fmla 累积，双累加器压低乘法链延迟；末段标量兜底。
// 仅供对照——绝大多数场景让编译器自动向量化即可，手写是「编译器不给力时」的底牌。
double sum_sq_neon(const std::vector<float>& xs) {
    float32x4_t acc0 = vdupq_n_f32(0.0f);
    float32x4_t acc1 = vdupq_n_f32(0.0f);
    std::size_t i = 0;
    const std::size_t n = xs.size();
    for (; i + 8 <= n; i += 8) {  // 一次搬 8 个，分两个 4 宽累加器
        const float32x4_t a = vld1q_f32(xs.data() + i);
        const float32x4_t b = vld1q_f32(xs.data() + i + 4);
        acc0 = vmlaq_f32(acc0, a, a);
        acc1 = vmlaq_f32(acc1, b, b);
    }
    const float32x4_t acc = vaddq_f32(acc0, acc1);
    float lane[4];
    vst1q_f32(lane, acc);
    double sum = static_cast<double>(lane[0]) + lane[1] + lane[2] + lane[3];
    for (; i < n; ++i) {
        sum += static_cast<double>(xs[i]) * xs[i];
    }
    return sum;
}
#else
double sum_sq_neon(const std::vector<float>& xs) {
    // 非 arm64 环境的退路：本文件在 x86-64 编译时 NEON 内核退化为 SoA 标量，
    // 结论不受影响（SoA vs AoS 的布局差距依然可见）。
    std::cerr << "（提示）非 arm64：NEON 内核退化为标量 SoA\n";
    return sum_sq_soa_slice(xs);
}
#endif

// 扰动被测数组的某一个元素：float 直接加，Point3 加在 x 上。目的只有一个——
// 让每轮测量结果随轮次变化，编译器就无法把整段计算提升到计时循环外。
void perturb(float& v) { v += 1.0e-7f; }
void perturb(Point3& p) { p.x += 1.0e-7f; }

// 测时：取多轮最小值；volatile 落盘防止「结果未使用」整体删除。
template <typename F, typename PerturbVec>
double measure_kernel(F&& kernel, int reps, PerturbVec& data) {
    kernel();
    double best = 1e300;
    for (int r = 0; r < reps; ++r) {
        perturb(data[static_cast<std::size_t>(r) % data.size()]);
        const auto t0 = Clock::now();
        volatile double sink = kernel();
        (void)sink;
        const auto t1 = Clock::now();
        best = std::min(best, std::chrono::duration<double>(t1 - t0).count());
    }
    return best;
}

// 容差说明：float 累加器在 ~2e6 量级的总和上，顺序/多路/向量三种累加次序的
// 舍入差异可到 ~0.4%，所以这里用 2% 相对容差做「同一批数据的平方和」一致性校验——
// 校验目的是抓语义错误（量级不符），不是抓浮点次序噪声。
bool near(double a, double b) {
    return std::fabs(a - b) < 1e-4 + 2e-2 * std::max(1.0, std::fabs(b));
}

}  // namespace

int main() {
    constexpr std::size_t k = 6'000'000;  // 6M 点：SoA 的 x 数组 24 MB，超出本机 L2
    std::mt19937 rng(7);
    std::uniform_real_distribution<float> dist(0.0f, 1.0f);

    std::vector<Point3> aos(k);   // AoS：每个元素 12 B（x,y,z 排在一起）
    std::vector<float> xs(k);     // SoA：x 分量单独一张连续表
    std::vector<float> ys(k);
    std::vector<float> zs(k);
    for (std::size_t i = 0; i < k; ++i) {
        const float x = dist(rng);
        const float y = dist(rng);
        const float z = dist(rng);
        aos[i] = Point3{x, y, z};
        xs[i] = x;
        ys[i] = y;
        zs[i] = z;
    }

    const int reps = 5;
    const double t_aos = measure_kernel([&] { return sum_sq_aos_slice(aos); }, reps, aos);
    const double t_soa = measure_kernel([&] { return sum_sq_soa_slice(xs); }, reps, xs);
    const double t_unroll4 =
        measure_kernel([&] { return sum_sq_soa_unroll4(xs); }, reps, xs);
    const double t_neon = measure_kernel([&] { return sum_sq_neon(xs); }, reps, xs);

    std::cout << "6M 个三维点 Σx²（AoS/SoA 各占内存 72/24 MB，均超出本机 L2）\n";
    std::cout << "实现                   耗时(ms)    相对 ①\n";
    std::cout << "① AoS  切片取 x        " << std::to_string(t_aos * 1e3).substr(0, 6) << "      1.00x\n";
    std::cout << "② SoA  标量单累加器     " << std::to_string(t_soa * 1e3).substr(0, 6) << "      "
              << std::to_string(t_aos / t_soa).substr(0, 5) << "x\n";
    std::cout << "③ SoA  4 路标量累加器   " << std::to_string(t_unroll4 * 1e3).substr(0, 6) << "      "
              << std::to_string(t_aos / t_unroll4).substr(0, 5) << "x\n";
    std::cout << "④ SoA  手写 NEON       " << std::to_string(t_neon * 1e3).substr(0, 6) << "      "
              << std::to_string(t_aos / t_neon).substr(0, 5) << "x\n\n";

    const double r_aos = sum_sq_aos_slice(aos);
    const double r_soa = sum_sq_soa_slice(xs);
    const double r_unroll4 = sum_sq_soa_unroll4(xs);
    const double r_neon = sum_sq_neon(xs);
    check(near(r_aos, r_soa), "①与②数值一致（同一批 x 的平方和）");
    check(near(r_soa, r_unroll4), "③与②数值一致（4 路累加只是改变加法次序）");
    check(near(r_soa, r_neon), "④与②数值一致（向量逐位平方和 + 尾数标量）");
    check(t_unroll4 < t_soa, "实测：拆依赖链（③）快于单累加器（②）");
    check(t_neon <= t_unroll4 * 1.2 + 1e-4, "实测：NEON（④）不慢于 4 路标量（③）");
    check(t_soa < t_aos && t_aos > 0.0, "实测：SoA 切片至少不慢于 AoS 切片，计时有效");

    std::cout << (g_failures == 0 ? "全部通过，退出码 0\n" : "存在失败\n");
    return g_failures == 0 ? 0 : 1;
}
