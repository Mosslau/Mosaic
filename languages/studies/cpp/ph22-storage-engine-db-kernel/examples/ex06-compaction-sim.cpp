// ex06-compaction-sim.cpp —— Compaction：归并语义 / tombstone / 放大计量 / 归并节奏对比
// 对应 ph22 主文档 3.5/4.1 与 roadmap §22「Compaction、读放大/写放大/空间放大」。
// 教学点：
//   ① compaction 是 LSM 的“后台整理”：把多个有序 run 归并成更少的 run——
//      顺带做三件事：旧值被新值覆盖（丢掉）、tombstone 真正删除 key、数据更紧凑；
//   ② tombstone 语义：非底层归并（下面还有更老的 run）必须保留删除标记——
//      否则更老 run 里的旧值会“复活”；只有“到底”的 full compaction 才能真删；
//   ③ 三放大：读放大（一次点查要查几个 run / 文件）、写放大（后台 rewrite 是输入的几倍）、
//      空间放大（物理占用 / 有效数据）；
//   ④ 归并节奏的取舍：每次 flush 都全量归并 → 历史被反复重写（写放大高）；
//      攒 N 次再归并 → 重写次数少（写放大低），但没归并前点查要跨更多 run（读放大高）。
//      ——“何时触发 compaction”本身就是调参，是 LSM 的核心运维杠杆。
//   ⑤ 教学简化（注明）：key 域与负载为确定性伪随机；run 之间按“全重叠”建模
//      （真实 leveled 会按 key 区间挑文件，避免重写不相交区间——见主文档 3.5）；
//      数值只对本模型成立，趋势（攒批降写放大）对真实引擎同样成立。
// 资源管理：纯内存模拟（无文件、无裸资源），聚焦归并算法与计量。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -Wall -Wextra ex06-compaction-sim.cpp -o /tmp/ph22-ex06 && /tmp/ph22-ex06
// 验证状态：已验证（零警告、断言全绿、退出码 0）

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <map>
#include <string>
#include <utility>
#include <vector>

