// ex05-iterator-range-scan.cpp —— Iterator 抽象：把 MemTable 与 SSTable 接成 range scan
// 对应 ph22 主文档 3.9 与 roadmap §22「用 Iterator 抽象 MemTable 和 SSTable 的 range scan」；
// 兑现 ph21 project「下一阶段」预告：skip_list 的 begin()/end() 有序扫描只是单表读面，
// 多个表（一个内存 MemTable + 多个磁盘 SSTable）要用统一的 Iterator 抽象 + 多源归并。
// 教学点：
//   ① Iterator 接口（Valid/Next/Seek/Key/Value）让“内存有序结构”与“磁盘有序文件”
//      露出同一张读面——上层（scan 执行器）完全不关心数据来自内存还是磁盘；
//   ② mem 迭代器：包 std::map 迭代器（project/ 里换成 ph21 skip_list_map，接口同款）；
//   ③ sst 迭代器：整文件解析为有序 entry 数组后按下标前进（真实版是逐 block 迭代，
//      这里把“块内顺扫”压缩成数组游标，聚焦归并逻辑）；
//   ④ merge_iterator：多路按 (key, 源序号) 取最小，“新层赢旧层”——同 key 只保留
//      序号最小（最新）的那个值；delete/tombstone 语义属 project/，此处只做“覆盖”。
//   ⑤ seek(key) = lower_bound 语义：定位到第一个 >= key，是 range scan [lo, hi) 的入口。
// 资源管理：children_ 用 unique_ptr 持有（多态析构，R.11）；文件字节归 vector 所有。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -Wall -Wextra ex05-iterator-range-scan.cpp -o /tmp/ph22-ex05 && /tmp/ph22-ex05
// 验证状态：已验证（零警告、断言全绿、退出码 0）

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace its {

// —— 统一读面：MemTable 与 SSTable 都实现它 ——
class kv_iterator {
public:
    virtual ~kv_iterator() = default;
    virtual bool valid() const = 0;
    virtual void next() = 0;                             // 前提：valid()
    virtual void seek(std::string_view key) = 0;         // lower_bound：第一个 >= key
    virtual void seek_to_first() = 0;
    virtual std::string_view key() const = 0;
    virtual std::string_view value() const = 0;
};

// —— 内存 MemTable 的迭代器（教学用 std::map 充当；ph22 project 换成 ph21 skip_list_map）——
class mem_iterator : public kv_iterator {
public:
    explicit mem_iterator(const std::map<std::string, std::string>& table)
        : table_{&table}, it_{table.end()} {}

    bool valid() const override { return it_ != table_->end(); }

    void next() override {
        if (valid()) {
            ++it_;
        }
    }

    void seek(std::string_view key) override {
        it_ = table_->lower_bound(std::string(key));  // 树的下界 = range scan 起点
    }

    void seek_to_first() override { it_ = table_->begin(); }

    std::string_view key() const override { return it_->first; }
    std::string_view value() const override { return it_->second; }

private:
    const std::map<std::string, std::string>* table_;
    std::map<std::string, std::string>::const_iterator it_;
};

// —— “磁盘”SSTable 迭代器：文件写成简单 record 流，打开后解析为有序 entry 数组 ——
// 教学简化（注明）：真实 SSTable 逐 block 迭代（ex02 布局），此处把整文件解析成
// 有序数组，用下标当“块内顺扫”，以聚焦多源归并本身。
struct sst_entry {
    std::string key;
    std::string value;
};

// 写迷你 SSTable 文件：entry = [klen u32][vlen u32][key][value]，升序
void write_entries_file(const std::string& path, const std::vector<sst_entry>& entries) {
    std::vector<std::uint8_t> buf;
    for (const auto& e : entries) {
        const std::uint32_t klen = static_cast<std::uint32_t>(e.key.size());
        const std::uint32_t vlen = static_cast<std::uint32_t>(e.value.size());
        const std::uint8_t h[8] = {
            static_cast<std::uint8_t>((klen >> 24) & 0xFFu),
            static_cast<std::uint8_t>((klen >> 16) & 0xFFu),
            static_cast<std::uint8_t>((klen >> 8) & 0xFFu),
            static_cast<std::uint8_t>(klen & 0xFFu),
            static_cast<std::uint8_t>((vlen >> 24) & 0xFFu),
            static_cast<std::uint8_t>((vlen >> 16) & 0xFFu),
            static_cast<std::uint8_t>((vlen >> 8) & 0xFFu),
            static_cast<std::uint8_t>(vlen & 0xFFu),
        };
        buf.insert(buf.end(), h, h + 8);
        buf.insert(buf.end(), e.key.begin(), e.key.end());
        buf.insert(buf.end(), e.value.begin(), e.value.end());
    }
    const int fd = ::open(path.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) {
        throw std::runtime_error("open(write) failed: " + path);
    }
    std::size_t done = 0;
    while (done < buf.size()) {
        const ssize_t w = ::write(fd, buf.data() + done, buf.size() - done);
        if (w < 0) {
            if (errno == EINTR) {
                continue;
            }
            ::close(fd);
            throw std::runtime_error("write failed");
        }
        done += static_cast<std::size_t>(w);
    }
    if (::close(fd) != 0) {
        throw std::runtime_error("close failed");
    }
}

class sst_iterator : public kv_iterator {
public:
    explicit sst_iterator(const std::string& path) {
        // 读整个文件字节
        const int fd = ::open(path.c_str(), O_RDONLY);
        if (fd < 0) {
            throw std::runtime_error("open(read) failed: " + path);
        }
        std::vector<std::uint8_t> bytes;
        std::array<std::uint8_t, 4096> chunk{};
        ssize_t n = 0;
        while ((n = ::read(fd, chunk.data(), chunk.size())) > 0) {
            bytes.insert(bytes.end(), chunk.begin(), chunk.begin() + n);
        }
        ::close(fd);
        if (n < 0) {
            throw std::runtime_error("read failed");
        }
        // 解析 record 流（klen u32 + vlen u32 + key + value）
        std::size_t p = 0;
        while (p < bytes.size()) {
            if (p + 8 > bytes.size()) {
                throw std::runtime_error("truncated sst file");
            }
            const std::uint32_t klen = (static_cast<std::uint32_t>(bytes[p]) << 24) |
                                       (static_cast<std::uint32_t>(bytes[p + 1]) << 16) |
                                       (static_cast<std::uint32_t>(bytes[p + 2]) << 8) |
                                       static_cast<std::uint32_t>(bytes[p + 3]);
            const std::uint32_t vlen = (static_cast<std::uint32_t>(bytes[p + 4]) << 24) |
                                       (static_cast<std::uint32_t>(bytes[p + 5]) << 16) |
                                       (static_cast<std::uint32_t>(bytes[p + 6]) << 8) |
                                       static_cast<std::uint32_t>(bytes[p + 7]);
            p += 8;
            if (p + klen + vlen > bytes.size()) {
                throw std::runtime_error("truncated entry");
            }
            entries_.push_back({
                std::string(reinterpret_cast<const char*>(bytes.data() + p), klen),
                std::string(reinterpret_cast<const char*>(bytes.data() + p + klen), vlen),
            });
            p += klen + vlen;
        }
        idx_ = entries_.size();
    }

    bool valid() const override { return idx_ < entries_.size(); }

    void next() override {
        if (valid()) {
            ++idx_;
        }
    }

    void seek(std::string_view key) override {
        // 有序数组 + 二分：等价于“索引定位到块 → 块内顺扫到边界”
        idx_ = static_cast<std::size_t>(std::lower_bound(
            entries_.begin(), entries_.end(), std::string(key),
            [](const sst_entry& e, const std::string& k) { return e.key < k; }) -
            entries_.begin());
    }

    void seek_to_first() override { idx_ = 0; }

    std::string_view key() const override { return entries_[idx_].key; }
    std::string_view value() const override { return entries_[idx_].value; }

private:
    std::vector<sst_entry> entries_;
    std::size_t idx_{0};
};

// —— 多源归并迭代器：子迭代器按“新 → 旧”排序；同 key 保留序号最小（最新）的值 ——
class merge_iterator : public kv_iterator {
public:
    explicit merge_iterator(std::vector<std::unique_ptr<kv_iterator>> children)
        : children_{std::move(children)} {
        for (auto& c : children_) {
            c->seek_to_first();
        }
        pick_min();
    }

    bool valid() const override { return active_ < children_.size(); }

    void next() override {
        if (!valid()) {
            return;
        }
        const std::string_view cur = key();
        children_[active_]->next();          // 前进当前的源
        // 清掉其他源里同样 key 的旧版本（新层赢旧层：它们已经输给当前值）
        for (std::size_t i = 0; i < children_.size(); ++i) {
            if (i != active_ && children_[i]->valid() && children_[i]->key() == cur) {
                children_[i]->next();
            }
        }
        pick_min();
    }

    void seek(std::string_view key) override {
        for (auto& c : children_) {
            c->seek(key);
        }
        pick_min();
    }

    void seek_to_first() override {
        for (auto& c : children_) {
            c->seek_to_first();
        }
        pick_min();
    }

    std::string_view key() const override { return children_[active_]->key(); }
    std::string_view value() const override { return children_[active_]->value(); }

private:
    std::vector<std::unique_ptr<kv_iterator>> children_;
    std::size_t active_{0};  // == children_.size() 表示无候选（end）

    // 在全部 valid 子迭代器中选 (key, 源序号) 最小者；同 key 的旧版本在此被吞掉
    void pick_min() {
        active_ = children_.size();
        for (std::size_t i = 0; i < children_.size(); ++i) {
            if (!children_[i]->valid()) {
                continue;
            }
            if (active_ == children_.size() || std::make_pair(children_[i]->key(), i) <
                                                  std::make_pair(children_[active_]->key(), active_)) {
                active_ = i;
            }
        }
        if (active_ == children_.size()) {
            return;
        }
        // 同一 key 的其他（更旧）源直接前进跳过
        const std::string_view chosen = children_[active_]->key();
        for (std::size_t i = 0; i < children_.size(); ++i) {
            if (i != active_ && children_[i]->valid() && children_[i]->key() == chosen) {
                children_[i]->next();
            }
        }
    }
};

// 把迭代器当前区间 [lo, hi) 全量读出来（返回字符串仅供断言）
std::vector<std::pair<std::string, std::string>> drain(kv_iterator& it) {
    std::vector<std::pair<std::string, std::string>> out;
    for (; it.valid(); it.next()) {
        out.emplace_back(std::string(it.key()), std::string(it.value()));
    }
    return out;
}

}  // namespace its

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

