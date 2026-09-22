// ex01-stats-core.h —— C++ 核心：只被 C++ 侧 include，绝不跨二进制边界
// 验证环境：Apple clang 21.0.0（/usr/bin/clang++，默认 PATH）+ Homebrew clang 21.1.8 交叉实测
// 构建：见 examples/README.md ex01；编译命令 clang++ -std=c++20 -Wall -Wextra -dynamiclib
// 验证状态：已验证（双编译器编译 dylib 零警告、C 宿主调用断言全绿、退出码 0）
#ifndef EX01_STATS_CORE_H
#define EX01_STATS_CORE_H

#include <cstddef>
#include <numeric>
#include <stdexcept>
#include <vector>

namespace vtest {

// 纯 C++ 内部实现：std::vector、异常随便用，全部不出边界。
// 教学性简化：刻意做成 Rule of Zero 极简类，聚焦「边界翻译」而非类设计。
class running_stats {
public:
    void add(double value) {
        if (value != value) {  // NaN 拒绝：错误留在这层，C ABI 用错误码表达
            throw std::invalid_argument("value is NaN");
        }
        values_.push_back(value);
    }

    std::size_t count() const { return values_.size(); }

    double mean() const {
        if (values_.empty()) {
            throw std::runtime_error("no samples yet");
        }
        const double sum = std::accumulate(values_.begin(), values_.end(), 0.0);
        return sum / static_cast<double>(values_.size());
    }

private:
    std::vector<double> values_;
};

}  // namespace vtest

#endif  // EX01_STATS_CORE_H
