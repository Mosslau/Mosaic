// sstable.h —— Mini LSM KV：SSTable 组件（header-only writer/reader）
// 对应 ph22 主文档 3.3/3.4。不可变有序文件，一次 flush 写出、之后只读。
// 文件布局（教学简化版，多字节统一大端）：
//   [数据区] block*（每块 k_block_cap 条，key 升序）
//            entry = [type u8(1=put/2=del)][klen u32][vlen u32][key][value]
//   [索引区] 每数据块 1 条：块首 key + 块偏移（稀疏索引，open 载入内存二分）
//   [bloom]  filter.serialize()：k u8 + m u64(LE) + 位数组字节
//   [footer] 定长 32 字节：index_off u64 | index_size u32 | bloom_off u64 |
//            bloom_len u32 | magic u32
// 点查路径：footer → 载入 bloom 与索引 → bloom “不在”零数据区 IO →
//           索引二分 → 块内顺扫 ≤ k_block_cap 条。
// 注意：tombstone（type=del）也会写进 bloom —— 否则删除会被误拦而旧值复活。
// 资源管理：RAII fd + vector 拥有文件字节（R.1/R.11）。
#ifndef PH22_PROJECT_SSTABLE_H
#define PH22_PROJECT_SSTABLE_H

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

#include "bloom.h"

namespace minilsm::sst {

constexpr std::uint32_t k_magic = 0x53535432u;  // "SST2"
constexpr std::size_t k_footer = 28;
constexpr std::size_t k_block_cap = 8;          // 每块最多 8 条
constexpr std::uint32_t k_max_kv = 64u * 1024u;

struct rec {
    std::string key;
    std::string value;
    bool deleted{false};
};

// —— writer ——
// records 必须按 key 升序且无重复（MemTable flush 天然满足）。
inline void write_sstable(const std::string& path, const std::vector<rec>& records) {
    minilsm::bloom::filter bf =
        minilsm::bloom::filter::sized_for(records.empty() ? 1 : records.size());
    std::vector<std::uint8_t> data;   // 数据区
    std::vector<std::uint8_t> index;  // 索引区

    auto put_u32 = [](std::vector<std::uint8_t>& out, std::uint32_t v) {
        const std::uint8_t b[4] = {
            static_cast<std::uint8_t>((v >> 24) & 0xFFu),
            static_cast<std::uint8_t>((v >> 16) & 0xFFu),
            static_cast<std::uint8_t>((v >> 8) & 0xFFu),
            static_cast<std::uint8_t>(v & 0xFFu),
        };
        out.insert(out.end(), b, b + 4);
    };
    auto put_u64 = [&](std::vector<std::uint8_t>& out, std::uint64_t v) {
        put_u32(out, static_cast<std::uint32_t>(v >> 32));
        put_u32(out, static_cast<std::uint32_t>(v & 0xFFFFFFFFu));
    };
    auto append_str = [](std::vector<std::uint8_t>& out, std::string_view s) {
        out.insert(out.end(), s.begin(), s.end());
    };

    std::size_t block_cnt = 0;
    std::size_t in_block = 0;
    std::string first_key;
    std::uint64_t block_start = 0;

    auto close_block = [&]() {
        if (in_block == 0) {
            return;
        }
        put_u32(index, static_cast<std::uint32_t>(first_key.size()));
        append_str(index, first_key);
        put_u64(index, block_start);
        ++block_cnt;
        in_block = 0;
    };

    for (const auto& r : records) {
        if (r.key.size() + r.value.size() > k_max_kv) {
            throw std::runtime_error("record too large");
        }
        bf.add(r.key);  // tombstone 也进 bloom（语义见文件头注释）
        if (in_block == 0) {
            first_key = r.key;
            block_start = data.size();  // 块起点（封块前记录）
        }
        data.push_back(r.deleted ? static_cast<std::uint8_t>(2) : static_cast<std::uint8_t>(1));
        put_u32(data, static_cast<std::uint32_t>(r.key.size()));
        put_u32(data, static_cast<std::uint32_t>(r.value.size()));
        append_str(data, r.key);
        append_str(data, r.value);
        ++in_block;
        if (in_block == k_block_cap) {
            close_block();
        }
    }
    close_block();

    // bloom 区
    std::vector<std::uint8_t> bloom_bytes = bf.serialize();
    // footer
    std::vector<std::uint8_t> footer;
    put_u64(footer, static_cast<std::uint64_t>(data.size()));   // index_off
    put_u32(footer, static_cast<std::uint32_t>(index.size()));  // index_size
    put_u64(footer, static_cast<std::uint64_t>(data.size() + index.size()));  // bloom_off
    put_u32(footer, static_cast<std::uint32_t>(bloom_bytes.size()));          // bloom_len
    put_u32(footer, k_magic);
    if (footer.size() != k_footer) {
        throw std::runtime_error("footer size bug");
    }

    std::vector<std::uint8_t> file;
    file.reserve(data.size() + index.size() + bloom_bytes.size() + footer.size());
    file.insert(file.end(), data.begin(), data.end());
    file.insert(file.end(), index.begin(), index.end());
    file.insert(file.end(), bloom_bytes.begin(), bloom_bytes.end());
    file.insert(file.end(), footer.begin(), footer.end());

    const int fd = ::open(path.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) {
        throw std::runtime_error("sstable open(write) failed: " + path);
    }
    std::size_t done = 0;
    while (done < file.size()) {
        const ssize_t w = ::write(fd, file.data() + done, file.size() - done);
        if (w < 0) {
            if (errno == EINTR) {
                continue;
            }
            ::close(fd);
            throw std::runtime_error("sstable write failed");
        }
        done += static_cast<std::size_t>(w);
    }
    if (::fsync(fd) != 0) {
        ::close(fd);
        throw std::runtime_error("fsync failed");
    }
    ::close(fd);
}

// —— reader ——
class reader {
public:
    enum class find_state { none, deleted, value };

