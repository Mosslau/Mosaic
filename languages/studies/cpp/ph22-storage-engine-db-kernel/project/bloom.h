// bloom.h —— Mini LSM KV：Bloom Filter 组件（header-only，可序列化进 SSTable）
// 对应 ph22 主文档 3.4 与 roadmap §22「为 SSTable 增加 Bloom Filter」。
// 设计要点：双哈希（FNV-1a 基哈希线性组合）、位数组大小取素数（m 偶数时双哈希
// 位置奇偶聚集会翻倍假阳性率——examples/ex03 有实测翻车记录）、m 精确落盘
// （reader 用字节数反推 m 会因 ceil 错位，exercises/sol-03 有注释）。
// 删除语义提醒：tombstone 的 key 也必须 add —— bloom 只回答“表里有没有这个 key”，
// 不回答“活着还是已删”；漏加会让删除被 bloom 误拦、旧值“复活”。
#ifndef PH22_PROJECT_BLOOM_H
#define PH22_PROJECT_BLOOM_H

#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace minilsm::bloom {

inline std::uint64_t fnv1a(std::string_view s, std::uint64_t salt) {
    std::uint64_t h = 0xcbf29ce484222325ULL ^ (salt * 0x100000001b3ULL);
    for (const unsigned char c : s) {
        h ^= c;
        h *= 0x100000001b3ULL;
    }
    return h;
}

inline bool is_prime(std::size_t v) {
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

inline std::size_t next_prime(std::size_t v) {
    while (!is_prime(v)) {
        ++v;
    }
    return v;
}

class filter {
public:
    filter() = default;
    filter(std::size_t num_bits, std::size_t k) : m_{num_bits}, k_{k}, bits_((num_bits + 7) / 8) {
        if (m_ == 0) {
            throw std::invalid_argument("bloom m must > 0");
        }
    }

    // 每 key 约 10 位、k=7（最优 ≈ (m/n)·ln2）
    static filter sized_for(std::size_t n, std::size_t k = 7) {
        return filter{next_prime(n * 10 + 1), k};
    }

    void add(std::string_view key) {
        const auto [h1, h2] = bases(key);
        for (std::size_t i = 0; i < k_; ++i) {
            const std::uint64_t bit = (h1 + static_cast<std::uint64_t>(i) * h2) % m_;
            bits_[static_cast<std::size_t>(bit / 8)] |=
                static_cast<std::uint8_t>(1u << (bit % 8));
        }
    }

    bool maybe_contains(std::string_view key) const {
        const auto [h1, h2] = bases(key);
        for (std::size_t i = 0; i < k_; ++i) {
            const std::uint64_t bit = (h1 + static_cast<std::uint64_t>(i) * h2) % m_;
            if ((bits_[static_cast<std::size_t>(bit / 8)] &
                 static_cast<std::uint8_t>(1u << (bit % 8))) == 0) {
                return false;
            }
        }
        return true;
    }

    std::size_t num_bits() const { return m_; }
    std::size_t num_hashes() const { return k_; }

    // —— 序列化：k u8 + m u64（小端）+ bits ——
    std::vector<std::uint8_t> serialize() const {
        std::vector<std::uint8_t> out;
        out.push_back(static_cast<std::uint8_t>(k_));
        const std::uint64_t m = m_;
        for (int j = 0; j < 8; ++j) {
            out.push_back(static_cast<std::uint8_t>((m >> (8 * j)) & 0xFFu));
        }
        out.insert(out.end(), bits_.begin(), bits_.end());
        return out;
    }

    static filter deserialize(const std::uint8_t* bytes, std::size_t len) {
        if (len < 9) {
            throw std::runtime_error("bloom meta too short");
        }
        const std::size_t k = bytes[0];
        std::uint64_t m = 0;
        for (int j = 0; j < 8; ++j) {
            m |= static_cast<std::uint64_t>(bytes[1 + static_cast<std::size_t>(j)])
                 << (8 * j);
        }
        if (m == 0 || len != 9 + (m + 7) / 8) {
            throw std::runtime_error("bloom meta inconsistent");
        }
        filter bf{static_cast<std::size_t>(m), k};
        bf.bits_.assign(bytes + 9, bytes + len);
        return bf;
    }

private:
    std::size_t m_{0};
    std::size_t k_{0};
    std::vector<std::uint8_t> bits_;

    std::pair<std::uint64_t, std::uint64_t> bases(std::string_view key) const {
        return {fnv1a(key, 1), fnv1a(key, 2)};
    }
};

}  // namespace minilsm::bloom

#endif  // PH22_PROJECT_BLOOM_H