namespace csim {

// —— 一条日志/一条 SSTable 记录：带 seq（越大越新）+ deleted（tombstone）——
struct entry {
    std::string key;
    std::string value;
    std::uint64_t seq{0};
    bool deleted{false};
};

// 一个 run（MemTable flush 出的 SSTable 的逻辑等价物）：key 有序、key 唯一
using run = std::vector<entry>;

// 一个 run 的物理字节数（8 字节定长头 + key + value；头在两种 value 下等长，比较不受影响）
std::uint64_t run_bytes(const run& r) {
    std::uint64_t b = 0;
    for (const auto& e : r) {
        b += 8 + e.key.size() + e.value.size();
    }
    return b;
}

struct merge_metrics {
    std::uint64_t input_entries{0};
    std::uint64_t dropped_stale{0};   // 被更新版本的覆盖掉的旧值条
    std::uint64_t dropped_tombstone{0};  // 在 full compaction 中真正删掉的 key
    std::uint64_t output_entries{0};
    std::uint64_t input_bytes{0};
    std::uint64_t output_bytes{0};
};

// 归并并返回结果 run（metrics 通过输出参数回传）：
//   runs 按“新 → 旧”排序；final=true 表示这是到底层的 full compaction——
//   允许把 tombstone 丢掉（下面没有更老的数据了）；
//   final=false 时 tombstone 必须保留，否则旧 run 里的值会复活。
run merge_runs_result(const std::vector<run>& runs, bool final, merge_metrics* m_out) {
    std::map<std::string, entry> best;
    merge_metrics m;
    for (const auto& r : runs) {
        for (const auto& e : r) {
            m.input_entries += 1;
            m.input_bytes += 8 + e.key.size() + e.value.size();
            const auto it = best.find(e.key);
            if (it == best.end() || e.seq > it->second.seq) {
                if (it != best.end()) {
                    ++m.dropped_stale;  // 旧版本（无论是否 tombstone）被压掉一条
                }
                best[e.key] = e;
            } else {
                ++m.dropped_stale;
            }
        }
    }
    run out;
    out.reserve(best.size());
    for (auto& [k, e] : best) {
        if (e.deleted && final) {
            ++m.dropped_tombstone;
            continue;
        }
        out.push_back(std::move(e));
    }
    m.output_entries = out.size();
    m.output_bytes = run_bytes(out);
    if (m_out) {
        *m_out = m;
    }
    return out;
}

// —— 一次点查要探测几个 run：返回第一个给出答案的 run 下标（含“无答案”需探测全部）——
struct probe_result {
    bool found{false};
    bool deleted{false};
    std::string value;
    std::size_t runs_probed{0};  // 读放大代理：探测了几个 run
};

probe_result point_lookup(const std::vector<run>& runs, const std::string& key) {
    for (std::size_t i = 0; i < runs.size(); ++i) {
        const auto& r = runs[i];
        // 教学简化：二分定位（run 内有序）
        const auto it = std::lower_bound(r.begin(), r.end(), key,
                                         [](const entry& e, const std::string& k) {
                                             return e.key < k;
                                         });
        if (it != r.end() && it->key == key) {
            return probe_result{!it->deleted, it->deleted, it->value, i + 1};
        }
    }
    return probe_result{false, false, "", runs.size()};  // 全探测完也没找到
}

// —— 由操作序列构造一个 run（同一次 MemTable 快照：同 key 只留最新一条）——
std::uint64_t g_seq = 0;

run build_run_from_ops(const std::vector<std::pair<std::string, bool>>& ops,
                       std::string value_prefix) {
    std::map<std::string, entry> best;
    for (const auto& [key, deleted] : ops) {
        entry e;
        e.key = key;
        e.value = deleted ? "" : (value_prefix + key);
        e.seq = ++g_seq;
        e.deleted = deleted;
        best[key] = std::move(e);  // 同一 run 内后写覆盖先写
    }
    run out;
    out.reserve(best.size());
    for (auto& [k, e] : best) {
        out.push_back(std::move(e));
    }
    return out;
}

// —— 确定性负载：key 域固定，重复覆盖 + 部分删除 ——
std::string pad(std::size_t v, int width) {
    std::string s = std::to_string(v);
    while (static_cast<int>(s.size()) < width) {
        s = "0" + s;
    }
    return s;
}

std::vector<std::pair<std::string, bool>> make_ops(std::size_t seed, std::size_t n,
                                                   std::size_t key_domain) {
    std::vector<std::pair<std::string, bool>> ops;
    std::uint64_t s = 88172645463325252ULL + seed * 3935559000370003845ULL;
    for (std::size_t i = 0; i < n; ++i) {
        s = s * 6364136223846793005ULL + 1442695040888963407ULL;
        const auto kid = static_cast<std::size_t>((s >> 40) % key_domain);
        const bool del = (kid % 7 == 0);  // ~1/7 是删除
        ops.emplace_back("key-" + pad(kid, 3), del);
    }
    return ops;
}

}  // namespace csim

// —— 测试框架 ——
static int g_failed = 0;
static int g_checks = 0;

#define CHECK(cond)                                                        \
    do {                                                                   \
        ++g_checks;                                                        \
        if (!(cond)) {                                                     \
            std::cerr << "FAIL: " << #cond << " (line " << __LINE__ << ")\n"; \
            ++g_failed;                                                    \
        }                                                                  \
    } while (0)