static std::string dump(const std::vector<std::pair<std::string, std::string>>& rows) {
    std::string out;
    for (const auto& [k, v] : rows) {
        if (!out.empty()) {
            out += ' ';
        }
        out += k + '=' + v;
    }
    return out;
}

int main() {
    const std::string f1 = "/tmp/ph22-ex05-f1.sst";
    const std::string f2 = "/tmp/ph22-ex05-f2.sst";
    ::unlink(f1.c_str());
    ::unlink(f2.c_str());

    // 数据：三层（mem 最新 > f1 > f2 最旧）
    std::map<std::string, std::string> mem{{"apple", "mem"}, {"banana", "mem"}, {"cherry", "mem"}};
    its::write_entries_file(f1, {{"apple", "f1"}, {"avocado", "f1"}, {"banana", "f1-old"}, {"fig", "f1"}});
    its::write_entries_file(f2, {{"apple", "f2"}, {"date", "f2"}});

    // 按“新 → 旧”排子迭代器
    std::vector<std::unique_ptr<its::kv_iterator>> children;
    children.push_back(std::make_unique<its::mem_iterator>(mem));
    children.push_back(std::make_unique<its::sst_iterator>(f1));
    children.push_back(std::make_unique<its::sst_iterator>(f2));
    its::merge_iterator scan{std::move(children)};

    // 1. 全表 range scan：同 key 新层赢旧层（apple=mem 盖掉 f1/f2；banana=mem 盖掉 f1-old）
    auto full = its::drain(scan);
    std::cout << "[1] 全表有序扫描: " << dump(full) << '\n';
    CHECK(full.size() == 6);
    CHECK(full[0] == std::make_pair(std::string("apple"), std::string("mem")));
    CHECK(full[1] == std::make_pair(std::string("avocado"), std::string("f1")));
    CHECK(full[2] == std::make_pair(std::string("banana"), std::string("mem")));
    CHECK(full[3] == std::make_pair(std::string("cherry"), std::string("mem")));
    CHECK(full[4] == std::make_pair(std::string("date"), std::string("f2")));
    CHECK(full[5] == std::make_pair(std::string("fig"), std::string("f1")));

    // 2. 从中间 seek：模拟 range scan [cherry, +∞)
    scan.seek("cherry");
    auto tail = its::drain(scan);
    std::cout << "[2] seek(\"cherry\") 起扫描: " << dump(tail) << '\n';
    CHECK(tail.size() == 3);
    CHECK(tail[0].first == "cherry" && tail[1].first == "date" && tail[2].first == "fig");

    // 3. seek 落在 gap 里的 key：banana < "beat" < cherry → 起点是 cherry，banana 被跳过
    scan.seek("beat");
    auto gap = its::drain(scan);
    std::cout << "[3] seek(\"beat\") 起扫描: " << dump(gap) << '\n';
    CHECK(gap.size() == 3 && gap[0].first == "cherry" && gap[1].first == "date" &&
          gap[2].first == "fig");

    // 4. seek 超过最大值 → 空
    scan.seek("zzz");
    auto beyond = its::drain(scan);
    CHECK(beyond.empty());

    ::unlink(f1.c_str());
    ::unlink(f2.c_str());
    std::cout << "checks: " << g_checks << ", failed: " << g_failed << '\n';
    if (g_failed == 0) {
        std::cout << "ph22-ex05 OK\n";
        return 0;
    }
    return 1;
}
