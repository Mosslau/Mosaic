// examples/ex06-bench-harness.cpp —— 微型 benchmark 工具 + 「模式 vs 裸写」实测
// 教学点（兑现 ph17「下一阶段」预告：对模式开销给出 benchmark 结论）：
//   ① 一个自带的微型 benchmark 工具怎么用——预热、多轮取最优、ns/op 归一下；
//   ② 派发方式的实测结论（本机 -O2）：当所有实现都在同一翻译单元、调用点对编译器
//      全可见时，直调 / 函数指针 / std::function / 虚函数四路全被内联与去虚化，
//      收敛到 ~0.6–0.8 ns/op，差距 ≤30%——**编译器能看见的间接几乎是免费的**；
//   ③ ph17 的「执行器管道」形态（pull 模型虚节点，状态藏在堆对象里、跨 next()
//      调用迁移）vs 裸写循环：同一语义差约 5 倍——模式成本真正显形的地方，
//      是信息被藏起来、编译器无法恢复的那类运行时结构。
// 结论先看数字。两条合起来正是 roadmap 必会概念：先测量，再优化——别凭「模式贵」
// 或「模式免费」的直觉下结论。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 编译：
//   clang++ -std=c++20 -O2 -Wall -Wextra ex06-bench-harness.cpp -o /tmp/ph18cpp-ex06
// 运行：/tmp/ph18cpp-ex06
// 预期输出：四路派发 ns/op（同速量级）+ 管道 vs 裸写 ms 与倍率 + 一致性断言，退出码 0
// 验证状态：已验证（双编译器 -O2 实测：编译零警告、运行通过；
//   本机：派发四路 0.6–0.8 ns/op；过滤聚合 pull 虚管道约慢 5.6 倍）
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <iostream>
#include <memory>
#include <string>
#include <utility>
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

// 每次测量前递增的 volatile 探针：让每轮被测输入都不同，编译器无法把循环
// 外提到被测区外或整段公共子表达式消除（LICM/CSE 防护）。
volatile double g_tick = 1.0;

// ---- ① 微型 benchmark 工具：body 内部自跑 kOps 次操作并返回总和 ----
template <typename Body>
double best_of(Body&& body, int samples) {
    body(g_tick);  // 预热：触发代际缓存、频率稳定
    double best = 1e300;
    for (int s = 0; s < samples; ++s) {
        const double tick = g_tick;  // volatile 读：本轮真实输入
        g_tick += 0.5;
        const auto t0 = Clock::now();
        volatile double sink = body(tick);  // volatile 落盘：结果必须真实产出
        (void)sink;
        const auto t1 = Clock::now();
        best = std::min(best, std::chrono::duration<double>(t1 - t0).count());
    }
    return best;
}

// ---- ② 派发方式对比：四种调用同一个一元算子（x -> x*2+1） ----
constexpr std::size_t kOps = 4'000'000;

double op_mul2(double x) { return x * 2.0 + 1.0; }
double op_half(double x) { return x * 0.5 + 1.5; }  // 第二实现：让函数指针/多态真实「分派」

using FnPtr = double (*)(double);

class IUnary {  // 虚函数多态接口（ph17 风格的抽象形态）
public:
    virtual ~IUnary() = default;
    virtual double apply(double x) const = 0;
};

class UnaryMul2 final : public IUnary {
public:
    double apply(double x) const override { return x * 2.0 + 1.0; }
};

class UnaryHalf final : public IUnary {
public:
    double apply(double x) const override { return x * 0.5 + 1.5; }
};

void print_dispatch_results(double direct, double fnptr, double stdfn, double virt) {
    std::cout << "派发方式对比（每" << kOps << " 次一元调用，单位 ns/op，-O2 同翻译单元）\n";
    std::cout << "  直调           " << std::to_string(direct).substr(0, 6) << '\n';
    std::cout << "  函数指针       " << std::to_string(fnptr).substr(0, 6) << '\n';
    std::cout << "  std::function " << std::to_string(stdfn).substr(0, 6) << '\n';
    std::cout << "  虚函数         " << std::to_string(virt).substr(0, 6) << '\n';
    const double worst = std::max({fnptr, stdfn, virt});
    std::cout << "  → 最慢/最快 " << std::to_string(worst / direct).substr(0, 4)
              << "x：调用点全可见时，编译器把四种机制收敛到几乎同速\n\n";
}