    struct find_result {
        find_state state{find_state::none};
        std::string value;
    };

    reader() = default;

    // 打开文件：载入 footer / 索引 / bloom
    void open(const std::string& path) {
        const int fd = ::open(path.c_str(), O_RDONLY);
        if (fd < 0) {
            throw std::runtime_error("sstable open(read) failed: " + path);
        }
        bytes_.clear();
        std::array<std::uint8_t, 8192> chunk{};
        ssize_t n = 0;
        while ((n = ::read(fd, chunk.data(), chunk.size())) > 0) {
            bytes_.insert(bytes_.end(), chunk.begin(), chunk.begin() + n);
        }
        ::close(fd);
        if (n < 0) {
            throw std::runtime_error("sstable read failed");
        }
        if (bytes_.size() < k_footer) {
            throw std::runtime_error("sstable too small");
        }
        const std::size_t foot = bytes_.size() - k_footer;
        index_off_ = get_u64(foot);
        const std::uint32_t index_size = get_u32(foot + 8);
        const std::uint64_t bloom_off = get_u64(foot + 12);
        const std::uint32_t bloom_len = get_u32(foot + 20);
        if (get_u32(foot + 24) != k_magic) {
            throw std::runtime_error("sstable magic mismatch");
        }
        if (static_cast<std::uint64_t>(bloom_off) + bloom_len + k_footer != bytes_.size()) {
            throw std::runtime_error("sstable layout inconsistent");
        }
        data_end_ = index_off_;
        // 解析索引
        index_.clear();
        std::size_t p = static_cast<std::size_t>(index_off_);
        const std::size_t iend = p + index_size;
        while (p + 12 <= iend) {
            const std::uint32_t klen = get_u32(p);
            p += 4;
            if (p + klen + 8 > iend) {
                throw std::runtime_error("bad sstable index");
            }
            index_item item;
            item.first_key.assign(reinterpret_cast<const char*>(bytes_.data() + p), klen);
            p += klen;
            item.offset = get_u64(p);
            p += 8;
            if (item.offset > data_end_) {
                throw std::runtime_error("index offset out of data area");
            }
            index_.push_back(std::move(item));
        }
        if (p != iend) {
            throw std::runtime_error("index area not fully consumed");
        }
        bloom_ = minilsm::bloom::filter::deserialize(
            bytes_.data() + static_cast<std::ptrdiff_t>(bloom_off), bloom_len);
    }

