// examples/ex03-profiling-demo.cpp —— 插桩式剖析（manual instrumentation）教学版
// 教学点：roadmap 必会概念「先测量，再优化」。真实采样剖析器（perf/Tracy，
// 见主文档 3.2/3.3）是外挂进程、零代码侵入；本示例演示**没有剖析器时的替代品**：
// 在代码里埋 ScopeTimer，把一条数据管线的每个阶段分别计时、多轮累计后打印占比，
// 用一份「耗时分布表」代替拍脑袋猜热点。结论要先看数据再下。
//
// 验证环境：macOS arm64，Apple clang 21.0.0 / Homebrew clang 21.1.8，libc++
// 编译：
//   clang++ -std=c++20 -O2 -Wall -Wextra ex03-profiling-demo.cpp -o /tmp/ph18cpp-ex03
// 运行：/tmp/ph18cpp-ex03 [passes]（默认 2 轮；可传参数缩短教学演示）
// 预期输出：三个阶段各自的累计耗时/调用次数/占比 + 校验和一致，退出码 0
// 验证状态：已验证（双编译器 -O2 实测：编译零警告、运行通过；
//   本机 1M 行 × 2 轮：字符串构建阶段占比通常 >60%，为最热阶段）
//
// 关于剖析方法的诚实边界：插桩计时只告诉你「各阶段总时长」，回答不了
// 「时间花在哪个函数哪一行」（那要采样剖析器按 PC 回溯）。两者互补。
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

namespace {

using Clock = std::chrono::steady_clock;

struct Row {
    std::int64_t id;
    double x;
    double y;
};

// ---- 极简插桩计时器：进入作用域开始计时，退出时累加到 PhaseAccum ----
struct PhaseAccum {
    const char* name;
    double seconds = 0.0;
    int calls = 0;
};

class ScopedTimer {
public:
    explicit ScopedTimer(PhaseAccum& acc) : acc_(acc), t0_(Clock::now()) {}
    ~ScopedTimer() {
        acc_.seconds += std::chrono::duration<double>(Clock::now() - t0_).count();
        ++acc_.calls;
    }

private:
    PhaseAccum& acc_;
    Clock::time_point t0_;
};

// 生成 1M 行确定性数据：LCG 伪随机，避免 <random> 的分布对象干扰插桩结果。
void generate_rows(std::vector<Row>& rows, std::size_t n) {
    std::uint64_t state = 0x9E3779B97F4A7C15ULL;  // 黄金分割常数做种子
    rows.resize(n);
    for (std::size_t i = 0; i < n; ++i) {
        state = state * 6364136223846793005ULL + 1442695040888963407ULL;
        const double u = static_cast<double>(state >> 11) / static_cast<double>(1ULL << 53);
        state = state * 6364136223846793005ULL + 1442695040888963407ULL;
        const double v = static_cast<double>(state >> 11) / static_cast<double>(1ULL << 53);
        rows[i] = Row{static_cast<std::int64_t>(i), u, v};
    }
}

// 扫描 + 过滤 + 聚合：只保留 y > 0.5 的行，累加 x。纯算术，快的阶段。
double filter_sum(const std::vector<Row>& rows) {
    double sum = 0.0;
    for (const Row& r : rows) {
        if (r.y > 0.5) {
            sum += r.x;
        }
    }
    return sum;
}

// 每行构建一次字符串：to_string + emplace_back。堆分配密集，通常是最热阶段。
std::size_t string_build(const std::vector<Row>& rows) {
    std::vector<std::string> out;
    out.reserve(rows.size());  // 只消掉 vector 自身的扩容分配，字符串载荷分配仍在
    for (const Row& r : rows) {
        out.emplace_back(std::to_string(r.id));  // 每个字符串一次堆分配（libc++ SSO 上限 22 B，id 短串大概率走 SSO）
    }
    std::size_t total_len = 0;
    for (const std::string& s : out) {
        total_len += s.size();
    }
    return total_len;
}

// 计算 id 0..n-1 十进制位数的算术期望（与 string_build 里 to_string 的长度等价），
// 用于校验字符串阶段没有算错，纯整数运算不产生分配。
std::size_t expected_digit_length(std::size_t n) {
    std::size_t sum = 0;
    for (std::size_t i = 0; i < n; ++i) {
        std::size_t v = i;
        std::size_t digits = 1;
        while (v >= 10) {
            v /= 10;
            ++digits;
        }
        sum += digits;
    }
    return sum;
}

}  // namespace

int main(int argc, char** argv) {
    const int passes = (argc > 1) ? std::max(1, std::stoi(argv[1])) : 2;
    constexpr std::size_t kRows = 1'000'000;

    PhaseAccum acc_gen{"生成数据", 0.0, 0};
    PhaseAccum acc_filter{"过滤聚合", 0.0, 0};
    PhaseAccum acc_string{"字符串构建", 0.0, 0};

    std::vector<Row> rows;
    double checksum = 0.0;
    std::size_t len_sum = 0;

    for (int p = 0; p < passes; ++p) {
        {
            ScopedTimer t(acc_gen);
            generate_rows(rows, kRows);
        }
        {
            ScopedTimer t(acc_filter);
            checksum += filter_sum(rows);
        }
        {
            ScopedTimer t(acc_string);
            len_sum += string_build(rows);
        }
    }

    const PhaseAccum* accs[] = {&acc_gen, &acc_filter, &acc_string};
    const double total = acc_gen.seconds + acc_filter.seconds + acc_string.seconds;

    std::cout << "插桩式剖析报告（" << kRows << " 行 × " << passes << " 轮）\n";
    std::cout << "阶段          累计耗时(ms)  调用次数   占比\n";
    for (const PhaseAccum* a : accs) {
        std::cout << a->name << "      " << std::to_string(a->seconds * 1e3).substr(0, 7)
                  << "        " << a->calls << "        "
                  << std::to_string(a->seconds / total * 100.0).substr(0, 5) << "%\n";
    }
    std::cout << "------------------------------------------------------\n";
    std::cout << "校验和：过滤聚合累计 " << std::to_string(checksum).substr(0, 8)
              << "，字符串长度累计 " << len_sum << '\n';

    // 断言只覆盖正确性与「计时器确实工作了」，不锁死耗时排序——不同机器上
    // 各阶段占比可能不同，教学结论是「以这份数据为据决定优化哪个阶段」。
    const bool timers_worked = (acc_gen.seconds > 0.0) && (acc_filter.seconds > 0.0) &&
                               (acc_string.seconds > 0.0);
    const bool length_ok =
        len_sum == static_cast<std::size_t>(passes) * expected_digit_length(kRows);
    std::cout << (timers_worked ? "[通过] " : "[失败] ") << "三个阶段计时器均有累计耗时\n";
    std::cout << (length_ok ? "[通过] " : "[失败] ") << "字符串长度校验和一致\n";
    std::cout << (timers_worked && length_ok ? "全部通过，退出码 0\n" : "存在失败\n");
    return (timers_worked && length_ok) ? 0 : 1;
}
