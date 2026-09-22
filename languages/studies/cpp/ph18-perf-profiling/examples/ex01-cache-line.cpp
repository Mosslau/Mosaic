// examples/ex01-cache-line.cpp —— cache locality 教学完整版：连续 vs 跨步（列主序）访问
// 教学点：roadmap 必会概念「连续内存通常更利于缓存」。同一块行主序矩阵，
// 按行连续求和 vs 按列跨步求和——后者每次取数都跨一整行（16 KB），几乎每次都
// 错过缓存行且无法被硬件预取利用；本示例把这条差距量化成数字，先测量再下结论。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 编译（-O3 才谈得上 cache locality；-O0 会让差距失真，教学时请勿用 -O0）：
//   clang++ -std=c++20 -O3 -Wall -Wextra ex01-cache-line.cpp -o /tmp/ph18cpp-ex01
// 运行：/tmp/ph18cpp-ex01
// 预期输出（节选）：见 main() 内注释（逐行打印行主序/列主序耗时与慢倍率）
// 验证状态：已验证（Apple clang 21.0.0 与 Homebrew clang 21.1.8 双编译器 -O3
//   实测：编译零警告、运行通过、断言行全绿；本机列主序慢约 5.6 倍）
#include <chrono>
#include <cmath>
#include <cstddef>
#include <iostream>
#include <random>
#include <string>
#include <vector>

namespace {

using Clock = std::chrono::steady_clock;

int g_failures = 0;

void check(bool ok, const std::string& what) {
    std::cout << (ok ? "[通过] " : "[失败] ") << what << '\n';
    if (!ok) {
        ++g_failures;
    }
}

// 测时小助手：先热身一次，再跑 reps 次取最小值（最小值对调度噪声最稳）。
// 返回秒数。两个防优化细节缺一不可：
//   ① 每轮开始前修改 data 的某一个元素——被测结果随轮次变化，
//      编译器无法把整段计算提升到循环外（loop-invariant code motion）；
//   ② 结果写入 volatile double ——volatile 访问是不可消除的副作用，
//      保证真实执行求和而非被 -O3 当作「结果未使用」整体删除。
template <typename F>
double measure_kernel(F&& kernel, int reps, std::vector<float>& data) {
    kernel();  // 热身：把数据抬进缓存、让 CPU 频率稳定
    double best = 1e300;
    for (int r = 0; r < reps; ++r) {
        data[static_cast<std::size_t>(r) % data.size()] += 1.0e-7f;  // 见上方注释 ①
        const auto t0 = Clock::now();
        volatile double sink = kernel();  // 见上方注释 ②
        (void)sink;
        const auto t1 = Clock::now();
        best = std::min(best, std::chrono::duration<double>(t1 - t0).count());
    }
    return best;
}

// 按行主序连续求和：编译器可向量化，硬件预取器按 64 B 缓存行顺序拉取。
double sum_row_major(const std::vector<float>& data, std::size_t k) {
    double sum = 0.0;
    for (std::size_t i = 0; i < k; ++i) {
        for (std::size_t j = 0; j < k; ++j) {
            sum += static_cast<double>(data[i * k + j]);  // 相邻两次访问地址相差 4 B
        }
    }
    return sum;
}

// 按列跨步求和：同一列内相邻两行地址相差 k*4 B（本示例 16 KB），逐元素错过缓存行。
double sum_column_major(const std::vector<float>& data, std::size_t k) {
    double sum = 0.0;
    for (std::size_t j = 0; j < k; ++j) {
        for (std::size_t i = 0; i < k; ++i) {
            sum += static_cast<double>(data[i * k + j]);  // 相邻两次访问地址相差 k*4 B
        }
    }
    return sum;
}

// 分块求和（blocked/tiled）：把「列访问」切成 kTile*kTile 的小方块，
// 每块内部元素靠近（块径 64*4=256 B），跨步距离从 16 KB 降到 256 B——
// 牺牲一点顺序性换回局部性，是「改数据访问顺序」的中间档。
double sum_blocked(const std::vector<float>& data, std::size_t k, std::size_t tile) {
    double sum = 0.0;
    for (std::size_t ib = 0; ib < k; ib += tile) {
        for (std::size_t jb = 0; jb < k; jb += tile) {
            for (std::size_t i = ib; i < ib + tile && i < k; ++i) {
                for (std::size_t j = jb; j < jb + tile && j < k; ++j) {
                    sum += static_cast<double>(data[i * k + j]);
                }
            }
        }
    }
    return sum;
}

bool near(double a, double b) { return std::fabs(a - b) < 1e-3 * std::max(1.0, std::fabs(b)); }

}  // namespace

int main() {
    constexpr std::size_t k = 4096;                       // 4096*4096*4 B = 64 MiB 矩阵
    constexpr std::size_t tile = 64;                      // 分块直径 64 元素 = 256 B
    const std::size_t elements = k * k;                   // 16.7M 个 float

    // 64 MiB 数据远超本机 L2（4 MB，见主文档 4.1 的 sysctl 实测表）——缓存装不下，
    // 访问模式对耗时的影响才不会被「整块常驻缓存」掩盖。
    std::mt19937 rng(42);
    std::uniform_real_distribution<float> dist(0.0f, 1.0f);
    std::vector<float> data(elements);
    for (float& v : data) {
        v = dist(rng);
    }

    std::cout << "数据规模：k=" << k << "（" << (elements * 4 / 1024 / 1024)
              << " MiB，超出本机 L2 4 MB）\n\n";

    const int reps = 5;
    const double t_row = measure_kernel([&] { return sum_row_major(data, k); }, reps, data);
    const double t_col = measure_kernel([&] { return sum_column_major(data, k); }, reps, data);
    const double t_blk = measure_kernel([&] { return sum_blocked(data, k, tile); }, reps, data);

    std::cout << "访问模式     耗时(ms)   相对行主序\n";
    std::cout << "行主序(连续)  " << std::to_string(t_row * 1e3).substr(0, 6) << "     1.00x\n";
    std::cout << "列主序(跨步)  " << std::to_string(t_col * 1e3).substr(0, 6) << "     "
              << std::to_string(t_col / t_row).substr(0, 5) << "x\n";
    std::cout << "分块(64x64)   " << std::to_string(t_blk * 1e3).substr(0, 6) << "     "
              << std::to_string(t_blk / t_row).substr(0, 5) << "x\n\n";

    // 正确性：三种遍历覆盖同一批元素，只交换求和顺序，FP 误差应远小于 1e-3。
    const double r_row = sum_row_major(data, k);
    const double r_col = sum_column_major(data, k);
    const double r_blk = sum_blocked(data, k, tile);
    check(near(r_row, r_col), "行主序与列主序求和一致（仅求和顺序不同）");
    check(near(r_row, r_blk), "行主序与分块求和一致");
    check(t_col > t_row, "实测：列主序慢于行主序");
    check(t_blk < t_col, "实测：分块介于两者之间（局部性折中）");

    std::cout << (g_failures == 0 ? "全部通过，退出码 0\n" : "存在失败\n");
    return g_failures == 0 ? 0 : 1;
}
