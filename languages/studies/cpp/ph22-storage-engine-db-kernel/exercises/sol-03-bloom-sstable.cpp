// sol-03-bloom-sstable.cpp —— exercises/练习 3 参考实现：为 SSTable 增加 Bloom Filter
// 题目见 exercises/README.md。做法：writer 在建表时把全部 key 编进位数组，
// reader 点查先问 bloom：“不在” → 零数据区解码直接拒绝（读放大下降）；
// “可能在” → 走正常数据区解码。本实现把“会不会白读数据”变成可计数的指标。
// 文件布局（教学简化，突出 bloom 与数据区的关系）：
//   [数据区] entry*：升序 [klen u32][vlen u32][key][value]
//   [bloom]  [k u8][bytes_cnt u32][位数组字节]
//   [footer] 定长：data_len u64 | bloom_off u64 | bloom_bytes u32 | magic u32
// 注意（tombstone 语义）：删除记录仍然要进 bloom —— bloom 只回答“这个 key 在不在表里”，
// 不回答“活着还是 tombstone”，所以 DEL 记录也必须 add（否则会被 bloom 误拦，旧值复活）。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -Wall -Wextra sol-03-bloom-sstable.cpp -o /tmp/ph22-sol03 && /tmp/ph22-sol03
// 验证状态：已验证（零警告、断言全绿、退出码 0）

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace bss {

constexpr std::uint32_t k_magic = 0x53424C4Du;  // "SBLM"
constexpr std::size_t k_footer = 24;            // data_len8 + bloom_off8 + bloom_bytes4 + magic4
constexpr std::size_t k_max_kv = 64u * 1024u;

struct kv {
    std::string key;
    std::string value;  // 空 value 即 tombstone（练习提示：DEL 也要进 bloom）
};

// —— FNV-1a + 位数组 Bloom（与 examples/ex03 同款思想，布局独立）——
std::uint64_t fnv1a(std::string_view s, std::uint64_t salt) {
    std::uint64_t h = 0xcbf29ce484222325ULL ^ (salt * 0x100000001b3ULL);
    for (const unsigned char c : s) {
        h ^= c;
        h *= 0x100000001b3ULL;
    }
    return h;
}

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

class bloom {
public:
    bloom(std::size_t num_bits, std::size_t k) : m_{num_bits}, k_{k}, bits_((num_bits + 7) / 8) {}

    static bloom sized_for(std::size_t n, std::size_t k = 7) {
        return bloom{next_prime(n * 10), k};  // 每 key 10 位（向上取素数）
    }

    void add(std::string_view key) {
        const auto [h1, h2] = bases(key);
        for (std::size_t i = 0; i < k_; ++i) {
            const std::uint64_t bit = (h1 + static_cast<std::uint64_t>(i) * h2) % m_;
            bits_[static_cast<std::size_t>(bit / 8)] |=
                static_cast<std::uint8_t>(1u << (bit % 8));
        }
    }

    bool maybe(std::string_view key) const {
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

    std::pair<std::uint64_t, std::uint64_t> bases(std::string_view key) const {
        return {fnv1a(key, 1), fnv1a(key, 2)};
    }

    std::size_t num_bits() const { return m_; }
    std::size_t num_hashes() const { return k_; }

    std::vector<std::uint8_t> bytes() const { return bits_; }
    void set_bytes(std::vector<std::uint8_t> b) { bits_ = std::move(b); }

private:
    std::size_t m_;
    std::size_t k_;
    std::vector<std::uint8_t> bits_;
};

// —— writer：entries（升序；key 可重复？不允许）→ 数据区 + bloom + footer ——
std::uint64_t write_sstable(const std::string& path, const std::vector<kv>& entries) {
    bloom bf = bloom::sized_for(entries.empty() ? 1 : entries.size());
    std::vector<std::uint8_t> data;
    for (const auto& e : entries) {
        if (e.key.size() + e.value.size() > k_max_kv) {
            throw std::runtime_error("entry too large");
        }
        bf.add(e.key);  // ★ tombstone（空 value）也进 bloom
        const std::uint32_t klen = static_cast<std::uint32_t>(e.key.size());
        const std::uint32_t vlen = static_cast<std::uint32_t>(e.value.size());
        const std::uint8_t len[8] = {
            static_cast<std::uint8_t>((klen >> 24) & 0xFFu),
            static_cast<std::uint8_t>((klen >> 16) & 0xFFu),
            static_cast<std::uint8_t>((klen >> 8) & 0xFFu),
            static_cast<std::uint8_t>(klen & 0xFFu),
            static_cast<std::uint8_t>((vlen >> 24) & 0xFFu),
            static_cast<std::uint8_t>((vlen >> 16) & 0xFFu),
            static_cast<std::uint8_t>((vlen >> 8) & 0xFFu),
            static_cast<std::uint8_t>(vlen & 0xFFu),
        };
        data.insert(data.end(), len, len + 8);
        data.insert(data.end(), e.key.begin(), e.key.end());
        data.insert(data.end(), e.value.begin(), e.value.end());
    }

    std::vector<std::uint8_t> bloom_bytes = bf.bytes();
    // meta = [k u8][m u64 小端][位数组字节] —— m 必须精确落盘：
    // 位数组字节数 = ceil(m/8)，reader 若反推 m 会得到 ≥ 原值，导致 % m 错位。
    std::vector<std::uint8_t> meta;
    meta.push_back(static_cast<std::uint8_t>(bf.num_hashes()));
    const std::uint64_t mbits = bf.num_bits();
    for (int i = 0; i < 8; ++i) {
        meta.push_back(static_cast<std::uint8_t>((mbits >> (8 * i)) & 0xFFu));  // 小端（教学约定）
    }
    meta.insert(meta.end(), bloom_bytes.begin(), bloom_bytes.end());

    const std::uint64_t data_len = data.size();
    const std::uint64_t bloom_off = data.size();
    std::vector<std::uint8_t> file;
    file.reserve(data.size() + meta.size() + k_footer);
    file.insert(file.end(), data.begin(), data.end());
    file.insert(file.end(), meta.begin(), meta.end());
    std::uint8_t ft[k_footer];
    auto put64 = [&](std::size_t at, std::uint64_t v) {
        for (int i = 0; i < 8; ++i) {
            ft[at + static_cast<std::size_t>(i)] =
                static_cast<std::uint8_t>((v >> (56 - 8 * i)) & 0xFFu);
        }
    };
    auto put32 = [&](std::size_t at, std::uint32_t v) {
        for (int i = 0; i < 4; ++i) {
            ft[at + static_cast<std::size_t>(i)] =
                static_cast<std::uint8_t>((v >> (24 - 8 * i)) & 0xFFu);
        }
    };
    put64(0, data_len);
    put64(8, bloom_off);
    put32(16, static_cast<std::uint32_t>(meta.size()));
    put32(20, k_magic);
    file.insert(file.end(), ft, ft + k_footer);

    const int fd = ::open(path.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) {
        throw std::runtime_error("open(write) failed");
    }
    std::size_t done = 0;
    while (done < file.size()) {
        const ssize_t w = ::write(fd, file.data() + done, file.size() - done);
        if (w < 0) {
            if (errno == EINTR) {
                continue;
            }
            ::close(fd);
            throw std::runtime_error("write failed");
        }
        done += static_cast<std::size_t>(w);
    }
    ::close(fd);
    return static_cast<std::uint64_t>(file.size());
}

// —— reader：bloom 先拦，拦不住才解码数据区 ——
class sstable_reader {
public:
    explicit sstable_reader(const std::string& path) {
        const int fd = ::open(path.c_str(), O_RDONLY);
        if (fd < 0) {
            throw std::runtime_error("open(read) failed");
        }
        std::vector<std::uint8_t> all;
        std::array<std::uint8_t, 4096> buf{};
        ssize_t n = 0;
        while ((n = ::read(fd, buf.data(), buf.size())) > 0) {
            all.insert(all.end(), buf.begin(), buf.begin() + n);
        }
        ::close(fd);
        if (n < 0) {
            throw std::runtime_error("read failed");
        }
        if (all.size() < k_footer) {
            throw std::runtime_error("too small");
        }
        auto get64 = [&](std::size_t at) {
            std::uint64_t v = 0;
            for (int i = 0; i < 8; ++i) {
                v = (v << 8) | all[at + static_cast<std::size_t>(i)];
            }
            return v;
        };
        auto get32 = [&](std::size_t at) {
            std::uint32_t v = 0;
            for (int i = 0; i < 4; ++i) {
                v = (v << 8) | all[at + static_cast<std::size_t>(i)];
            }
            return v;
        };
        const std::size_t foot = all.size() - k_footer;
        if (get32(foot + 20) != k_magic) {
            throw std::runtime_error("magic mismatch");
        }
        const std::uint64_t data_len = get64(foot);
        const std::uint64_t bloom_off = get64(foot + 8);
        const std::uint32_t meta_size = get32(foot + 16);
        // meta = [k u8][m u64 小端][bits]
        const std::size_t base = static_cast<std::size_t>(bloom_off);
        if (static_cast<std::uint64_t>(bloom_off) + meta_size + k_footer != all.size()) {
            throw std::runtime_error("meta/footer layout inconsistent");
        }
        const std::size_t kk = all[base];
        std::uint64_t mbits = 0;
        for (int j = 0; j < 8; ++j) {  // 小端解码：byte j 在第 8j 位
            mbits |= static_cast<std::uint64_t>(all[base + 1 + static_cast<std::size_t>(j)])
                     << (8 * j);
        }
        if (mbits == 0) {
            throw std::runtime_error("bad bloom meta");
        }
        const std::size_t nbytes = meta_size - 9;
        bf_ = bloom{static_cast<std::size_t>(mbits), kk};
        std::vector<std::uint8_t> bits;
        bits.assign(all.begin() + static_cast<std::ptrdiff_t>(base + 9),
                    all.begin() + static_cast<std::ptrdiff_t>(base + 9 + nbytes));
        bf_.set_bytes(std::move(bits));
        entries_bytes_ = {all.begin(), all.begin() + static_cast<std::ptrdiff_t>(data_len)};
    }

    struct query_result {
        bool found;
        std::string value;
        bool bloom_allowed;   // true = bloom 放行（进入数据区）
        std::size_t entries_decoded;  // 实际解码了几条 entry（数据区 IO 代理）
    };

    // 非 const：内部累加统计
    query_result get(const std::string& key) {
        query_result r{false, "", true, 0};
        if (!bf_.maybe(key)) {
            ++bloom_negatives_;
            r.bloom_allowed = false;
            return r;  // ★ bloom 说不在：零数据区 IO
        }
        ++bloom_positives_;
        std::size_t p = 0;
        while (p + 8 <= entries_bytes_.size()) {
            const std::uint32_t klen = (static_cast<std::uint32_t>(entries_bytes_[p]) << 24) |
                                       (static_cast<std::uint32_t>(entries_bytes_[p + 1]) << 16) |
                                       (static_cast<std::uint32_t>(entries_bytes_[p + 2]) << 8) |
                                       static_cast<std::uint32_t>(entries_bytes_[p + 3]);
            const std::uint32_t vlen = (static_cast<std::uint32_t>(entries_bytes_[p + 4]) << 24) |
                                       (static_cast<std::uint32_t>(entries_bytes_[p + 5]) << 16) |
                                       (static_cast<std::uint32_t>(entries_bytes_[p + 6]) << 8) |
                                       static_cast<std::uint32_t>(entries_bytes_[p + 7]);
            p += 8;
            if (p + klen + vlen > entries_bytes_.size()) {
                throw std::runtime_error("corrupt data area");
            }
            ++r.entries_decoded;
            const std::string k(reinterpret_cast<const char*>(entries_bytes_.data() + p), klen);
            if (k == key) {
                r.found = true;
                r.value.assign(reinterpret_cast<const char*>(entries_bytes_.data() + p + klen), vlen);
                return r;
            }
            if (k > key) {
                break;  // 升序：越过即 miss
            }
            p += klen + vlen;
        }
        ++bloom_false_positives_;  // bloom 放行却查无此 key = 一次假阳性白读
        return r;
    }

    std::size_t bloom_negatives() const { return bloom_negatives_; }
    std::size_t bloom_positives() const { return bloom_positives_; }
    std::size_t bloom_false_positives() const { return bloom_false_positives_; }

private:
    bloom bf_{1, 1};
    std::vector<std::uint8_t> entries_bytes_;
    std::size_t bloom_negatives_{0};
    std::size_t bloom_positives_{0};
    std::size_t bloom_false_positives_{0};
};

}  // namespace bss

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

// 确定性 key 生成（与 examples/ex03 同款，保证可复现）
std::string make_key(std::uint64_t seed) {
    std::uint64_t s = seed * 6364136223846793005ULL + 1442695040888963407ULL;
    std::string out;
    for (int i = 0; i < 10; ++i) {
        s = s * 6364136223846793005ULL + 1442695040888963407ULL;
        out.push_back(static_cast<char>('a' + (s >> 58)));
    }
    return out;
}

int main() {
    const std::string path = "/tmp/ph22-sol03.sst";
    ::unlink(path.c_str());

    // 1000 个真 key + 若干 tombstone（空 value），模拟一次真实的 SSTable flush
    std::vector<bss::kv> entries;
    for (std::size_t i = 0; i < 1000; ++i) {
        const auto k = make_key(i + 1);
        entries.push_back({k, i % 11 == 0 ? "" : ("v" + std::to_string(i))});  // ~9% tombstone
    }
    std::sort(entries.begin(), entries.end(),
              [](const bss::kv& a, const bss::kv& b) { return a.key < b.key; });

    const std::uint64_t sz = bss::write_sstable(path, entries);
    std::cout << "[1] 写出 " << sz << " 字节 (" << entries.size() << " 条, 含 "
              << std::count_if(entries.begin(), entries.end(),
                               [](const bss::kv& e) { return e.value.empty(); })
              << " 条 tombstone)\n";

    bss::sstable_reader r{path};

    // 真 key：必须全部命中且零假阴性
    std::size_t data_reads_present = 0;
    for (const auto& e : entries) {
        const auto q = r.get(e.key);
        CHECK(q.found);
        if (e.value.empty()) {
            CHECK(q.value.empty());  // tombstone 查回也是“在表里但值为空”
        } else {
            CHECK(q.value == e.value);
        }
        data_reads_present += q.entries_decoded;
    }
    std::cout << "[2] " << entries.size() << " 个真 key 点查: 假阴性 0, "
              << "共解码 " << data_reads_present << " 条 entry\n";
    CHECK(r.bloom_false_positives() == 0);  // 无假阴性 → 真 key 从不被拦

    // 不存在的 key：绝大多数被 bloom 拦下（零解码），少数假阳性白读
    bss::sstable_reader r2{path};
    std::size_t intercepted = 0;
    std::size_t decoded = 0;
    constexpr std::size_t k_probe = 20000;
    for (std::size_t i = 0; i < k_probe; ++i) {
        const auto q = r2.get(make_key(1'000'000 + i));
        CHECK(!q.found);
        if (!q.bloom_allowed) {
            ++intercepted;
        }
        decoded += q.entries_decoded;
    }
    std::cout << "[3] 探测 " << k_probe << " 个不存在 key: bloom 拦截 " << intercepted
              << " 次 (" << intercepted * 100.0 / k_probe << "%), 假阳性白读 "
              << r2.bloom_false_positives() << " 次, 白读平均解码 "
              << decoded / (r2.bloom_false_positives() == 0 ? 1 : r2.bloom_false_positives())
              << " 条/次 (线性格式平均扫半文件)\n";
    CHECK(r2.bloom_negatives() > 0);              // 确实有拦截发生
    CHECK(intercepted > k_probe * 95 / 100);      // 拦截率 > 95%
    CHECK(r2.bloom_false_positives() > 0);        // 也有假阳性（概率结构）
    CHECK(decoded > 0);                           // 假阳性确实付出了数据区 IO

    ::unlink(path.c_str());
    std::cout << "checks: " << g_checks << ", failed: " << g_failed << '\n';
    if (g_failed == 0) {
        std::cout << "ph22-sol-03 OK\n";
        return 0;
    }
    return 1;
}
