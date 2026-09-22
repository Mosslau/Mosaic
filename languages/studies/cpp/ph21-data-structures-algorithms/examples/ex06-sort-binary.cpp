// ex06-sort-binary.cpp —— 排序族与二分族 + 双指针/滑动窗口
// 对应主文档 3.9/3.10。教学点：sort（内省、不稳定）/stable_sort/partial_sort/nth_element 分场景；
// lower_bound/upper_bound/equal_range 区间语义；二分只对随机访问容器真 O(log n)；
// 双指针夹逼与滑动窗口把 O(n²) 压到 O(n)。
// 验证环境：Apple clang 21.0.0（/usr/bin/clang++），macOS arm64 + libc++
// 编译/运行：clang++ -std=c++20 -Wall -Wextra ex06-sort-binary.cpp -o /tmp/ph21-ex06 && /tmp/ph21-ex06
// 验证状态：已验证（编译零警告、断言全绿、退出码 0）
#include <algorithm>
#include <cstddef>
#include <deque>
#include <functional>
#include <iostream>
#include <utility>
#include <vector>

namespace {

void require(bool cond, const char* what) {
    if (!cond) {
        std::cerr << "FAIL: " << what << '\n';
        std::exit(1);
    }
}

void demo_sort_family() {
    std::vector<int> xs{5, 2, 9, 1, 7, 3, 8, 4, 6};
    std::sort(xs.begin(), xs.end());                    // 内省排序：O(n log n)，不稳定
    require(xs == std::vector<int>({1, 2, 3, 4, 5, 6, 7, 8, 9}), "sort ascending");

    std::sort(xs.begin(), xs.end(), std::greater<>{});  // 降序：传比较器
    require(xs.front() == 9 && xs.back() == 1, "sort descending via comparator");

    // stable_sort：相等键保持原相对序（按 score 排，同分保持插入序）
    std::vector<std::pair<int, int>> scores{{90, 1}, {80, 2}, {90, 3}, {70, 4}};
    std::stable_sort(scores.begin(), scores.end(),      // 只比 score
                     [](const auto& a, const auto& b) { return a.first < b.first; });
    require(scores[0] == std::pair{70, 4} && scores[1] == std::pair{80, 2}, "stable order tail");
    require(scores[2] == std::pair{90, 1} && scores[3] == std::pair{90, 3},
            "stable_sort keeps equal-key order (90,1) before (90,3)");

    // partial_sort：只保证前 k 就位有序；nth_element：只保证第 k 位就位（找中位数）
    std::vector<int> p{9, 2, 5, 1, 8, 3};
    std::partial_sort(p.begin(), p.begin() + 3, p.end());
    require(p[0] == 1 && p[1] == 2 && p[2] == 3, "partial_sort fixes first 3");

    std::vector<int> n{5, 2, 9, 1, 7, 3, 8, 4, 6};
    std::nth_element(n.begin(), n.begin() + 4, n.end());  // 升序后的第 4 位 = 5（中位数）
    require(n[4] == 5, "nth_element places median at index 4");
    std::cout << "  sort family checks passed\n";
}

void demo_binary_family() {
    std::vector<int> v{1, 3, 3, 3, 5, 7};
    const auto lo = std::lower_bound(v.begin(), v.end(), 3);   // 第一个 >= 3
    const auto hi = std::upper_bound(v.begin(), v.end(), 3);   // 第一个 > 3
    require(static_cast<std::size_t>(lo - v.begin()) == 1, "lower_bound(3) = index 1");
    require(static_cast<std::size_t>(hi - v.begin()) == 4, "upper_bound(3) = index 4");
    const auto range = std::equal_range(v.begin(), v.end(), 3);
    require(range.first == lo && range.second == hi, "equal_range spans [lo, hi)");
    require(std::binary_search(v.begin(), v.end(), 3), "binary_search says present");
    require(!std::binary_search(v.begin(), v.end(), 4), "binary_search says absent");
    require(std::lower_bound(v.begin(), v.end(), 8) == v.end(), "lower_bound beyond all -> end()");
    std::cout << "  binary family checks passed\n";
}

void demo_two_pointer() {
    // 有序数组两数之和：左右夹逼，每个指针至多走 n 步 -> O(n)
    const std::vector<int> sorted{-3, 0, 1, 2, 5};
    const int target = 2;
    std::size_t left = 0;
    std::size_t right = sorted.size() - 1;
    bool found = false;
    while (left < right) {
        const int sum = sorted[left] + sorted[right];
        if (sum == target) {
            found = true;
            break;
        }
        if (sum < target) {
            ++left;                  // 和太小：左指针右移变大
        } else {
            --right;                 // 和太大：右指针左移变小
        }
    }
    require(found, "two-pointer finds pair summing to target (0 + 2)");
    std::cout << "  two-pointer pair-sum passed\n";
}

void demo_sliding_window() {
    // 滑动窗口：和 <= S 的最长连续子数组（正整数数组，右扩左缩）
    const std::vector<int> a{3, 1, 2, 1, 1, 1, 4, 2};
    constexpr long long k_limit = 5;
    std::size_t win_left = 0;
    long long win_sum = 0;
    std::size_t best_len = 0;
    for (std::size_t right = 0; right < a.size(); ++right) {
        win_sum += a[right];
        while (win_sum > k_limit) {          // 超了才收左指针
            win_sum -= a[win_left];
            ++win_left;
        }
        best_len = std::max(best_len, right - win_left + 1);
    }
    require(best_len == 4, "longest subarray with sum<=5 has length 4 ({1,2,1,1})");

    // 单调队列：滑动窗口最大值（deque 存下标，队头恒为当前窗口最大值）
    const std::vector<int> in{1, 3, -1, -3, 5, 3, 6, 7};
    constexpr std::size_t k = 3;
    std::vector<int> out;
    std::deque<std::size_t> dq;
    for (std::size_t i = 0; i < in.size(); ++i) {
        while (!dq.empty() && in[dq.back()] <= in[i]) {
            dq.pop_back();                   // 队尾比新元素小：永远不可能是窗口最大，淘汰
        }
        dq.push_back(i);
        while (!dq.empty() && dq.front() + k <= i) {
            dq.pop_front();                  // 队头滑出窗口
        }
        if (i >= k - 1) {
            out.push_back(in[dq.front()]);
        }
    }
    require(out == std::vector<int>({3, 3, 5, 5, 6, 7}), "sliding window maximums");
    std::cout << "  sliding-window checks passed\n";
}

}  // namespace

int main() {
    demo_sort_family();
    demo_binary_family();
    demo_two_pointer();
    demo_sliding_window();
    std::cout << "ex06-sort-binary OK\n";
    return 0;
}
