// sol-05-faiss-recall.cpp —— 练习 5 参考实现：Faiss IVF / HNSW 的 recall-QPS 扫描表
// 对应 roadmap §23「使用 Faiss 建立 IVF / HNSW 索引并测试召回率」。
// 与 examples/ex07 的分工：ex07 用聚类高斯数据展示"参数旋钮曲线"；本解用均匀随机数据
//   扫 nprobe ∈ {1,10,100} 与 efSearch ∈ {16,64,256} 输出表——同样验证"Flat 恒 1.0、
//   nprobe/efSearch 增大 → recall 与耗时同向"。
// 本机无 brew faiss：验证走 /tmp 源码构建（faiss 1.9.0，摘除 OpenMP 依赖 + omp 桩，
//   单线程 generic 构建）——绝对 QPS 与官方发行版不同，请看曲线不看绝对值。
// 验证环境：macOS arm64，Faiss 1.9.0（/tmp 源码构建）+ Apple clang 21.0.0。
// 编译命令：
//   clang++ -std=c++17 -O2 -Wall -Wextra sol-05-faiss-recall.cpp \
//       -I/tmp/faiss-install/include -I/tmp/omp-stub \
//       -L/tmp/faiss-install/lib -L/tmp/omp-stub -lfaiss -lompstub \
//       -framework Accelerate -o /tmp/ph23-sol05
//   （brew install faiss 的机器简化为：... -lfaiss，去掉 omp 桩与手动 include）
// 运行命令：/tmp/ph23-sol05
// 验证状态：已验证（输出节选：IVF recall 0.09/0.44/1.00 @ 16/58/457µs；HNSW recall
//   0.36/0.71/0.95 @ 39/144/723µs；Flat recall=1.0 @ 59µs——recall 与耗时同向上移）

#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <random>
#include <string>
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

double run_recall_qps(faiss::Index& idx, const std::vector<float>& xq, std::size_t nq,
                      std::size_t k, const std::vector<faiss::idx_t>& gt,
                      std::vector<float>* last_dist) {
    std::vector<faiss::idx_t> ids(nq * k);
    std::vector<float> dist(nq * k);
    const double t0 = now_us();
    idx.search(static_cast<faiss::idx_t>(nq), xq.data(), static_cast<faiss::idx_t>(k),
               dist.data(), ids.data());
    const double t1 = now_us();
    if (last_dist) *last_dist = std::move(dist);

    double hits = 0.0;
    for (std::size_t i = 0; i < nq; ++i)
        for (std::size_t j = 0; j < k; ++j)
            for (std::size_t g = 0; g < k; ++g)
                if (ids[i * k + j] == gt[i * k + g]) {
                    ++hits;
                    break;
                }
    const double recall = hits / (static_cast<double>(nq) * static_cast<double>(k));
    std::printf("    recall@%zu=%.4f   %9.1f µs/query   %8.0f QPS\n", k, recall,
                (t1 - t0) / nq, nq * 1e6 / (t1 - t0));
    return recall;
}

}  // namespace

int main() {
    // —— 数据集：可复现 ——
    constexpr std::size_t dim = 64;
    constexpr std::size_t n = 100000;
    constexpr std::size_t nq = 200;
    constexpr std::size_t k = 10;

    std::mt19937 rng(777u);
    std::uniform_real_distribution<float> uni(0.0f, 1.0f);
    std::vector<float> xb(n * dim), xq(nq * dim);
    for (auto& x : xb) x = uni(rng);
    for (auto& x : xq) x = uni(rng);

    // ground truth
    faiss::IndexFlatL2 flat(dim);
    flat.add(static_cast<faiss::idx_t>(n), xb.data());
    std::vector<faiss::idx_t> gt(nq * k);
    std::vector<float> gt_d(nq * k);
    flat.search(static_cast<faiss::idx_t>(nq), xq.data(), static_cast<faiss::idx_t>(k),
                gt_d.data(), gt.data());

    std::printf("Faiss recall 扫描: n=%zu dim=%zu nq=%zu k=%zu\n", n, dim, nq, k);

    // [1] Flat 恒为精确 → recall 必须 = 1.0
    std::printf("[1] Flat(L2) 精确基线:\n");
    std::vector<float> last_dist;
    const double flat_recall =
        run_recall_qps(flat, xq, nq, k, gt, &last_dist);
    if (std::fabs(flat_recall - 1.0) > 1e-9)
        std::printf("    [警告] Flat recall 应恒为 1.0（本值 %.4f 说明 ground truth 不严）\n",
                    flat_recall);

    // [2] IVF: nprobe 扫描
    std::printf("[2] IVFFlat(nlist=100), nprobe 扫描:\n");
    for (const std::size_t nprobe : {1u, 10u, 100u}) {
        std::unique_ptr<faiss::Index> ivf(faiss::index_factory(
            static_cast<int>(dim), "IVF100,Flat", faiss::METRIC_L2));
        ivf->train(static_cast<faiss::idx_t>(n), xb.data());
        ivf->add(static_cast<faiss::idx_t>(n), xb.data());
        if (auto* f = dynamic_cast<faiss::IndexIVFFlat*>(ivf.get())) f->nprobe = nprobe;
        std::printf("    nprobe=%3zu: ", nprobe);
        run_recall_qps(*ivf, xq, nq, k, gt, nullptr);
    }

    // [3] HNSW: efSearch 扫描
    std::printf("[3] HNSW(M=32), efSearch 扫描:\n");
    for (const std::size_t ef : {16u, 64u, 256u}) {
        std::unique_ptr<faiss::Index> h(faiss::index_factory(
            static_cast<int>(dim), "HNSW32,Flat", faiss::METRIC_L2));
        h->add(static_cast<faiss::idx_t>(n), xb.data());
        if (auto* hh = dynamic_cast<faiss::IndexHNSW*>(h.get())) hh->hnsw.efSearch = ef;
        std::printf("    efSearch=%3zu: ", ef);
        run_recall_qps(*h, xq, nq, k, gt, nullptr);
    }

    std::printf("结论: Flat 行 recall=1.0（精确检索，无近似参数）；nprobe/efSearch 增大\n");
    std::printf("      → 召回↑ 与 µs/query↑ 同向——「召回率-延迟」是 ANN 的唯一交易对象。\n");
    std::printf("ph23-sol05 done\n");
    return 0;
}
