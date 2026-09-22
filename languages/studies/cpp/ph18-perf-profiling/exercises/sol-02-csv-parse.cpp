// exercises/sol-02-csv-parse.cpp —— 练习 2 参考实现：CSV 解析优化（零拷贝 + from_chars）
// 对应题目：exercises/README.md 练习 2（roadmap §18 练习「优化 JSON/CSV 解析」）。
// 教学点：同一份 10 万行 CSV「id,name,score」，统计 id 为偶数的行的 score 之和——
//   基线：每行构造 istringstream + 逐字段 std::string（每字段一次分配）+ std::stod
//   优化：对 string_view 单遍扫描，字段用 std::from_chars 直读（零分配、无 locale）
// 实测吞吐差一个数量级很正常。优化后字段解析不经过「先造字符串再转换」的中间态。
//
// 验证环境：macOS arm64，Apple clang 21.0.0，libc++（C++20）
// 编译：clang++ -std=c++20 -O2 -Wall -Wextra sol-02-csv-parse.cpp -o /tmp/ph18sol-02
// 运行：/tmp/ph18sol-02
// 验证状态：已验证（本机实测：10 万行，基线约 11 ms（171 MB/s）、优化约 3 ms
//   （616 MB/s），快约 3.6 倍，结果一致）
#include <algorithm>
#include <charconv>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <random>
#include <sstream>
#include <string>
#include <string_view>
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

// ---- 基线：istringstream + std::string 中间态 ----
// 每行都构造一个 istringstream（内部要建 locale 相关状态机），三个字段各自
// 分配一个 std::string；stod 还要再解析一次字符串。三重浪费。
struct Stats {
    std::int64_t count = 0;
    double sum_score = 0.0;
};

Stats parse_baseline(const std::string& csv) {
    Stats stats;
    std::istringstream lines(csv);
    std::string line;
    while (std::getline(lines, line)) {
        std::istringstream row(line);
        std::string id_str;
        std::string name;
        std::string score_str;
        if (!std::getline(row, id_str, ',') || !std::getline(row, name, ',') ||
            !std::getline(row, score_str)) {
            continue;  // 教学简化：坏行直接跳过，聚焦解析路径的差异
        }
        const int id = std::stoi(id_str);
        if (id % 2 == 0) {
            stats.sum_score += std::stod(score_str);
            ++stats.count;
        }
    }
    return stats;
}

// ---- 优化：string_view 单遍扫描 + from_chars 直读 ----
// 字段位置用 find 找出来，数值直接用 from_chars 从字符区间解析——
// 不产生任何中间 std::string，也不触碰 locale。
Stats parse_fast(std::string_view csv) {
    Stats stats;
    std::size_t line_start = 0;
    while (line_start < csv.size()) {
        const std::size_t line_end = csv.find('\n', line_start);
        if (line_end == std::string_view::npos) {
            break;
        }
        const std::string_view line = csv.substr(line_start, line_end - line_start);
        line_start = line_end + 1;

        const std::size_t c1 = line.find(',');
        if (c1 == std::string_view::npos) {
            continue;
        }
        const std::size_t c2 = line.find(',', c1 + 1);
        if (c2 == std::string_view::npos) {
            continue;
        }

        int id = 0;
        const auto id_res = std::from_chars(line.data(), line.data() + c1, id);
        if (id_res.ec != std::errc{}) {
            continue;  // 解析失败 → 可诊断处理的最小形态（ph09）
        }
        if (id % 2 != 0) {
            continue;  // 谓词前置：偶数才需要看 score，跳过可省一次解析
        }

        const std::string_view score_view = line.substr(c2 + 1);
        double score = 0.0;
        const auto sc_res =
            std::from_chars(score_view.data(), score_view.data() + score_view.size(), score);
        if (sc_res.ec != std::errc{}) {
            continue;
        }
        stats.sum_score += score;
        ++stats.count;
    }
    return stats;
}

std::string make_csv(std::size_t rows) {
    std::string csv;
    csv.reserve(rows * 24);
    std::mt19937 rng(3);
    std::uniform_int_distribution<int> id_dist(0, 9999);
    std::uniform_real_distribution<double> score_dist(0.0, 100.0);
    static constexpr std::string_view names[] = {"ada", "bob", "carol", "dave", "erin"};
    for (std::size_t i = 0; i < rows; ++i) {
        csv += std::to_string(id_dist(rng));
        csv += ',';
        csv += names[i % std::size(names)];
        csv += ',';
        csv += std::to_string(score_dist(rng));
        csv += '\n';
    }
    return csv;
}

double best_ms(const std::string& csv, Stats& out, bool fast) {
    const auto run = [&] { return fast ? parse_fast(csv) : parse_baseline(csv); };
    out = run();  // 预热 + 首次结果（结果值在 main 中用于一致性断言）
    double best = 1e300;
    for (int r = 0; r < 5; ++r) {
        const auto t0 = Clock::now();
        out = run();  // out 每轮被覆盖——结果「被消费」，不会被整体删除
        const auto t1 = Clock::now();
        best = std::min(best, std::chrono::duration<double, std::milli>(t1 - t0).count());
    }
    return best;
}

bool near(double a, double b) {
    const double scale = std::max(1.0, std::abs(b));
    return std::abs(a - b) < 1e-9 * scale;  // 同一文本，stod 与 from_chars 应逐位一致
}

}  // namespace

int main() {
    const std::string csv = make_csv(100'000);
    const double csv_mb = static_cast<double>(csv.size()) / (1024.0 * 1024.0);

    Stats stats_base;
    Stats stats_fast;
    const double t_base = best_ms(csv, stats_base, /*fast=*/false);
    const double t_fast = best_ms(csv, stats_fast, /*fast=*/true);

    std::cout << "CSV 解析统计（" << csv.size() << " 字节 ≈ " << std::to_string(csv_mb).substr(0, 4)
              << " MB，10 万行）\n";
    std::cout << "  基线 istringstream + 字符串中间态: " << std::to_string(t_base).substr(0, 6)
              << " ms（" << std::to_string(csv_mb / t_base * 1e3).substr(0, 5) << " MB/s）\n";
    std::cout << "  优化 string_view + from_chars:      " << std::to_string(t_fast).substr(0, 6)
              << " ms（" << std::to_string(csv_mb / t_fast * 1e3).substr(0, 5) << " MB/s），快 "
              << std::to_string(t_base / t_fast).substr(0, 5) << "x\n\n";

    check(stats_base.count == stats_fast.count, "两版计数一致");
    check(near(stats_base.sum_score, stats_fast.sum_score), "两版 score 之和一致");
    check(t_fast < t_base, "实测：优化版明显更快");

    std::cout << (g_failures == 0 ? "全部通过，退出码 0\n" : "存在失败\n");
    return g_failures == 0 ? 0 : 1;
}
