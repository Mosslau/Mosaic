// main.cpp —— ph23 project：vsearch 库的自测 + benchmark 驱动
// 两种模式：
//   vsearch selftest                  → 断言自测（验收入口之一）
//   vsearch bench [N] [DIM] [NQ] [K] [l2|ip|cosine]
//                                     → 实测输出 recall / QPS / P95 延迟 / 内存占用
// bench 说明：
//   - 数据与查询都用固定随机种子生成（可复现，不臆造数字）；
//   - recall 由"独立的 double 全排序 ground truth"逐 query 对照（不是自己证自己）；
//   - 每次查询单独计时 → 排序样本取 P50/P95/P99；QPS = 查询数 / 总耗时；
//   - 内存报两项：索引自身 memory_bytes()（账本）与进程峰值 RSS ru_maxrss（含一切）。
// 编译/运行见 Makefile（make test / make bench / make bench_scalar 对照 SIMD 收益）。
#include "vsearch.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

#include <sys/resource.h>
#include <unistd.h>

#if defined(__ARM_NEON) && !defined(VSEARCH_FORCE_SCALAR)
#define PH23_SIMD_LABEL "NEON"
#else
#define PH23_SIMD_LABEL "scalar"
#endif

namespace {

double now_us() {
    using namespace std::chrono;
    return static_cast<double>(
        duration_cast<microseconds>(steady_clock::now().time_since_epoch()).count());
}

double peak_rss_mib() {          // macOS ru_maxrss 单位 = 字节；Linux = KB
    struct rusage ru {};
    if (getrusage(RUSAGE_SELF, &ru) != 0) return 0.0;
#if defined(__APPLE__)
    return static_cast<double>(ru.ru_maxrss) / 1048576.0;
#else
    return static_cast<double>(ru.ru_maxrss) / 1024.0;
#endif
}

std::vector<float> fill_rng(std::size_t n, std::uint32_t seed) {
    std::mt19937 rng(seed);
    std::uniform_real_distribution<float> uni(0.0f, 1.0f);
    std::vector<float> v(n);
    for (auto& x : v) x = uni(rng);
    return v;
}

// —— 独立 ground truth：double 全排序（不调用 vsearch 内部，避免自证）——
std::vector<std::vector<std::int64_t>> ground_truth(const std::vector<float>& db,
                                                    std::size_t dim, std::size_t n,
                                                    const std::vector<float>& qs,
                                                    std::size_t nq, std::size_t k) {
    std::vector<std::vector<std::int64_t>> out(nq);
    for (std::size_t qi = 0; qi < nq; ++qi) {
        const float* q = qs.data() + qi * dim;
        std::vector<std::pair<double, std::int64_t>> all(n);
        for (std::size_t i = 0; i < n; ++i) {
            const float* r = db.data() + i * dim;
            double s = 0.0;
            for (std::size_t d = 0; d < dim; ++d) {
                const double t = static_cast<double>(r[d]) - static_cast<double>(q[d]);
                s += t * t;
            }
            all[i] = {s, static_cast<std::int64_t>(i)};
        }
        std::partial_sort(all.begin(), all.begin() + static_cast<std::ptrdiff_t>(k), all.end());
        for (std::size_t j = 0; j < k; ++j) out[qi].push_back(all[j].second);
    }
    return out;
}

void run_selftest() {
    using namespace vsearch;
    constexpr std::size_t dim = 8;
    std::vector<float> v1{1, 0, 0, 0, 0, 0, 0, 0};
    std::vector<float> v2{0, 1, 0, 0, 0, 0, 0, 0};
    std::vector<float> v3{0.6f, 0.8f, 0, 0, 0, 0, 0, 0};
    std::vector<float> v4{3, 0, 0, 0, 0, 0, 0, 0};   // 与 v1 同方向、长度×3

    // [1] metric 正确性：cosine 把"同向长向量"与"同向单位向量"打成平手（长度无关），
    //     而 IP 会让长向量（v4）明显胜出——两种度量对长度敏感性的对照。
    {
        flat_index idx_c(dim, metric::cosine);
        idx_c.add(1, v1);
        idx_c.add(2, v2);
        idx_c.add(3, v3);
        idx_c.add(4, v4);
        const auto rc = idx_c.search(v1, 4);        // query = v1
        bool has1 = false, has4 = false;
        for (std::size_t j = 0; j < 2; ++j) {       // top2 应同时含 v1、v4（余弦都 = 1）
            has1 |= (rc[j].id == 1);
            has4 |= (rc[j].id == 4);
            if (std::fabs(rc[j].score - 1.0f) > 1e-4f)
                throw std::runtime_error("selftest: cos(·, v1)=1 的向量分数应为 1");
        }
        if (!has1 || !has4)
            throw std::runtime_error("selftest: cosine 下同向 v1/v4 应并列 top2（长度无关）");
        std::printf("selftest [1] cosine 长度无关性 ✓（v4 长度为 v1×3 仍与 v1 并列）\n");

        flat_index idx_ip(dim, metric::ip);
        idx_ip.add(1, v1);
        idx_ip.add(4, v4);
        const auto ri = idx_ip.search(v1, 2);
        if (ri.empty() || ri[0].id != 4)
            throw std::runtime_error("selftest: IP 应让长向量 v4 排第一");
        std::printf("selftest [1] ip 保留长度偏好 ✓（同 query 下 v4 的 IP=%.1f > v1 的 IP=1）\n",
                    static_cast<double>(ri[0].score));
    }

    // [2] l2 与独立 double ground truth 一致（随机子集）
    {
        constexpr std::size_t n = 2000, nq = 20, k = 5;
        const auto db = fill_rng(n * dim, 41u);
        const auto qs = fill_rng(nq * dim, 42u);
        flat_index idx(dim, metric::l2);
        for (std::size_t i = 0; i < n; ++i)
            idx.add(static_cast<std::int64_t>(i), std::vector<float>(db.begin() + static_cast<std::ptrdiff_t>(i * dim), db.begin() + static_cast<std::ptrdiff_t>((i + 1) * dim)));
        const auto gt = ground_truth(db, dim, n, qs, nq, k);
        for (std::size_t qi = 0; qi < nq; ++qi) {
            const std::vector<float> q(qs.begin() + static_cast<std::ptrdiff_t>(qi * dim),
                                       qs.begin() + static_cast<std::ptrdiff_t>((qi + 1) * dim));
            const auto r = idx.search(q, k);
            if (r.size() != k) throw std::runtime_error("selftest: top-k size");
            for (std::size_t j = 0; j < k; ++j)
                if (r[j].id != gt[qi][j]) {
                    std::printf("mismatch qi=%zu j=%zu got=%lld want=%lld\n", qi, j,
                                static_cast<long long>(r[j].id), static_cast<long long>(gt[qi][j]));
                    throw std::runtime_error("selftest: l2 top-k 与 double ground truth 不一致");
                }
        }
        std::printf("selftest [2] l2 检索与独立 double ground truth 一致 ✓ (%zu queries)\n", nq);
    }

    // [3] 持久化 round-trip + 篡改检测（临时文件 /tmp，退出自删）
    {
        const std::string path = "/tmp/ph23-vsearch-selftest.bin";
        std::remove(path.c_str());
        std::remove((path + ".tmp").c_str());
        constexpr std::size_t n = 500;
        const auto db = fill_rng(n * dim, 7u);
        flat_index idx(dim, metric::l2);
        for (std::size_t i = 0; i < n; ++i)
            idx.add(static_cast<std::int64_t>(1000 + i),
                    std::vector<float>(db.begin() + static_cast<std::ptrdiff_t>(i * dim),
                                       db.begin() + static_cast<std::ptrdiff_t>((i + 1) * dim)));
        idx.save(path);
        auto back = flat_index::load(path);
        if (back.size() != n || back.dim() != dim) throw std::runtime_error("selftest: reload meta");
        const auto q = fill_rng(dim, 8u);
        const auto r1 = idx.search(q, 3);
        const auto r2 = back.search(q, 3);
        for (std::size_t j = 0; j < r1.size(); ++j) {
            if (r1[j].id != r2[j].id || std::fabs(r1[j].score - r2[j].score) > 1e-3f)
                throw std::runtime_error("selftest: reload 后检索不一致");
        }
        std::printf("selftest [3] save/load round-trip ✓ (snapshot 字节=%zu)\n",
                    static_cast<std::size_t>([&] {
                        std::ifstream in(path, std::ios::binary | std::ios::ate);
                        return in.tellg();
                    }()));
        // 篡改数据区一字节 → load 必须抛错（SSTable 纪律：损坏即拒绝服务）
        {
            std::fstream fs(path, std::ios::binary | std::ios::in | std::ios::out);
            fs.seekp(30);
            const char c = 'X';
            fs.write(&c, 1);
            fs.close();
            bool caught = false;
            try {
                (void)flat_index::load(path);
            } catch (const std::runtime_error&) {
                caught = true;
            }
            if (!caught) throw std::runtime_error("selftest: 篡改未被校验拦截");
            std::printf("selftest [3] 篡改一字节 → load 抛错 ✓\n");
        }
        std::remove(path.c_str());
    }
    std::printf("ph23-vsearch selftest OK\n");
}

void run_bench(std::size_t n, std::size_t dim, std::size_t nq, std::size_t k,
               vsearch::metric m) {
    using namespace vsearch;
    const auto db = fill_rng(n * dim, 2024u);
    const auto qs = fill_rng(nq * dim, 2025u);

    flat_index idx(dim, m);
    const double t_add0 = now_us();
    for (std::size_t i = 0; i < n; ++i)
        idx.add(static_cast<std::int64_t>(i),
                std::vector<float>(db.begin() + static_cast<std::ptrdiff_t>(i * dim),
                                   db.begin() + static_cast<std::ptrdiff_t>((i + 1) * dim)));
    const double t_add1 = now_us();

    // 预热
    volatile std::size_t sink = 0;
    for (std::size_t i = 0; i < 20; ++i)
        sink += idx.search(std::vector<float>(qs.begin() + static_cast<std::ptrdiff_t>((i % nq) * dim),
                                              qs.begin() + static_cast<std::ptrdiff_t>((i % nq) * dim + dim)),
                           k).size();

    // 逐 query 计时
    std::vector<double> lats;
    lats.reserve(nq);
    std::vector<std::vector<result>> hits(nq);
    for (std::size_t qi = 0; qi < nq; ++qi) {
        const std::vector<float> q(qs.begin() + static_cast<std::ptrdiff_t>(qi * dim),
                                   qs.begin() + static_cast<std::ptrdiff_t>((qi + 1) * dim));
        const double t0 = now_us();
        hits[qi] = idx.search(q, k);
        const double t1 = now_us();
        lats.push_back(t1 - t0);
    }
    std::vector<double> sorted = lats;
    std::sort(sorted.begin(), sorted.end());
    auto pct = [&](double p) {
        const std::size_t i = static_cast<std::size_t>(p * static_cast<double>(sorted.size() - 1));
        return sorted[i];
    };
    double total_us = 0.0;
    for (const double l : lats) total_us += l;

    // recall vs 独立 double ground truth（前 min(nq, 50) 个 query，控制自测时长）
    const std::size_t check_q = std::min<std::size_t>(nq, 50);
    const auto gt = ground_truth(db, dim, n, qs, check_q, k);
    double recall_sum = 0.0;
    for (std::size_t qi = 0; qi < check_q; ++qi) {
        std::size_t inter = 0;
        for (const auto& h : hits[qi]) {
            for (std::size_t j = 0; j < k; ++j)
                if (h.id == gt[qi][j]) {
                    ++inter;
                    break;
                }
        }
        recall_sum += static_cast<double>(inter) / static_cast<double>(k);
    }

    std::printf("== vsearch bench: n=%zu dim=%zu nq=%zu k=%zu metric=%s backend=%s ==\n", n,
                dim, nq, k, idx.metric_name(), PH23_SIMD_LABEL);
    std::printf("build(仅 add):  %.1f ms | 索引内存账本 %.1f MiB | 进程峰值 RSS %.1f MiB\n",
                (t_add1 - t_add0) / 1000.0, idx.memory_bytes() / 1048576.0, peak_rss_mib());
    std::printf("recall@%zu   :  %.4f（精确检索，对照独立 double ground truth）\n", k,
                recall_sum / static_cast<double>(check_q));
    std::printf("QPS         :  %.0f\n", nq * 1e6 / total_us);
    std::printf("latency     :  P50 %.0f µs | P95 %.0f µs | P99 %.0f µs\n", pct(0.50), pct(0.95),
                pct(0.99));
    std::printf("(sink=%zu)\n", sink);
}

}  // namespace

int main(int argc, char** argv) {
    const std::string mode = argc > 1 ? argv[1] : "selftest";
    if (mode == "selftest") {
        run_selftest();
        return 0;
    }
    if (mode == "bench") {
        std::size_t n = argc > 2 ? std::strtoull(argv[2], nullptr, 10) : 100000;
        std::size_t dim = argc > 3 ? std::strtoull(argv[3], nullptr, 10) : 64;
        std::size_t nq = argc > 4 ? std::strtoull(argv[4], nullptr, 10) : 300;
        std::size_t k = argc > 5 ? std::strtoull(argv[5], nullptr, 10) : 10;
        const std::string metric_s = argc > 6 ? argv[6] : "l2";
        vsearch::metric m = vsearch::metric::l2;
        if (metric_s == "ip") m = vsearch::metric::ip;
        if (metric_s == "cosine") m = vsearch::metric::cosine;
        if (dim == 0 || n == 0 || nq == 0 || k == 0)
            throw std::invalid_argument("bench 参数须为正数");
        run_bench(n, dim, nq, k, m);
        return 0;
    }
    std::printf("用法: %s selftest | %s bench [N] [DIM] [NQ] [K] [l2|ip|cosine]\n", argv[0],
                argv[0]);
    return 2;
}
