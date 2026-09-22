// ex05-metadata-filter.cpp —— 向量 + 标量元数据联合过滤的两种工程形态（search-then-filter vs filter-then-search）
// 对应 ph23 主文档 3.6 与 roadmap §23「metadata filter」。
// 教学点：
//   ① 需求形态：检索不能只看向量相似度——还常要过滤"标签/价格/分类/是否可见"等标量字段，
//      这是生产向量库必答的问题（RAG 里按文档来源过滤、电商按类目过滤都属于它）；
//   ② search-then-filter（先向量后过滤）：全库算距离 → 逐条检查谓词 → 维护 top-k。
//      正确性最简单、对任何谓词都成立，但选择性差（谓词只留 1% 数据时仍付 100% 距离成本）；
//   ③ filter-then-search（先过滤后向量）：给高频过滤键建倒排（tag → id 表），
//      先拿谓词缩小候选集、再只对候选算距离——把"距离次数"从 N 降到 |候选|；
//      代价：每多一个过滤键就要多一张索引，多键谓词还要做集合交并（本示例用 tag 交 + 逐条验 price）；
//   ④ 工程铁律：**过滤后的候选集必须再做一次逐条谓词复查**（候选由 tag 索引给出，price 过滤在
//      扫列表时顺手做；若用多键交集，任何一步的近似都可能放进不满足谓词的点——校验不能省）；
//   ⑤ 实测：同一 query 下两种形态结果逐位一致；选择性（命中比例）决定谁快——命中多时
//      filter-first 也要算很多距离，优势缩小；本示例对选择性高/低两种谓词分别给数字。
// 资源管理：纯 std::vector / 位集，无裸指针（R.11）。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -O2 -Wall -Wextra ex05-metadata-filter.cpp -o /tmp/ph23-ex05 && /tmp/ph23-ex05
// 验证状态：已验证（零警告、断言全绿、退出码 0）

#include <algorithm>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <numeric>
#include <random>
#include <stdexcept>
#include <vector>

namespace meta {

constexpr std::size_t k_tags = 10;   // 标签空间：t0..t9
constexpr std::size_t k_ntag = 3;    // 每个 item 挂的标签数

struct item {
    std::vector<float> vec;   // 向量本体
    float price{0.0f};        // 标量属性
    bool visible{true};       // 布尔过滤（如"软删除/上架"）
    std::uint16_t tagmask{0}; // 位集：第 i 位 = 拥有标签 ti
};

struct hit {
    std::size_t id;
    float dist;
};

// 谓词：标签位集命中 且 price 在 [lo, hi] 且 visible
struct predicate {
    std::uint16_t need_tag{0};
    float price_lo{0.0f};
    float price_hi{1e30f};
};

bool passes(const item& it, const predicate& p) {
    if (!it.visible) return false;
    if ((it.tagmask & p.need_tag) != p.need_tag) return false;
    return it.price >= p.price_lo && it.price <= p.price_hi;
}

// —— 形态 A：search-then-filter（全库算距离，边算边过滤）——
// 谓词检查次数固定 = N，与谓词选择性无关；距离计算只发生在"通过谓词"的条目上。
// pred_checks 输出谓词检查总次数（形态对比的确定性指标，见 main）。
std::vector<hit> stf_topk(const std::vector<item>& db, const std::vector<float>& q,
                          std::size_t k, const predicate& p, std::size_t* pred_checks) {
    std::vector<std::pair<float, std::size_t>> best;  // (dist,id)，小顶堆语义用 vector+sort
    for (std::size_t i = 0; i < db.size(); ++i) {
        if (pred_checks) ++*pred_checks;
        if (!passes(db[i], p)) continue;
        const auto& v = db[i].vec;
        float s = 0.0f;
        for (std::size_t d = 0; d < v.size(); ++d) {
            const float t = v[d] - q[d];
            s += t * t;
        }
        best.push_back({s, i});
    }
    std::sort(best.begin(), best.end());
    std::vector<hit> out;
    const std::size_t take = std::min(k, best.size());
    for (std::size_t j = 0; j < take; ++j) out.push_back({best[j].second, best[j].first});
    return out;
}

// —— 形态 B：filter-then-search（倒排 tag 缩小候选，再算距离）——
// 倒排索引：tag → 全部持该 tag 的 id。对"tag 命中的 id"再逐条复查 price/visible（铁律 ④）。
struct inverted_index {
    explicit inverted_index(const std::vector<item>& db) : db_(db) {
        lists_.assign(k_tags, {});
        for (std::size_t i = 0; i < db.size(); ++i) {
            for (std::size_t t = 0; t < k_tags; ++t) {
                if ((db[i].tagmask >> t) & 1u) lists_[t].push_back(i);
            }
        }
    }
    std::size_t list_size(std::size_t t) const { return lists_[t].size(); }

