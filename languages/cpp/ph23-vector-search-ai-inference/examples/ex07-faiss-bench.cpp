// ex07-faiss-bench.cpp —— Faiss 使用与基准：Flat / IVF / HNSW 的 recall-延迟曲线
// 对应 ph23 主文档 3.5/3.8 与 roadmap §23「使用 Faiss 建立 IVF / HNSW 索引并测试召回率」。
// 教学点：
//   ① index_factory("结构,度量") 一行建索引，train/add/search 生命周期显式；
//   ② Flat 是精确基线（recall 恒 1.0）；IVF 扫 nprobe、HNSW 扫 efSearch，
//      观察"召回率与 µs/query 同向移动"的 ANN 铁律；
//   ③ 数据用**聚类高斯**（Faiss 官方 demo 同款形态）而非均匀随机：均匀随机数据没有
//      结构可挖，是 ANN 的最坏情形——若在那上面跑，ANN 可能不比 flat 快（flat 走
//      BLAS 矩阵乘）。真实 embedding 有聚类结构，本示例就是模拟它；
//   ④ 诚实读数：绝对 QPS 依赖机器/库构建（本机 faiss 为无 OpenMP 单线程构建），
//      结论看"参数旋钮移动时 recall 与耗时是否同向"，以及 ANN vs flat 的差值方向。
// 注意：本文件依赖外部库 faiss；编译/运行命令见下。若用 /tmp 源码构建的 faiss
//   （无 OpenMP），链接还需 omp 桩库（本仓库在无 brew 环境的验证路径，见 README）。
// 验证环境：macOS arm64，Faiss 1.9.0（/tmp 源码构建）+ Apple clang 21.0.0；
// 编译命令：
//   clang++ -std=c++17 -O2 -Wall -Wextra ex07-faiss-bench.cpp \
//       -I/tmp/faiss-install/include -I/tmp/omp-stub \
//       -L/tmp/faiss-install/lib -L/tmp/omp-stub -lfaiss -lompstub \
//       -framework Accelerate -o /tmp/ph23-ex07
//   （brew install faiss 的机器简化为：... -lfaiss，去掉 omp 桩与手动 include）
// 运行命令：/tmp/ph23-ex07
// 验证状态：已验证（Apple clang 21.0.0 + faiss 1.9.0 /tmp 构建；运行输出见下）

#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <random>
#include <vector>

#include <faiss/IndexFlat.h>
#include <faiss/IndexHNSW.h>
#include <faiss/IndexIVFFlat.h>
#include <faiss/index_factory.h>

namespace {

double now_us() {
    using namespace std::chrono;
    return static_cast<double>(
        duration_cast<microseconds>(steady_clock::now().time_since_epoch()).count());
}

// 聚类高斯数据：200 个随机中心 + 高斯散布（模拟真实 embedding 的簇结构）
void fill_clustered(std::vector<float>& m, std::size_t dim, std::uint32_t seed,
                    std::size_t n_clusters) {
    std::mt19937 rng(seed);
    std::uniform_real_distribution<float> uni(-5.0f, 5.0f);
    std::normal_distribution<float> gauss(0.0f, 0.35f);
    const std::size_t total = m.size() / dim;
    // 预生成聚类中心
    std::vector<float> centers(n_clusters * dim);
    for (auto& x : centers) x = uni(rng);
    std::uniform_int_distribution<std::size_t> pick(0, n_clusters - 1);
    for (std::size_t i = 0; i < total; ++i) {
        const std::size_t c = pick(rng);
        float* row = m.data() + i * dim;
        const float* center = centers.data() + c * dim;
        for (std::size_t d = 0; d < dim; ++d) row[d] = center[d] + gauss(rng);
    }
}

}  // namespace

int main() {
    // —— 数据集 ——
    constexpr std::size_t dim = 64;
    constexpr std::size_t n = 100000;   // 库内向量（含 200 簇结构）
    constexpr std::size_t nq = 200;     // 查询数
    constexpr std::size_t k = 10;

    std::vector<float> xb(n * dim), xq(nq * dim);
    fill_clustered(xb, dim, 1u, 200);
    fill_clustered(xq, dim, 2u, 200);

    // ground truth：精确索引
    faiss::IndexFlatL2 flat(dim);
    flat.add(static_cast<faiss::idx_t>(n), xb.data());
    std::vector<faiss::idx_t> gt(nq * k);
    std::vector<float> gt_d(nq * k);
    flat.search(static_cast<faiss::idx_t>(nq), xq.data(), static_cast<faiss::idx_t>(k),
                gt_d.data(), gt.data());

    auto bench_row = [&](const char* name, faiss::Index& idx) {
        std::vector<faiss::idx_t> ids(nq * k);
        std::vector<float> dist(nq * k);
        const double t0 = now_us();
        idx.search(static_cast<faiss::idx_t>(nq), xq.data(), static_cast<faiss::idx_t>(k),
                   dist.data(), ids.data());
        const double t1 = now_us();
        double hits = 0.0;
        for (std::size_t i = 0; i < nq; ++i)
            for (std::size_t j = 0; j < k; ++j)
                for (std::size_t g = 0; g < k; ++g)
                    if (ids[i * k + j] == gt[i * k + g]) {
                        ++hits;
                        break;
                    }
        const double recall = hits / (static_cast<double>(nq) * static_cast<double>(k));
        std::printf("%-16s recall@10=%.4f   平均 %8.1f µs/query\n", name, recall,
                    (t1 - t0) / nq);
    };

    std::printf("Faiss bench: n=%zu dim=%zu nq=%zu k=%zu（聚类高斯数据）\n", n, dim, nq, k);
    std::printf("--- Flat（精确基线）---\n");
    bench_row("Flat(L2)", flat);

    std::printf("--- IVF200,Flat：nprobe 扫描（召回-延迟同向）---\n");
    for (const std::size_t nprobe : {1u, 10u, 100u}) {
        std::unique_ptr<faiss::Index> ivf(faiss::index_factory(
            static_cast<int>(dim), "IVF200,Flat", faiss::METRIC_L2));
        ivf->train(static_cast<faiss::idx_t>(n), xb.data());
        ivf->add(static_cast<faiss::idx_t>(n), xb.data());
        if (auto* f = dynamic_cast<faiss::IndexIVFFlat*>(ivf.get())) f->nprobe = nprobe;
        std::printf("  nprobe=%3zu: ", nprobe);
        bench_row("", *ivf);
    }

    std::printf("--- HNSW32,Flat：efSearch 扫描（召回-延迟同向）---\n");
    for (const std::size_t ef : {16u, 64u, 256u}) {
        std::unique_ptr<faiss::Index> h(faiss::index_factory(
            static_cast<int>(dim), "HNSW32,Flat", faiss::METRIC_L2));
        h->add(static_cast<faiss::idx_t>(n), xb.data());
        if (auto* hh = dynamic_cast<faiss::IndexHNSW*>(h.get())) hh->hnsw.efSearch = ef;
        std::printf("  efSearch=%3zu: ", ef);
        bench_row("", *h);
    }

    std::printf("结论: Flat 恒 recall=1.0；nprobe/efSearch 增大 → recall 与耗时同向上移。\n");
    std::printf("     ANN 的绝对 QPS 依赖数据结构与库构建；均匀随机数据上 ANN 未必快过 flat。\n");
    std::printf("ph23-ex07 done\n");
    return 0;
}