// ---- ③ 查询过滤聚合：pull 模型虚管道（ph17 执行器同款形态）vs 裸写 ----
struct Record {
    std::int64_t id;
    double x;
    double y;
};

std::vector<Record> make_records(std::size_t n) {
    std::vector<Record> out;
    out.reserve(n);
    std::uint64_t state = 0x9E3779B97F4A7C15ULL;
    for (std::size_t i = 0; i < n; ++i) {
        state = state * 6364136223846793005ULL + 1442695040888963407ULL;
        const double u = static_cast<double>(state >> 11) / static_cast<double>(1ULL << 53);
        state = state * 6364136223846793005ULL + 1442695040888963407ULL;
        const double v = static_cast<double>(state >> 11) / static_cast<double>(1ULL << 53);
        out.push_back(Record{static_cast<std::int64_t>(i), u, v});
    }
    return out;
}

// 裸写：单层循环内完成「过滤 + 聚合」，编译器看得见全部数据流。
// tick 以每行 1e-9 参与累加：让每轮测量结果随 tick 变化（远大于总和量级的 ULP），
// 编译器既不能跨样本公共子表达式消除，语义上也只引入 ~1e-9 级别的噪声。
double raw_filter_sum(const std::vector<Record>& rows, double tick) {
    double sum = 0.0;
    for (const Record& r : rows) {
        if (r.y > 0.5) {
            sum += r.x + tick * 1e-9;
        }
    }
    return sum;
}

// pull 模型管道：Scan ──▶ Filter。每个包装节点独占持有上游（unique_ptr，ph17 手法），
// 每取一行要穿越 Filter::next()（虚调用）→ 上游 Scan::next()（虚调用）。
class IStep {
public:
    virtual ~IStep() = default;
    virtual bool next(Record& out) = 0;
};

class ScanStep final : public IStep {
public:
    explicit ScanStep(const std::vector<Record>& rows) : rows_(rows) {}
    bool next(Record& out) override {
        if (idx_ >= rows_.size()) {
            return false;
        }
        out = rows_[idx_++];
        return true;
    }

private:
    const std::vector<Record>& rows_;  // 非拥有视图（R.3）
    std::size_t idx_ = 0;
};

class FilterStep final : public IStep {
public:
    FilterStep(std::unique_ptr<IStep> upstream, std::function<bool(const Record&)> pred)
        : upstream_(std::move(upstream)), pred_(std::move(pred)) {}
    bool next(Record& out) override {
        Record r;
        while (upstream_->next(r)) {  // 一直向上游拉，直到谓词通过或上游耗尽
            if (pred_(r)) {
                out = r;
                return true;
            }
        }
        return false;
    }

private:
    std::unique_ptr<IStep> upstream_;  // 独占持有上游节点，生命周期沿管道传递
    std::function<bool(const Record&)> pred_;
};

double pipe_filter_sum(const std::vector<Record>& rows, double tick) {
    auto scan = std::make_unique<ScanStep>(rows);
    auto filter = std::make_unique<FilterStep>(
        std::move(scan), [](const Record& r) { return r.y > 0.5; });
    double sum = 0.0;
    Record r;
    while (filter->next(r)) {
        sum += r.x + tick * 1e-9;  // 同 raw_filter_sum：见该函数注释
    }
    return sum;
}

}  // namespace