int main() {
    using namespace csim;
    // —— [1] 归并语义：三个 run（新→旧），含跨 run 覆盖与删除 ——
    {
        run r0;  // 最旧
        r0.push_back({"apple", "r0", 1, false});
        r0.push_back({"banana", "r0", 2, false});
        run r1;
        r1.push_back({"banana", "r1", 11, false});   // 覆盖 r0 的 banana
        r1.push_back({"cherry", "r1", 12, false});
        run r2;  // 最新
        r2.push_back({"apple", "r2", 21, false});    // 覆盖 r0 的 apple
        r2.push_back({"banana", "", 22, true});      // 删除 banana → 压掉 r1/r0
        std::vector<run> runs{r2, r1, r0};

        // 点查前：不存在的 key 要探测全部 3 个 run（读放大 = 3）
        const auto miss = point_lookup(runs, "zzz");
        CHECK(!miss.found && miss.runs_probed == 3);

        // full compaction（final=true）：banana 被删除，apple 取 r2，cherry 保留
        merge_metrics m;
        run merged = merge_runs_result(runs, /*final=*/true, &m);
        std::cout << "[1] full compaction 3 个 run (共 " << m.input_entries
                  << " 条, " << m.input_bytes << " B) -> " << m.output_entries
                  << " 条, " << m.output_bytes << " B\n";
        std::cout << "    覆盖丢弃 " << m.dropped_stale << " 条, tombstone 真删 "
                  << m.dropped_tombstone << " 个 key\n";
        CHECK(merged.size() == 2);
        CHECK(merged[0].key == "apple" && merged[0].value == "r2");
        CHECK(merged[1].key == "cherry" && merged[1].value == "r1");

        // 合并后点查同样的不存在 key：只需探测 1 个 run
        const auto miss2 = point_lookup({merged}, "zzz");
        CHECK(!miss2.found && miss2.runs_probed == 1);
        std::cout << "    点查不存在 key: 3 run 时探测 " << miss.runs_probed
                  << " 次 -> 合并后探测 " << miss2.runs_probed
                  << " 次 (读放大 3 -> 1)\n";

        // 空间放大 = 物理占用 / 有效数据
        const auto space_before = m.input_bytes;
        const auto live_bytes = run_bytes(merged);
        std::cout << "    空间: 物理 " << space_before << " B / 有效 " << live_bytes
                  << " B (空间放大 " << (space_before / static_cast<double>(live_bytes)) << "x)\n";
        CHECK(space_before > live_bytes);
    }

    // —— [2] tombstone 语义：非底层归并必须保留删除标记 ——
    {
        run older;
        older.push_back({"fig", "v", 1, false});
        run newer;
        newer.push_back({"fig", "", 9, true});  // 删除 fig，但下面还有 older
        const std::vector<run> runs{newer, older};
        merge_metrics m;
        const run partial = merge_runs_result(runs, /*final=*/false, &m);
        std::cout << "[2] 非底层归并: tombstone 保留? "
                  << (partial.size() == 1 && partial[0].deleted ? "是" : "否")
                  << " (若丢掉, 更老的 fig=v 会复活)\n";
        CHECK(partial.size() == 1 && partial[0].deleted);
        const run full = merge_runs_result(runs, /*final=*/true, &m);
        CHECK(full.empty());  // 到底层时 tombstone 落地，key 真正消失
    }

    // —— [3] 归并节奏 vs 写放大：每次 flush 都归并 vs 攒 4 次再归并 ——
    {
        constexpr std::size_t k_flushes = 12;
        constexpr std::size_t k_domain = 60;  // key 域小 → 大量覆盖，历史数据反复重写

        std::vector<run> history;              // 方案 A 的“已归并历史”
        std::vector<run> pending;              // 方案 B 的待归并 run
        std::uint64_t aggressive_write = 0;    // 方案 A：每次 flush 后全量归并
        std::uint64_t batched_write = 0;       // 方案 B：攒 4 个 run 归并一次

        g_seq = 0;
        for (std::size_t i = 0; i < k_flushes; ++i) {
            const auto ops = make_ops(i, 40, k_domain);
            run fresh = build_run_from_ops(ops, "v");
            // 方案 A：history 每次都被全量重写（当前全部 run 归并）
            if (!history.empty()) {
                std::vector<run> all = history;
                all.push_back(fresh);
                merge_metrics m;
                history = {merge_runs_result(all, false, &m)};
                aggressive_write += m.output_bytes;
            } else {
                history.push_back(fresh);
            }
            // 方案 B：攒到 4 个才归并
            pending.push_back(fresh);
            if (pending.size() >= 4) {
                merge_metrics m;
                pending = {merge_runs_result(pending, false, &m)};
                batched_write += m.output_bytes;
            }
        }
        std::cout << "[3] " << k_flushes << " 次 flush 的归并写字节:\n";
        std::cout << "    每次 flush 都归并: " << aggressive_write << " B\n";
        std::cout << "    攒 4 次归并一次:   " << batched_write << " B\n";
        std::cout << "    结论: 攒批少重写旧历史 -> 写放大更低 (本例 "
                  << (batched_write < aggressive_write ? "batched 更低" : "相同")
                  << ")\n";
        CHECK(aggressive_write > batched_write);
        CHECK(history.size() == 1);              // 方案 A 始终维持单 run
        CHECK(pending.size() >= 1 && pending.size() < 4);  // 方案 B 攒批未完，读放大还在累积
    }

    std::cout << "checks: " << g_checks << ", failed: " << g_failed << '\n';
    if (g_failed == 0) {
        std::cout << "ph22-ex06 OK\n";
        return 0;
    }
    return 1;
}
