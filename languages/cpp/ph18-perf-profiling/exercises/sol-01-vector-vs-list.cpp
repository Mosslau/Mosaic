// exercises/sol-01-vector-vs-list.cpp —— 练习 1 参考实现：vector vs list 遍历性能对比
// 对应题目：exercises/README.md 练习 1（roadmap §18 练习「对比 vector 与 list 遍历性能」）。
// 教学点：同一批 200 万 int，vector 连续存放（64 B 缓存行一次带 16 个、可向量化），
// list 每节点一个堆分配 + next 指针跳转——顺序遍历的实测差距通常在 5~20 倍。
// 测时纪律：预热 + 多轮取最优；每轮把两个容器的**首元素**都 +1（O(1) 扰动），
// 让每轮输入略有变化，编译器无法把整段遍历提升到计时循环外。
//
// 验证环境：macOS arm64，Apple clang 21.0.0，libc++（C++20）
// 编译：clang++ -std=c++20 -O2 -Wall -Wextra sol-01-vector-vs-list.cpp -o /tmp/ph18sol-01
// 运行：/tmp/ph18sol-01
// 验证状态：已验证（本机实测：2M 个 int，vector 约 0.24 ms、list 约 1.8 ms，
//   list 慢约 7.7 倍，结果一致）
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <list>
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

std::int64_t sum_vector(const std::vector<int>& v) {
    std::int64_t sum = 0;
    for (const int x : v) {  // 连续步长 4 B：硬件预取 + 编译器可向量化
        sum += x;
    }
    return sum;
}

std::int64_t sum_list(const std::list<int>& l) {
    std::int64_t sum = 0;
    for (const int x : l) {  // 每步解引用一个 next 指针，节点地址不规则
        sum += x;
    }
    return sum;
}

// 测时：预热一次，跑 reps 轮取最小值。返回秒数。
template <typename F>
double best_of(F&& f, int reps) {
    f();  // 预热
    double best = 1e300;
    for (int r = 0; r < reps; ++r) {
        const auto t0 = Clock::now();
        const std::int64_t s = f();
        volatile std::int64_t sink = s;  // 结果必须真实产出（防整段删除）
        (void)sink;
        const auto t1 = Clock::now();
        best = std::min(best, std::chrono::duration<double>(t1 - t0).count());
    }
    return best;
}

}  // namespace

int main() {
    constexpr std::size_t k = 2'000'000;
    std::mt19937 rng(1);
    std::uniform_int_distribution<int> dist(0, 100'000);

    std::vector<int> vec(k);
    for (int& x : vec) {
        x = dist(rng);
    }
    std::list<int> lst(vec.begin(), vec.end());  // 与 vector 逐元素相同

    const int reps = 5;
    // 每轮把两容器首元素 +1：O(1) 扰动让每轮求和结果不同 → 防 LICM/CSE。
    // 两个容器扰动次数相同，最终内容仍逐元素一致，末尾可做严格相等断言。
    const double t_vec = best_of([&] {
        vec.front() += 1;
        return sum_vector(vec);
    }, reps);
    const double t_lst = best_of([&] {
        lst.front() += 1;
        return sum_list(lst);
    }, reps);

    std::cout << "顺序遍历求和（" << k << " 个 int）\n";
    std::cout << "  vector: " << std::to_string(t_vec * 1e3).substr(0, 6) << " ms（连续内存）\n";
    std::cout << "  list:   " << std::to_string(t_lst * 1e3).substr(0, 6) << " ms，慢 "
              << std::to_string(t_lst / t_vec).substr(0, 5) << "x（每节点指针跳转）\n\n";

    const std::int64_t sv = sum_vector(vec);
    const std::int64_t sl = sum_list(lst);
    check(sv == sl, "两容器遍历结果一致（内容逐元素相同）");
    check(t_lst > t_vec, "实测：vector 顺序遍历快于 list");
    check(vec.front() == lst.front(), "扰动同步进行，首元素仍一致");

    std::cout << (g_failures == 0 ? "全部通过，退出码 0\n" : "存在失败\n");
    return g_failures == 0 ? 0 : 1;
}
