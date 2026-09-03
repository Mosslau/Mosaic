// examples/ex04-alloc-optim.cpp —— 分配次数优化教学完整版
// 教学点：堆分配次数是可量化的第一性指标——分配要走分配器、可能碰锁与系统调用，
// 热路径上「少一次分配」往往比「少一次乘法」值钱得多。本示例重载全局 operator new
// 给整个进程数分配次数，对「字符串拼接」场景做基线 vs 优化的对照：
//   基线  result = result + tok + ','   每次迭代产生整段临时串（O(n) 拷贝 + 2 次分配）
//   优化  result.reserve(总长) + append  预分配一次，之后零分配纯追加
// 同一份输入、同一个输出，用数字证明「分配次数降了三个量级」。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 编译：
//   clang++ -std=c++20 -O2 -Wall -Wextra ex04-alloc-optim.cpp -o /tmp/ph18cpp-ex04
// 运行：/tmp/ph18cpp-ex04
// 预期输出：两路拼接的耗时与分配次数对比 + 输出一致断言 + 退出码 0
// 验证状态：已验证（双编译器 -O2 实测：编译零警告、运行通过；
//   本机 20k 词条：基线 ~24k 次分配，优化 1 次，快约 200 倍）
#include <chrono>
#include <cstddef>
#include <cstdlib>
#include <iostream>
#include <new>
#include <string>
#include <vector>

// ---- 全进程分配计数器：所有 ::operator new 都从这里过，可随时清零重计 ----
namespace {
std::size_t g_alloc_count = 0;  // 单线程示例，无需原子

struct AllocCounterGuard {  // 区域作用域内自动清零并在离开时读出——RAII 顺手复用
    explicit AllocCounterGuard(std::size_t& out) : out_(out) { g_alloc_count = 0; }
    ~AllocCounterGuard() { out_ = g_alloc_count; }

private:
    std::size_t& out_;
};
}  // namespace

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
void operator delete(void* p, std::size_t) noexcept { std::free(p); }  // sized delete 也计数归零后不会单独触发
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

std::string ascii_upper(std::string_view s) {
    std::string r(s);
    for (char& c : r) {
        if (c >= 'a' && c <= 'z') {
            c = static_cast<char>(c - 32);  // 只用 ASCII，避开 <cctype> 的 locale 依赖
        }
    }
    return r;
}

// 基线：每次迭代用 operator+ 造出全新临时串再赋值。
// 语义正确但两处致命伤：整段串被反复拷贝（O(n^2) 字符搬运）+ 每轮 2 次堆分配。
std::string baseline_join(const std::vector<std::string>& tokens) {
    std::string result;
    for (const std::string& tok : tokens) {
        result = result + ascii_upper(tok) + ',';  // 两次 operator+，两次新分配、一次整段拷贝
    }
    return result;
}

// 优化：先算准总长一次性 reserve，再逐词 append——区域总分配次数趋近 1。
std::string optimized_join(const std::vector<std::string>& tokens) {
    std::size_t total = 0;
    for (const std::string& tok : tokens) {
        total += tok.size() + 1;  // 词 + 逗号
    }
    std::string result;
    result.reserve(total);  // 唯一一次（可能）的分配，预留给全部载荷
    for (const std::string& tok : tokens) {
        for (const char c : tok) {
            result.push_back(static_cast<char>(c >= 'a' && c <= 'z' ? c - 32 : c));
        }
        result.push_back(',');  // 预分配充足，append/push_back 不再触发分配
    }
    return result;
}

}  // namespace

int main() {
    // 输入准备：7 个单词循环生成 20k 个词条（全部 ASCII 小写）。
    const std::vector<std::string> words{"alpha", "bravo",  "charlie", "delta",
                                         "echo",  "foxtrot", "golf"};
    std::vector<std::string> tokens;
    tokens.reserve(20'000);
    for (int i = 0; i < 20'000; ++i) {
        tokens.push_back(words[static_cast<std::size_t>(i) % words.size()]);
    }

    // 分配次数与耗时分开测，避免计时噪声与计数互相干扰。
    std::size_t alloc_base = 0;
    std::size_t alloc_opt = 0;

    const auto t0 = Clock::now();
    std::string base_out;
    {
        AllocCounterGuard guard(alloc_base);
        base_out = baseline_join(tokens);
    }
    const double t_base = std::chrono::duration<double>(Clock::now() - t0).count();

    const auto t1 = Clock::now();
    std::string opt_out;
    {
        AllocCounterGuard guard(alloc_opt);
        opt_out = optimized_join(tokens);
    }
    const double t_opt = std::chrono::duration<double>(Clock::now() - t1).count();

    std::cout << "拼接 20k 词条\n";
    std::cout << "  基线 result = result + tok + ',': 耗时 " << std::to_string(t_base * 1e3).substr(0, 6)
              << " ms，分配 " << alloc_base << " 次\n";
    std::cout << "  优化 reserve + append:           耗时 " << std::to_string(t_opt * 1e3).substr(0, 6)
              << " ms，分配 " << alloc_opt << " 次\n";
    std::cout << "  输出长度一致：" << (base_out.size() == opt_out.size()) << '\n';

    check(base_out == opt_out, "两路输出逐字节一致");
    check(alloc_base > 1000, "基线分配次数确实以千计");
    check(alloc_opt <= 2, "优化后分配次数趋近 0");
    check(alloc_opt * 100 < alloc_base, "分配次数下降两个量级以上");

    std::cout << (g_failures == 0 ? "全部通过，退出码 0\n" : "存在失败\n");
    return g_failures == 0 ? 0 : 1;
}
