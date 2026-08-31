// stats_utils.cpp —— ph10 工程模板：core 库实现
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 构建：由 project/Makefile 负责（make）
#include "stats_utils.h"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace stats {

static void require_nonempty(const std::vector<double>& v) {
    if (v.empty()) {
        throw std::invalid_argument("stats: empty input");
    }
}

double mean(const std::vector<double>& v) {
    require_nonempty(v);
    double sum = 0.0;
    for (const double x : v) sum += x;
    return sum / static_cast<double>(v.size());
}

double median(const std::vector<double>& v) {
    require_nonempty(v);
    std::vector<double> sorted = v;          // 拷贝后排序，不改动调用方
    std::sort(sorted.begin(), sorted.end());
    const std::size_t n = sorted.size();
    const std::size_t mid = n / 2;
    if (n % 2 == 1) return sorted[mid];
    return (sorted[mid - 1] + sorted[mid]) / 2.0;
}

double stddev(const std::vector<double>& v) {
    require_nonempty(v);
    const double m = mean(v);
    double sq_sum = 0.0;
    for (const double x : v) {
        const double d = x - m;
        sq_sum += d * d;
    }
    return std::sqrt(sq_sum / static_cast<double>(v.size()));   // 总体标准差（除以 N）
}

std::pair<double, double> min_max(const std::vector<double>& v) {
    require_nonempty(v);
    const auto [lo, hi] = std::minmax_element(v.begin(), v.end());
    return {*lo, *hi};
}

}  // namespace stats
