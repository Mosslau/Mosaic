// ex03-bloom-filter.cpp —— Bloom Filter：位数组 + 多哈希 + 假阳性率（理论 vs 实测）
// 对应 ph22 主文档 3.4 与 roadmap §22「为 SSTable 增加 Bloom Filter」（此处先做过滤器本体）。
// 教学点：
//   ① 概率语义：无假阴性（说过不在就一定不在）、有可控假阳性——代价是“也许白读一次”；
//   ② 双哈希法：用 h1(key)、h2(key) 两个基哈希线性组合出 k 个位位置
//      （h1 + i*h2 mod m），避免真算 k 个独立哈希；
//   ③ 位数组 m、哈希数 k 与元素数 n 的关系：最优点 k = (m/n)·ln2；
//      理论假阳性率 p = (1 - e^(-k·n/m))^k；
//   ④ “不能删”：清一个位会误伤共享该位的其他 key——LSM 里 bloom 随 SSTable 重建，
//      天然回避（删除靠 compaction 重写文件，见 project/）；
//   ⑤ 怎么“加进点查路径”：先问 bloom“在不在”，不在 → 零数据区 IO（见 3.4 与 sol-03/project）。
// 教学简化（注明）：用固定 key 序列（可复现的伪随机探测）保证每次运行输出一致；
//                  真生产实现用独立哈希族或双哈希 + 随机种子。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -Wall -Wextra ex03-bloom-filter.cpp -o /tmp/ph22-ex03 && /tmp/ph22-ex03
// 验证状态：已验证（零警告、断言全绿、退出码 0）

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

namespace bloom {

// FNV-1a 64 位（salt 区分不同哈希，教学版两个基哈希 = fnv1a(key,1)/fnv1a(key,2)）
std::uint64_t fnv1a(std::string_view s, std::uint64_t salt) {
    std::uint64_t h = 0xcbf29ce484222325ULL ^ (salt * 0x100000001b3ULL);
    for (const unsigned char c : s) {
        h ^= c;
        h *= 0x100000001b3ULL;
    }
    return h;
}

class bloom_filter {
public:
    // m = 位数组总位数；k = 哈希个数
    bloom_filter(std::size_t m, std::size_t k) : m_{m}, k_{k}, bits_(num_bytes(m)) {
        if (m == 0) {
            throw std::invalid_argument("m must be > 0");
        }
    }

    void add(std::string_view key) {
        const auto [h1, h2] = bases(key);
        for (std::size_t i = 0; i < k_; ++i) {
            set_bit((h1 + static_cast<std::uint64_t>(i) * h2) % m_);
        }
    }

    // 返回“可能在”；返回 false = 一定不在（无假阴性的来源）
    bool maybe_contains(std::string_view key) const {
        const auto [h1, h2] = bases(key);
        for (std::size_t i = 0; i < k_; ++i) {
            if (!test_bit((h1 + static_cast<std::uint64_t>(i) * h2) % m_)) {
                return false;
            }
        }
        return true;
    }

    std::size_t num_bits() const { return m_; }
    std::size_t num_hashes() const { return k_; }

private:
    std::size_t m_;
    std::size_t k_;
    std::vector<std::uint8_t> bits_;

    static std::size_t num_bytes(std::size_t m) {
        return (m + 7) / 8;
    }

    std::pair<std::uint64_t, std::uint64_t> bases(std::string_view key) const {
        return {fnv1a(key, 1), fnv1a(key, 2)};
    }

    void set_bit(std::uint64_t bit) {
        bits_[static_cast<std::size_t>(bit / 8)] |=
            static_cast<std::uint8_t>(1u << (bit % 8));
    }