    bool opened() const { return !bytes_.empty(); }
    std::size_t block_count() const { return index_.size(); }
    std::size_t bloom_negatives() const { return bloom_negatives_; }
    std::size_t bloom_false_positives() const { return bloom_false_positives_; }

    // 点查（bloom → 索引二分 → 块内顺扫）。结果三态：none/deleted/value。
    find_result find(const std::string& key) {
        if (!bloom_.maybe_contains(key)) {
            ++bloom_negatives_;  // ★ 零数据区 IO
            return {};
        }
        // 索引二分：最后一个 first_key <= key
        std::size_t lo = 0;
        std::size_t hi = index_.size();
        while (lo < hi) {
            const std::size_t mid = lo + (hi - lo) / 2;
            if (index_[mid].first_key <= key) {
                lo = mid + 1;
            } else {
                hi = mid;
            }
        }
        find_result out;
        bool saw_any = false;
        if (lo > 0) {
            std::size_t p = static_cast<std::size_t>(index_[lo - 1].offset);
            for (std::size_t i = 0; i < k_block_cap && p < data_end_; ++i) {
                if (p + 9 > data_end_) {
                    break;  // 损坏防护
                }
                const std::uint8_t type = bytes_[p];
                const std::uint32_t klen = get_u32(p + 1);
                const std::uint32_t vlen = get_u32(p + 5);
                p += 9;
                if (p + klen + vlen > data_end_) {
                    break;
                }
                const std::string k(reinterpret_cast<const char*>(bytes_.data() + p), klen);
                if (k == key) {
                    saw_any = true;
                    if (type == 2u) {
                        out.state = find_state::deleted;
                    } else {
                        out.state = find_state::value;
                        out.value.assign(
                            reinterpret_cast<const char*>(bytes_.data() + p + klen), vlen);
                    }
                    break;
                }
                if (k > key) {
                    break;  // 块内有序
                }
                p += klen + vlen;
            }
        }
        if (!saw_any) {
            ++bloom_false_positives_;  // bloom 放行但查无 → 一次假阳性白读
        }
        return out;
    }

    // 整表顺序读出（含删除标记）—— range scan / 归并的上游
    std::vector<rec> collect_all() const {
        std::vector<rec> out;
        std::size_t p = 0;
        while (p + 9 <= data_end_) {
            const std::uint8_t type = bytes_[p];
            const std::uint32_t klen = get_u32(p + 1);
            const std::uint32_t vlen = get_u32(p + 5);
            p += 9;
            if (p + klen + vlen > data_end_) {
                throw std::runtime_error("corrupt sstable data area");
            }
            rec r;
            r.key.assign(reinterpret_cast<const char*>(bytes_.data() + p), klen);
            r.value.assign(reinterpret_cast<const char*>(bytes_.data() + p + klen), vlen);
            r.deleted = (type == 2u);
            out.push_back(std::move(r));
            p += klen + vlen;
        }
        return out;
    }

private:
    struct index_item {
        std::string first_key;
        std::uint64_t offset;
    };

    std::vector<std::uint8_t> bytes_;
    std::vector<index_item> index_;
    minilsm::bloom::filter bloom_;
    std::uint64_t index_off_{0};
    std::uint64_t data_end_{0};
    std::size_t bloom_negatives_{0};
    std::size_t bloom_false_positives_{0};

    std::uint32_t get_u32(std::size_t at) const {
        return (static_cast<std::uint32_t>(bytes_[at]) << 24) |
               (static_cast<std::uint32_t>(bytes_[at + 1]) << 16) |
               (static_cast<std::uint32_t>(bytes_[at + 2]) << 8) |
               static_cast<std::uint32_t>(bytes_[at + 3]);
    }

    std::uint64_t get_u64(std::size_t at) const {
        return (static_cast<std::uint64_t>(get_u32(at)) << 32) | get_u32(at + 4);
    }
};

}  // namespace minilsm::sst

#endif  // PH22_PROJECT_SSTABLE_H
