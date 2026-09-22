// sol-03-geo-lib.cpp —— 练习 3 C++ 侧动态库：两点间 L2 距离
// 验证环境：Apple clang 21.0.0（C++20）；实测编译零警告
// 构建（exercises/ 目录内）：
//   clang++ -std=c++20 -Wall -Wextra -dynamiclib sol-03-geo-lib.cpp -o /tmp/libgeo.dylib
// 运行：rustc -O sol-03-rust.rs -L /tmp -l geo -o /tmp/sol03 && /tmp/sol03
// 验证状态：已验证（rustc 1.92.0 断言全绿）
// 错误码：GEO_OK=0  GEO_ERR_NULL=1  GEO_ERR_DIM=2（dim<=0）  GEO_ERR_INTERNAL=99
// 教学点：与 sol-01 同构的 C ABI 约定，接收方换成 Rust——Rust 侧手抄签名并翻译 Result。
#include <cmath>
#include <cstddef>
#include <stdexcept>

namespace {

constexpr int k_ok = 0;
constexpr int k_err_null = 1;
constexpr int k_err_dim = 2;
constexpr int k_err_internal = 99;

double distance_l2(const double* a, const double* b, long dim) {
    double acc = 0.0;
    for (long i = 0; i < dim; ++i) {
        const double d = a[i] - b[i];
        acc += d * d;
    }
    return std::sqrt(acc);
}

}  // namespace

extern "C" int geo_dist_l2(const double* a, const double* b, long dim, double* out) {
    if (a == nullptr || b == nullptr || out == nullptr) return k_err_null;
    if (dim <= 0) return k_err_dim;
    try {
        *out = distance_l2(a, b, dim);
        return k_ok;
    } catch (...) {
        return k_err_internal;
    }
}

extern "C" int geo_version(void) {
    return 1;
}
