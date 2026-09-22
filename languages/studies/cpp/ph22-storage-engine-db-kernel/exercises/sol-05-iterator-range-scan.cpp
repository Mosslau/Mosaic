// sol-05-iterator-range-scan.cpp —— exercises/练习 5 参考实现：Iterator 抽象跨源 range scan
// 题目见 exercises/README.md。roadmap 练习要求“用 Iterator 抽象 MemTable 和 SSTable 的
// range scan”；与 examples/ex05 的不同点：本解把 **删除（tombstone）语义** 也放进归并层——
// 空 value 表示“这个 key 已被删除”，任何源里最新的一份若为空，则整 key 从读面消失。
// 设计：
//   ① kv_iterator 统一读面（valid/next/seek/key/value），MemTable（std::map 站位）与
//      SSTable（解析后的有序 entry 数组）都实现它；
//   ② merge_iterator 每步做三件事：跨源取 (key, 源序号) 最小 → 若最新值是空（删除）则
//      把同 key 的所有源都前进（key 被隐藏）→ 否则输出并跳过同 key 的旧源（新层赢旧层）；
//   ③ seek(key) 是 range scan [lo, +∞) 的入口（lower_bound 语义）。
// 教学简化（注明）：MemTable 用 std::map 且“空 value = 删除标记”（真实版是 entry 带
// deleted 位，见 project/）；两个文件源只放真值，删除只出现在内存层，已足够演示遮挡规则。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -Wall -Wextra sol-05-iterator-range-scan.cpp -o /tmp/ph22-sol05 && /tmp/ph22-sol05
// 验证状态：已验证（零警告、断言全绿、退出码 0）

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace scan5 {

// —— 统一读面 ——
class kv_iterator {
public:
    virtual ~kv_iterator() = default;
    virtual bool valid() const = 0;
    virtual void next() = 0;
    virtual void seek(std::string_view key) = 0;   // 第一个 >= key
    virtual std::string_view key() const = 0;
    virtual std::string_view value() const = 0;    // 空 value = 删除标记（教学约定）
};

// —— MemTable 源（std::map；空 value 表示该 key 已被删除）——
class mem_source : public kv_iterator {
public:
    explicit mem_source(const std::map<std::string, std::string>& t)
        : table_{&t}, it_{t.end()} {}

    bool valid() const override { return it_ != table_->end(); }
    void next() override {
        if (valid()) {
            ++it_;
        }
    }
    void seek(std::string_view key) override {
        it_ = table_->lower_bound(std::string(key));
    }
    std::string_view key() const override { return it_->first; }
    std::string_view value() const override { return it_->second; }

private:
    const std::map<std::string, std::string>* table_;
    std::map<std::string, std::string>::const_iterator it_;
};

struct sst_entry {
    std::string key;
    std::string value;  // 文件源里的真值（本例不落删除标记）
};

// 写迷你有序文件：record = [klen u32][vlen u32][key][value]
void write_file(const std::string& path, const std::vector<sst_entry>& entries) {
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
        throw std::runtime_error("open(write) failed");
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
    ::close(fd);
}

// —— SSTable 源：解析文件为有序 entry 数组，用二分 seek ——
class file_source : public kv_iterator {
public:
    explicit file_source(const std::string& path) {
        const int fd = ::open(path.c_str(), O_RDONLY);
        if (fd < 0) {
            throw std::runtime_error("open(read) failed");
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
        std::size_t p = 0;
        while (p + 8 <= bytes.size()) {
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
        idx_ = static_cast<std::size_t>(std::lower_bound(
            entries_.begin(), entries_.end(), std::string(key),
            [](const sst_entry& e, const std::string& k) { return e.key < k; }) -
            entries_.begin());
    }
    std::string_view key() const override { return entries_[idx_].key; }
    std::string_view value() const override { return entries_[idx_].value; }

private:
    std::vector<sst_entry> entries_;
    std::size_t idx_{0};
};

// —— 多源归并（新 → 旧）。空 value（删除标记）出现在“最新一份”时隐藏整个 key ——
class merge_iterator : public kv_iterator {
public:
    explicit merge_iterator(std::vector<std::unique_ptr<kv_iterator>> children)
        : children_{std::move(children)} {
        for (auto& c : children_) {
            c->seek(std::string_view{});  // 空 key：所有源都定位到首个 entry
        }
        refresh();
    }

    void seek_to_first() {
        for (auto& c : children_) {
            c->seek(std::string_view{});  // 空 key：任何 >= "" 即首个
        }
        refresh();
    }

    bool valid() const override { return active_ < children_.size(); }
    void next() override {
        if (!valid()) {
            return;
        }
        children_[active_]->next();
        refresh();
    }
    void seek(std::string_view key) override {
        for (auto& c : children_) {
            c->seek(key);
        }
        refresh();
    }
    std::string_view key() const override { return children_[active_]->key(); }
    std::string_view value() const override { return children_[active_]->value(); }

private:
    std::vector<std::unique_ptr<kv_iterator>> children_;
    std::size_t active_{0};  // == size() 表示无输出

    // 选当前最小 key；同 key 选序号最小（最新）；最新值为空 → key 被删除，全部前进再选
    void refresh() {
        while (true) {
            std::size_t best = children_.size();
            for (std::size_t i = 0; i < children_.size(); ++i) {
                if (!children_[i]->valid()) {
                    continue;
                }
                if (best == children_.size() ||
                    std::make_pair(children_[i]->key(), i) <
                        std::make_pair(children_[best]->key(), best)) {
                    best = i;
                }
            }
            if (best == children_.size()) {
                active_ = children_.size();
                return;
            }
            const std::string_view chosen_key = children_[best]->key();
            if (children_[best]->value().empty()) {
                // 最新一份是删除标记：该 key 对所有读者隐藏（含旧层残余）
                for (auto& c : children_) {
                    if (c->valid() && c->key() == chosen_key) {
                        c->next();
                    }
                }
                continue;  // 重新选下一个 key
            }
            active_ = best;
            for (std::size_t i = 0; i < children_.size(); ++i) {  // 吞掉同 key 旧源
                if (i != best && children_[i]->valid() && children_[i]->key() == chosen_key) {
                    children_[i]->next();
                }
            }
            return;
        }
    }
};

}  // namespace scan5

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
    const std::string f1 = "/tmp/ph22-sol05-f1.sst";
    const std::string f2 = "/tmp/ph22-sol05-f2.sst";
    ::unlink(f1.c_str());
    ::unlink(f2.c_str());

    // 数据：MemTable（最新）：k1 新值、k2 删除标记（空）、k3 新值
    std::map<std::string, std::string> mem{{"k1", "mem-v1"}, {"k2", ""}, {"k3", "mem-v3"}};
    // f1（中间）：k1 旧值、k2 有值、k3 有值、k5
    scan5::write_file(f1, {{"k1", "f1-v1"}, {"k2", "f1-v2"}, {"k3", "f1-v3"}, {"k5", "f1-v5"}});
    // f2（最旧）：k1 更旧、k4
    scan5::write_file(f2, {{"k1", "f2-v1"}, {"k4", "f2-v4"}});

    std::vector<std::unique_ptr<scan5::kv_iterator>> children;
    children.push_back(std::make_unique<scan5::mem_source>(mem));
    children.push_back(std::make_unique<scan5::file_source>(f1));
    children.push_back(std::make_unique<scan5::file_source>(f2));
    scan5::merge_iterator scan{std::move(children)};

    // 1. 全表：k1 取 mem、k2 被删除整个消失、k3 取 mem、k4/k5 取各自文件
    std::cout << "[1] 全表 range scan:\n";
    std::vector<std::pair<std::string, std::string>> rows;
    for (; scan.valid(); scan.next()) {
        rows.emplace_back(std::string(scan.key()), std::string(scan.value()));
        std::cout << "    " << scan.key() << "=" << scan.value() << '\n';
    }
    CHECK(rows.size() == 4);
    CHECK(rows[0] == std::make_pair(std::string("k1"), std::string("mem-v1")));
    CHECK(rows[1] == std::make_pair(std::string("k3"), std::string("mem-v3")));
    CHECK(rows[2] == std::make_pair(std::string("k4"), std::string("f2-v4")));
    CHECK(rows[3] == std::make_pair(std::string("k5"), std::string("f1-v5")));

    // 2. 点查视角：k2 不存在（被删除），k1/k3 是 mem 值
    auto probe = [&](const std::string& key) -> std::optional<std::string> {
        scan.seek(key);
        if (!scan.valid() || scan.key() != key) {
            return std::nullopt;
        }
        return std::string(scan.value());
    };
    std::cout << "[2] 点查: k1=" << (probe("k1") ? *probe("k1") : "(无)")
              << ", k2=" << (probe("k2") ? *probe("k2") : "(已删除/无)")
              << ", k4=" << (probe("k4") ? *probe("k4") : "(无)") << '\n';
    CHECK(probe("k1") == std::string("mem-v1"));
    CHECK(!probe("k2").has_value());   // 删除标记遮挡了 f1 的 k2
    CHECK(probe("k4") == std::string("f2-v4"));

    // 3. seek 语义：从 k3 起
    scan.seek("k3");
    std::size_t n = 0;
    for (; scan.valid(); scan.next()) {
        ++n;
    }
    std::cout << "[3] seek(\"k3\") 起共 " << n << " 条 (期望 3: k3,k4,k5)\n";
    CHECK(n == 3);

    ::unlink(f1.c_str());
    ::unlink(f2.c_str());
    std::cout << "checks: " << g_checks << ", failed: " << g_failed << '\n';
    if (g_failed == 0) {
        std::cout << "ph22-sol-05 OK\n";
        return 0;
    }
    return 1;
}
