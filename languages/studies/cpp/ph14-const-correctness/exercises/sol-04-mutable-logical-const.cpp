// sol-04-mutable-logical-const.cpp —— 练习 4 参考实现：mutable 与逻辑 const 判断
// 练习 4 要求：给定一个遥测类，判断哪些成员属于"逻辑状态"（const 成员函数不可改）、
//              哪些属于"物理状态"（缓存/计数，用 mutable），实现懒计算缓存并用
//              首次计算/命中缓存的输出实测验证。
//
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致）：
//   [1] 判断：samples_ 是逻辑状态（const 成员函数不可改）；缓存/计数是物理状态（mutable）
//     samples_（原始样本）→ 逻辑状态，须保持不可变
//     count_cache_/max_cache_/hits_ → 物理状态，mutable（只影响位，不影响语义）
//   [2] 懒计算实测：第一次算，之后命中缓存（const 成员函数内改 mutable 缓存位）
//     sample_count 首次计算 -> 6
//     tm.sample_count() = 6
//     sample_count 命中缓存 -> 6
//     tm.sample_count() = 6
//     max_value 首次计算 -> 99
//     tm.max_value()    = 99
//     max_value 命中缓存 -> 99
//     tm.max_value()    = 99
//   [3] 缓存命中计数（mutable 计数器）
//     cache_hits = 2（两次命中）
//   [4] 对照：把缓存成员改成非 mutable 会编译失败（const 成员函数内不可写）
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-04-mutable-logical-const.cpp -o /tmp/ph14-sol-04
// 运行：    /tmp/ph14-sol-04
// 验证状态：已验证（两种编译器均零警告，输出一致）
#include <cstdio>
#include <optional>
#include <utility>
#include <vector>

// 遥测类：对外是"只读聚合视图"（逻辑 const），内部懒计算缓存（物理 mutable）
class Telemetry {
public:
    explicit Telemetry(std::vector<int> samples) : samples_(std::move(samples)) {}

    // 逻辑 const：sample_count 是"查询"，不改变逻辑状态
    std::size_t sample_count() const {
        if (!count_cache_.has_value()) {
            std::printf("  sample_count 首次计算 -> %zu\n", samples_.size());
            count_cache_ = samples_.size();      // 写 mutable 缓存位
        } else {
            hits_ += 1;
            std::printf("  sample_count 命中缓存 -> %zu\n", *count_cache_);
        }
        return *count_cache_;
    }

    int max_value() const {
        if (!max_cache_.has_value()) {
            int m = samples_.empty() ? 0 : samples_.front();
            for (int v : samples_) {
                if (v > m) {
                    m = v;
                }
            }
            std::printf("  max_value 首次计算 -> %d\n", m);
            max_cache_ = m;                      // 写 mutable 缓存位
        } else {
            hits_ += 1;
            std::printf("  max_value 命中缓存 -> %d\n", *max_cache_);
        }
        return *max_cache_;
    }

    std::size_t cache_hits() const { return hits_; }

private:
    std::vector<int> samples_;                        // 逻辑状态：构造后不可变
    mutable std::optional<std::size_t> count_cache_;  // 物理状态：懒计算缓存
    mutable std::optional<int> max_cache_;            // 物理状态：懒计算缓存
    mutable std::size_t hits_{0};                     // 物理状态：命中计数
};

int main() {
    std::printf("[1] 判断：samples_ 是逻辑状态（const 成员函数不可改）；"
                "缓存/计数是物理状态（mutable）\n");
    std::printf("  samples_（原始样本）→ 逻辑状态，须保持不可变\n");
    std::printf("  count_cache_/max_cache_/hits_ → 物理状态，mutable"
                "（只影响位，不影响语义）\n");

    std::printf("[2] 懒计算实测：第一次算，之后命中缓存（const 成员函数内改 mutable 缓存位）\n");
    const Telemetry tm(std::vector<int>{3, 1, 99, 5, 7, 2});
    std::printf("  tm.sample_count() = %zu\n", tm.sample_count());
    std::printf("  tm.sample_count() = %zu\n", tm.sample_count());
    std::printf("  tm.max_value()    = %d\n", tm.max_value());
    std::printf("  tm.max_value()    = %d\n", tm.max_value());

    std::printf("[3] 缓存命中计数（mutable 计数器）\n");
    std::printf("  cache_hits = %zu（两次命中）\n", tm.cache_hits());

    std::printf("[4] 对照：把缓存成员改成非 mutable 会编译失败（const 成员函数内不可写）\n");
    return 0;
}