    std::vector<hit> fts_topk(const std::vector<float>& q, std::size_t k,
                              const predicate& p, std::size_t* pred_checks) const {
        // 多键谓词：先取 need_tag 的倒排表，逐条复查其余条件（教学简化；多键交集见主文档 3.6）
        if (p.need_tag == 0) throw std::invalid_argument("fts needs a tag predicate");
        const std::size_t tag = ctz(p.need_tag);
        std::vector<std::pair<float, std::size_t>> cand;
        cand.reserve(lists_[tag].size());
        for (const std::size_t id : lists_[tag]) {
            if (pred_checks) ++*pred_checks;
            if (!passes(db_[id], p)) continue;   // 复查 price/visible —— 不可省
            const auto& v = db_[id].vec;
            float s = 0.0f;
            for (std::size_t d = 0; d < v.size(); ++d) {
                const float t = v[d] - q[d];
                s += t * t;
            }
            cand.push_back({s, id});
        }
        std::sort(cand.begin(), cand.end());
        std::vector<hit> out;
        const std::size_t take = std::min(k, cand.size());
        for (std::size_t j = 0; j < take; ++j) out.push_back({cand[j].second, cand[j].first});
        return out;
    }

private:
    static std::size_t ctz(std::uint16_t x) {  // 取唯一置位的最低下标（need_tag 单键）
        std::size_t i = 0;
        while (((x >> i) & 1u) == 0) ++i;
        return i;
    }
    const std::vector<item>& db_;
    std::vector<std::vector<std::size_t>> lists_;
};

}  // namespace meta

int main() {
    using namespace meta;
    // —— 数据：可复现 ——
    constexpr std::size_t dim = 16;
    constexpr std::size_t n = 20000;
    std::mt19937 rng(99u);
    std::uniform_real_distribution<float> uni(0.0f, 1.0f);
    std::uniform_int_distribution<int> tag_uni(0, static_cast<int>(k_tags) - 1);
    std::vector<item> db;
    db.reserve(n);
    for (std::size_t i = 0; i < n; ++i) {
        item it;
        it.vec.resize(dim);
        for (auto& x : it.vec) x = uni(rng);
        it.price = uni(rng) * 100.0f;
        it.visible = (i % 10 != 0);             // 90% 可见
        for (int j = 0; j < static_cast<int>(k_ntag); ++j)
            it.tagmask |= static_cast<std::uint16_t>(1u << tag_uni(rng));
        db.push_back(std::move(it));
    }
    std::vector<float> q(dim);
    for (auto& x : q) x = uni(rng);

    // —— 两条谓词：选择性高 / 选择性低 ——
    const predicate selective{static_cast<std::uint16_t>(1u << 3), 0.0f, 8.0f};
    const predicate broad{static_cast<std::uint16_t>(1u << 5), 0.0f, 95.0f};

    auto run = [&](const inverted_index& idx, const predicate& p, const char* name) {
        // A/B 只对"单次查询"计时（倒排索引在循环外只建一次——生产形态）
        const auto tA0 = std::chrono::steady_clock::now();
        std::size_t checks_a = 0;
        const auto ra = stf_topk(db, q, 10, p, &checks_a);
        const auto tA1 = std::chrono::steady_clock::now();
        const auto tB0 = std::chrono::steady_clock::now();
        std::size_t checks_b = 0;
        const auto rb = idx.fts_topk(q, 10, p, &checks_b);
        const auto tB1 = std::chrono::steady_clock::now();

        if (ra.size() != rb.size()) throw std::runtime_error("result size mismatch");
        for (std::size_t j = 0; j < ra.size(); ++j)
            if (ra[j].id != rb[j].id) throw std::runtime_error("result mismatch");
        const double usA = std::chrono::duration<double, std::micro>(tA1 - tA0).count();
        const double usB = std::chrono::duration<double, std::micro>(tB1 - tB0).count();
        std::cout << name << ": 结果两形态逐位一致（top-" << std::min<std::size_t>(10, ra.size())
                  << "）| A=" << usA << "µs / 谓词检查 " << checks_a << " 次 | B=" << usB
                  << "µs / 谓词检查 " << checks_b << " 次\n";
        if (checks_b >= checks_a)
            throw std::runtime_error("倒排形态的谓词检查次数必须严格小于全库扫描");
        return std::pair{usA, usB};
    };

    // 倒排索引只建一次（生产形态：写入时维护，查询不重建）
    const inverted_index idx(db);
    std::cout << "[0] 倒排表规模: t3 表=" << idx.list_size(3)
              << ", t5 表=" << idx.list_size(5) << "（库共 " << n << " 条，每键约 "
              << n * k_ntag / k_tags << " 条）\n";
    const auto s = run(idx, selective, "[1] 高选择性谓词(t3 & price<8)");
    const auto b = run(idx, broad, "[2] 低选择性谓词(t5 & price<95)");

    // 教学注记：距离计算次数只发生在"通过谓词"的条目上，A/B 的距离次数相等；
    // 差异在"谓词检查次数"（A=N、B=|倒排表|）与访存形态（A 顺序、B 跳表随机访问）。
    // 倒排真正的量级收益在 ANN 索引上放大：metadata 先挡掉大部分"不该碰的向量"，
    // 让昂贵的图/量化搜索只发生在小候选集里（见主文档 3.6）。这里 flat 扫描演示的
    // 是确定性事实：倒排把谓词检查从 N 次降到 |tag 表| 次（断言已验）。
    std::cout << "[3] A/B 耗时比: 高选择性=" << s.first / s.second
              << "x, 低选择性=" << b.first / b.second
              << "x —— flat 场景距离次数相等，差距来自谓词检查与访存；"
                 "上 ANN 索引后差距扩大为距离次数之差\n";
    std::cout << "ph23-ex05 OK\n";
    return 0;
}
