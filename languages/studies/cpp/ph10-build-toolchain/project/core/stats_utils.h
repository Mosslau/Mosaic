// stats_utils.h —— ph10 工程模板：core 库头文件
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 构建：由 project/Makefile 负责（make）
#ifndef PH10_STATS_UTILS_H
#define PH10_STATS_UTILS_H

#include <cstddef>
#include <utility>
#include <vector>

namespace stats {

double mean(const std::vector<double>& v);              // 算术平均，空输入抛 std::invalid_argument
double median(const std::vector<double>& v);            // 中位数（偶数取中间两数平均）
double stddev(const std::vector<double>& v);            // 总体标准差（除以 N）
std::pair<double, double> min_max(const std::vector<double>& v);  // (min, max)

}  // namespace stats

#endif  // PH10_STATS_UTILS_H
