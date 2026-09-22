// exercises/sol-03-alloc-reduction.cpp —— 练习 3 参考实现：减少热点路径内存分配
// 对应题目：exercises/README.md 练习 3（roadmap §18 练习「减少热点路径内存分配」）。
// 教学点：5 万行日志做词频统计——基线每个词都构造一个 std::string 再查表（每次出现
// 一次堆分配），优化改用 string_view 切词 + unordered_map<string_view,int>（只有新词
// 首次出现才分配一个表节点）。用全局 operator new 数分配次数验证，而不是凭感觉。
// string_view 作键的生命周期前提：输入文本必须活得比映射表久（本示例输入常驻）。
//
// 验证环境：macOS arm64，Apple clang 21.0.0，libc++（C++20）
// 编译：clang++ -std=c++20 -O2 -Wall -Wextra sol-03-alloc-reduction.cpp -o /tmp/ph18sol-03
// 运行：/tmp/ph18sol-03
// 验证状态：已验证（本机实测：50k 行长词日志，基线 ~15 万次分配（每词一次，
//   每次计数在 ~27 ms 内）、优化仅 11 次（每个新词一个节点），~4.7 ms）
#include <chrono>
#include <cstddef>
#include <cstdlib>
#include <iostream>
#include <new>
#include <random>
#include <sstream>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {
std::size_t g_alloc_count = 0;  // 单线程，无需原子
}  // namespace

// 全进程分配计数：只数次数，不拦分配本身。
void* operator new(std::size_t size) {
    ++g_alloc_count;
    if (void* p = std::malloc(size)) {
        return p;
    }
    throw std::bad_alloc();
}
void* operator new[](std::size_t size) {
    ++g_alloc_count;
    if (void* p = std::malloc(size)) {
        return p;
    }
    throw std::bad_alloc();
}
void operator delete(void* p) noexcept { std::free(p); }
void operator delete[](void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }
void operator delete[](void* p, std::size_t) noexcept { std::free(p); }

namespace {

using Clock = std::chrono::steady_clock;

int g_failures = 0;

void check(bool ok, const std::string& what) {
    std::cout << (ok ? "[通过] " : "[失败] ") << what << '\n';
    if (!ok) {
        ++g_failures;
    }
}

struct Result {  // 词频统计的代表性结果：最高频词及其计数
    std::string top_word;
    int top_count = 0;
};

// 基线：istringstream 切词，每个词先构造 std::string，operator[] 又默认构造一次候选键。
Result baseline_count(const std::vector<std::string>& lines) {
    std::unordered_map<std::string, int> counts;
    for (const std::string& line : lines) {
        std::istringstream iss(line);
        std::string word;
        while (iss >> word) {
            ++counts[word];  // 词出现一次 = 一次（或更多）堆分配
        }
    }
    Result best{"", 0};
    for (const auto& [word, n] : counts) {
        if (n > best.top_count) {
            best = Result{word, n};
        }
    }
    return best;
}

// 优化：同一份输入用 string_view 切词，映射键是视图——比较只看内容。
// 只有某词「第一次出现」才给映射表分配节点（distinct 词数远小于出现次数）。
Result fast_count(const std::vector<std::string>& lines) {
    std::unordered_map<std::string_view, int> counts;
    for (const std::string& line : lines) {
        std::size_t pos = 0;
        while (pos < line.size()) {
            const std::size_t start = line.find_first_not_of(' ', pos);
            if (start == std::string::npos) {
                break;
            }
            const std::size_t end = line.find(' ', start);
            const std::size_t stop = (end == std::string::npos) ? line.size() : end;
            ++counts[std::string_view(line).substr(start, stop - start)];
            pos = stop + 1;
        }
    }
    Result best{"", 0};
    for (const auto& [word, n] : counts) {
        if (n > best.top_count) {
            best = Result{std::string(word), n};  // 只在收尾复制最高频词
        }
    }
    return best;
}

// 注意词长：libc++ 的 std::string 对 ≤22 字节走小字符串优化（SSO，零堆分配），
// 会掩盖「每词一次分配」的差距——所以这里的词全部 >30 字节，强制走堆。
std::vector<std::string> make_lines(std::size_t n) {
    static constexpr std::string_view pool[] = {
        "quantum-entangled-memory-hierarchy-scalar-depth",
        "vectorization-friendly-contiguous-data-layout-width",
        "benchmark-warmup-minimum-of-repetitions-noise-floor",
        "cache-miss-prefetch-bandwidth-saturation-threshold",
        "profile-guided-optimization-hot-path-annotation-tag",
        "allocator-arena-pool-slub-cacheline-interleaving-mode"};
    std::vector<std::string> lines;
    lines.reserve(n);
    std::mt19937 rng(5);
    std::uniform_int_distribution<std::size_t> pick(0, std::size(pool) - 1);
    for (std::size_t i = 0; i < n; ++i) {
        lines.push_back(std::string(pool[pick(rng)]) + " " + std::string(pool[pick(rng)]) +
                        " " + std::string(pool[pick(rng)]));
    }
    return lines;
}

struct Measure {
    double ms;
    std::size_t allocs;
    Result result;
};

Measure run(const std::vector<std::string>& lines, bool fast) {
    g_alloc_count = 0;
    const auto t0 = Clock::now();
    Result r = fast ? fast_count(lines) : baseline_count(lines);
    const auto t1 = Clock::now();
    return Measure{std::chrono::duration<double, std::milli>(t1 - t0).count(),
                   g_alloc_count, std::move(r)};
}

}  // namespace

int main() {
    const std::vector<std::string> lines = make_lines(50'000);

    const Measure base = run(lines, /*fast=*/false);
    const Measure fast = run(lines, /*fast=*/true);

    std::cout << "词频统计（50k 行日志）\n";
    std::cout << "  基线 string 键:     " << std::to_string(base.ms).substr(0, 6) << " ms，"
              << base.allocs << " 次分配\n";
    std::cout << "  优化 string_view 键: " << std::to_string(fast.ms).substr(0, 6) << " ms，"
              << fast.allocs << " 次分配\n\n";
    std::cout << "  最高频词（基线/优化）：" << base.result.top_word << " / "
              << fast.result.top_word << "，计数 "
              << base.result.top_count << " / " << fast.result.top_count << '\n';

    check(base.result.top_word == fast.result.top_word, "两版最高频词一致");
    check(base.result.top_count == fast.result.top_count, "两版最高频计数一致");
    check(fast.allocs < base.allocs / 5, "实测：优化版分配次数显著更少");

    std::cout << (g_failures == 0 ? "全部通过，退出码 0\n" : "存在失败\n");
    return g_failures == 0 ? 0 : 1;
}