    bool test_bit(std::uint64_t bit) const {
        return (bits_[static_cast<std::size_t>(bit / 8)] &
                static_cast<std::uint8_t>(1u << (bit % 8))) != 0;
    }
};

// 理论假阳性率：p = (1 - e^(-k*n/m))^k
double theory_fpr(std::size_t n, std::size_t m, std::size_t k) {
    const double exponent = -static_cast<double>(k) * static_cast<double>(n) /
                            static_cast<double>(m);
    const double p = std::pow(1.0 - std::exp(exponent), static_cast<double>(k));
    return p;
}

// 教学版素性检查 + 取下一个素数。
// 为什么位数组大小要取素数：双哈希位序列 (h1 + i*h2) mod m 要求 h2 与 m 互质才
// 保证 i 个位置不产生周期/聚集；m 为偶数时 h2 偶数则所有位置同奇偶，假阳性率翻倍。
// （工程上另两条路：m 取 2 的幂 + 位掩码并要求 h2 为奇数；或 prime m 直接用模。）
bool is_prime(std::size_t v) {
    if (v < 2) {
        return false;
    }
    for (std::size_t d = 2; d * d <= v; ++d) {
        if (v % d == 0) {
            return false;
        }
    }
    return true;
}

std::size_t next_prime(std::size_t v) {
    while (!is_prime(v)) {
        ++v;
    }
    return v;
}

// 确定性 key：用简单 LCG 生成可复现的 key 序列（避免依赖 <random> 状态细节）
std::string make_key(std::uint64_t seed) {
    std::uint64_t s = seed * 6364136223846793005ULL + 1442695040888963407ULL;
    std::string out;
    for (int i = 0; i < 12; ++i) {
        s = s * 6364136223846793005ULL + 1442695040888963407ULL;
        out.push_back(static_cast<char>('a' + (s >> 58)));  // 取高位：低位的 LCG 周期太差
    }
    return out;
}

}  // namespace bloom

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
    constexpr std::size_t k_n = 10000;   // 已插入 key 数
    constexpr std::size_t k_m_per_key = 10;  // 每 key 10 位
    constexpr std::size_t k_probe = 100000;  // 探测（未插入）key 数

    // —— 第一部分：m/n=10, k=7 的基础性质 ——
    {
        const std::size_t m = bloom::next_prime(k_n * k_m_per_key);
        bloom::bloom_filter bf{m, 7};

        // 插入 k_n 个 key
        std::vector<std::string> present;
        present.reserve(k_n);
        for (std::size_t i = 0; i < k_n; ++i) {
            const auto key = bloom::make_key(i + 1);
            present.push_back(key);
            bf.add(key);
        }

        // 无假阴性：所有已插入 key 必须命中
        std::size_t false_neg = 0;
        for (const auto& key : present) {
            if (!bf.maybe_contains(key)) {
                ++false_neg;
            }
        }
        std::cout << "[1] 插入 " << k_n << " 个 key, 位数组 " << m << " 位 (=每 key "
                  << k_m_per_key << " 位向上取素数), k=7\n";
        std::cout << "    已插入 key 回查漏报: " << false_neg << " (期望 0)\n";
        CHECK(false_neg == 0);

        // 探测未插入的 key，统计误判
        std::size_t false_pos = 0;
        for (std::size_t i = 0; i < k_probe; ++i) {
            const auto key = bloom::make_key(1000000 + i);
            if (bf.maybe_contains(key)) {
                ++false_pos;
            }
        }
        const double measured = static_cast<double>(false_pos) / k_probe;
        const double theory = bloom::theory_fpr(k_n, m, 7);
        std::cout << "    探测 " << k_probe << " 个未插入 key: 误判 " << false_pos
                  << " 次 = " << measured * 100.0 << "% (理论 "
                  << theory * 100.0 << "%)\n";
        CHECK(false_pos > 0);                 // 有假阳性
        CHECK(measured < 0.03);               // 且被压得很低
    }

    // —— 第二部分：k 的选择（k=4/7/10 对照理论曲线，验证最优 ≈ (m/n)·ln2 ≈ 6.9）——
    {
        const std::size_t m = bloom::next_prime(k_n * k_m_per_key);
        std::cout << "[2] k 对假阳性率的影响 (n=" << k_n << ", m/n=" << k_m_per_key
                  << "):\n";
        for (const std::size_t k : {std::size_t{4}, std::size_t{7}, std::size_t{10}}) {
            bloom::bloom_filter bf{m, k};
            for (std::size_t i = 0; i < k_n; ++i) {
                bf.add(bloom::make_key(i + 1));
            }
            std::size_t fp = 0;
            for (std::size_t i = 0; i < k_probe; ++i) {
                if (bf.maybe_contains(bloom::make_key(1000000 + i))) {
                    ++fp;
                }
            }
            const double measured = static_cast<double>(fp) / k_probe;
            const double theory = bloom::theory_fpr(k_n, m, k);
            std::cout << "    k=" << k << ": 实测 " << measured * 100.0
                      << "% vs 理论 " << theory * 100.0 << "%\n";
        }
    }

    // —— 第三部分：“加进点查路径”的最小演示：查一个不存在的 key 先被 bloom 拦截 ——
    {
        bloom::bloom_filter bf{bloom::next_prime(k_n * k_m_per_key), 7};
        for (std::size_t i = 0; i < k_n; ++i) {
            bf.add(bloom::make_key(i + 1));
        }
        std::size_t intercepted = 0;   // 被 bloom 判“不在”、可省一次数据区 IO 的查询
        constexpr std::size_t k_queries = 5000;
        for (std::size_t i = 0; i < k_queries; ++i) {
            if (!bf.maybe_contains(bloom::make_key(1000000 + i))) {
                ++intercepted;
            }
        }
        const double ratio = static_cast<double>(intercepted) / k_queries;
        std::cout << "[3] 点查不存在 key " << k_queries << " 次: bloom 拦截 "
                  << intercepted << " 次 = " << ratio * 100.0
                  << "% 的查询无需读数据 (误报的 " << k_queries - intercepted
                  << " 次才会白读)\n";
        CHECK(ratio > 0.95);  // m/n=10 时绝大多数不存在查询被拦截
    }

    std::cout << "checks: " << g_checks << ", failed: " << g_failed << '\n';
    if (g_failed == 0) {
        std::cout << "ph22-ex03 OK\n";
        return 0;
    }
    return 1;
}
