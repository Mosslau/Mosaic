// sol-01-series-lib.cpp —— 练习 1 参考实现：C ABI 数值函数动态库
// 验证环境：Apple clang 21.0.0（C++20）；实测编译零警告、ctypes 断言全绿
// 构建（exercises/ 目录内）：
//   clang++ -std=c++20 -Wall -Wextra -dynamiclib sol-01-series-lib.cpp -o /tmp/libseries.dylib
// 运行：python3 sol-01-ctypes.py
// 验证状态：已验证
// 错误码约定（注释即契约，Python 侧按它断言）：
//   TSLIB_OK=0  TSLIB_ERR_NULL=1（xs/out 为 NULL）  TSLIB_ERR_INVALID=2（n <= 0）
//   其余异常兜底 TSLIB_ERR_INTERNAL=99
// 教学点：容器跨语言只传「指针 + 长度」（主文档 3.7）；错误码语义化并在两侧各自翻译。
#include <cmath>
#include <cstddef>
#include <stdexcept>
#include <vector>

namespace {

constexpr int k_ok = 0;
constexpr int k_err_null = 1;
constexpr int k_err_invalid = 2;
constexpr int k_err_internal = 99;

// C++ 核心：数值容器进来的第一步就拷进 std::vector——「借用」转「拥有」，
// 之后在 C++ 世界里随便用算法库，边界上不留任何指向 Python 内存的引用。
double sum_of(const std::vector<double>& xs) {
    double acc = 0.0;
    for (const double x : xs) acc += x;
    return acc;
}

}  // namespace

extern "C" int tslib_sum(const double* xs, long n, double* out) {
    if (xs == nullptr || out == nullptr) return k_err_null;
    if (n <= 0) return k_err_invalid;
    try {
        *out = sum_of(std::vector<double>(xs, xs + n));
        return k_ok;
    } catch (...) {
        return k_err_internal;
    }
}

extern "C" int tslib_norm2(const double* xs, long n, double* out) {
    if (xs == nullptr || out == nullptr) return k_err_null;
    if (n <= 0) return k_err_invalid;
    try {
        double acc = 0.0;
        for (long i = 0; i < n; ++i) {
            acc += xs[i] * xs[i];  // 教学性简化：n 小时直接平方累加即可
        }
        *out = std::sqrt(acc);
        return k_ok;
    } catch (...) {
        return k_err_internal;
    }
}

extern "C" int tslib_max(const double* xs, long n, double* out) {
    if (xs == nullptr || out == nullptr) return k_err_null;
    if (n <= 0) return k_err_invalid;
    try {
        double best = xs[0];
        for (long i = 1; i < n; ++i) {
            if (xs[i] > best) best = xs[i];
        }
        *out = best;
        return k_ok;
    } catch (...) {
        return k_err_internal;
    }
}

extern "C" int tslib_version(void) {
    return 1;
}