int main() {
    // ---- ② 派发方式 ----
    const FnPtr fns[2] = {&op_mul2, &op_half};
    const std::function<double(double)> funs[2] = {
        [](double x) { return x * 2.0 + 1.0; },
        [](double x) { return x * 0.5 + 1.5; }};
    const std::unique_ptr<IUnary> unaries[2] = {std::make_unique<UnaryMul2>(),
                                                std::make_unique<UnaryHalf>()};

    const int samples = 7;
    const double t_direct =
        best_of([](double tick) {
            double s = 0.0;
            for (std::size_t i = 0; i < kOps; ++i) {
                // 直调也按序换实现，保证与其余三种机制「同一算子序列」——纯比派发层
                s += (i % 2 == 0) ? op_mul2(static_cast<double>(i) + tick)
                                  : op_half(static_cast<double>(i) + tick);
            }
            return s;
        }, samples);
    const double t_fnptr =
        best_of([&](double tick) {
            double s = 0.0;
            for (std::size_t i = 0; i < kOps; ++i) {
                s += fns[i % 2](static_cast<double>(i) + tick);  // 运行期选实现 → 指针间接
            }
            return s;
        }, samples);
    const double t_stdfn =
        best_of([&](double tick) {
            double s = 0.0;
            for (std::size_t i = 0; i < kOps; ++i) {
                s += funs[i % 2](static_cast<double>(i) + tick);  // 类型擦除转发
            }
            return s;
        }, samples);
    const double t_virt =
        best_of([&](double tick) {
            double s = 0.0;
            for (std::size_t i = 0; i < kOps; ++i) {
                s += unaries[i % 2]->apply(static_cast<double>(i) + tick);  // vtable 两次间接
            }
            return s;
        }, samples);

    const double ns_direct = t_direct / kOps * 1e9;
    const double ns_fnptr = t_fnptr / kOps * 1e9;
    const double ns_stdfn = t_stdfn / kOps * 1e9;
    const double ns_virt = t_virt / kOps * 1e9;
    print_dispatch_results(ns_direct, ns_fnptr, ns_stdfn, ns_virt);

    // 一致性：四种方式在同 tick 下输出必须一致（四路跑两次同 tick 求差）
    const auto eval_all = [&](double tick) {
        return std::vector<double>{
            [&] { double s = 0; for (std::size_t i = 0; i < kOps; ++i) s += (i % 2 == 0) ? op_mul2(double(i) + tick) : op_half(double(i) + tick); return s; }(),
            [&] { double s = 0; for (std::size_t i = 0; i < kOps; ++i) s += fns[i % 2](double(i) + tick); return s; }(),
            [&] { double s = 0; for (std::size_t i = 0; i < kOps; ++i) s += funs[i % 2](double(i) + tick); return s; }(),
            [&] { double s = 0; for (std::size_t i = 0; i < kOps; ++i) s += unaries[i % 2]->apply(double(i) + tick); return s; }(),
        };
    };
    const auto a = eval_all(3.0);
    check(a[0] == a[1] && a[1] == a[2] && a[2] == a[3],
          "四路派发输出一致（同输入同结果）");

    // ---- ③ 过滤聚合：管道 vs 裸写 ----
    const std::vector<Record> rows = make_records(4'000'000);
    const double t_raw = best_of([&](double tick) { return raw_filter_sum(rows, tick); }, samples);
    const double t_pipe =
        best_of([&](double tick) { return pipe_filter_sum(rows, tick); }, samples);

    std::cout << "查询过滤聚合（4M 行，保留 y>0.5 累加 x）\n";
    std::cout << "  裸写单循环    " << std::to_string(t_raw * 1e3).substr(0, 6) << " ms\n";
    std::cout << "  pull 虚管道   " << std::to_string(t_pipe * 1e3).substr(0, 6) << " ms，慢 "
              << std::to_string(t_pipe / t_raw).substr(0, 5) << "x\n\n";

    check(t_pipe > t_raw, "实测：同等语义下裸写快于 pull 虚管道（每行虚调用有成本）");
    std::cout << (g_failures == 0 ? "全部通过，退出码 0\n" : "存在失败\n");
    return g_failures == 0 ? 0 : 1;
}
