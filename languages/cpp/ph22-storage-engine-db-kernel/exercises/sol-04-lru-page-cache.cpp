// sol-04-lru-page-cache.cpp —— exercises/练习 4 参考实现：LRU 升级为页帧缓存（pin/dirty）
// 题目见 exercises/README.md。ph21 练习 1 写过 list+map 的 LRU 本体；本解把 LRU 用在
// “页帧”上：每帧一块 16 字节数据、带 dirty 与 pin，淘汰 = 帧回写磁盘再复用。
// 与 ph21 纯 LRU 的三个差异（这是 ph22 的增量）：
//   ① 值不是直接覆盖，而是“在帧内改完标脏”，脏页被淘汰前必须写回 backing store；
//   ② fix(id) 计数 pin，pin>0 的帧绝不淘汰（上层可能正持着帧内指针在改）；
//   ③ 容量/淘汰发生在“帧”粒度，命中帧只改顺序不改地址（帧数组地址稳定）。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -Wall -Wextra sol-04-lru-page-cache.cpp -o /tmp/ph22-sol04 && /tmp/ph22-sol04
// 验证状态：已验证（零警告、断言全绿、退出码 0）

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <list>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace pagelru {

constexpr std::size_t k_page_size = 16;  // 教学页大小：16 字节

// backing store：页号 → 字节数组（模拟磁盘上的页文件）
class disk {
public:
    void load(std::uint64_t id, std::uint8_t* out) const {
        std::fill(out, out + k_page_size, 0);
        const auto it = map_.find(id);
        if (it != map_.end()) {
            std::copy_n(it->second.begin(), k_page_size, out);
        }
    }
    void store(std::uint64_t id, const std::uint8_t* in) {
        std::array<std::uint8_t, k_page_size> buf{};
        std::copy_n(in, k_page_size, buf.begin());
        map_[id] = std::move(buf);
    }
    std::string read_as_str(std::uint64_t id) const {
        std::uint8_t tmp[k_page_size];
        load(id, tmp);
        const char* begin = reinterpret_cast<const char*>(tmp);
        const char* end = std::find(begin, begin + k_page_size, '\0');
        return std::string(begin, end);  // 截到 NUL（页剩余是 0 填充）
    }

private:
    std::unordered_map<std::uint64_t, std::array<std::uint8_t, k_page_size>> map_;
};

class page_cache {
public:
    page_cache(std::size_t capacity, disk& d) : capacity_{capacity}, disk_{d}, frames_(capacity) {
        if (capacity == 0) {
            throw std::invalid_argument("capacity must > 0");
        }
    }

    struct frame {
        std::uint64_t id{0};
        std::array<std::uint8_t, k_page_size> bytes{};
        bool used{false};
        bool dirty{false};
        int pins{0};
    };

    // fix：取帧。帧地址在 unfix 前有效（帧数组定长，无重分配）。
    frame* fix(std::uint64_t id) {
        const auto it = index_.find(id);
        if (it != index_.end()) {
            frame& f = frames_[it->second];
            ++f.pins;
            if (f.pins == 1) {
                remove_from_lru(it->second);  // 钉住期间不是淘汰候选
            }
            ++hits_;  // 命中：帧已在池内
            return &f;
        }
        const std::size_t slot = victim();
        frame& f = frames_[slot];
        if (f.used) {
            if (f.dirty) {
                disk_.store(f.id, f.bytes.data());  // ★ 脏帧被淘汰前写回
            }
            index_.erase(f.id);
            ++evictions_;
        }
        f.id = id;
        f.used = true;
        f.dirty = false;
        f.pins = 1;
        disk_.load(id, f.bytes.data());
        index_[id] = slot;
        ++misses_;
        return &f;
    }

    void unfix(std::uint64_t id) {
        const auto it = index_.find(id);
        if (it == index_.end() || frames_[it->second].pins <= 0) {
            throw std::runtime_error("bad unfix");
        }
        frame& f = frames_[it->second];
        --f.pins;
        if (f.pins == 0) {
            lru_.push_front(it->second);  // 解锁即“最近”
        }
    }

    // 统计口径：miss 在 fix(新页) 计；hit = fix 直接命中
    std::size_t hits() const { return hits_; }
    std::size_t misses() const { return misses_; }
    std::size_t evictions() const { return evictions_; }
    bool resident(std::uint64_t id) const { return index_.find(id) != index_.end(); }

private:
    std::size_t capacity_;
    disk& disk_;
    std::vector<frame> frames_;
    std::unordered_map<std::uint64_t, std::size_t> index_;
    std::list<std::size_t> lru_;  // 未钉帧：头=最近，尾=最久
    std::size_t hits_{0};
    std::size_t misses_{0};
    std::size_t evictions_{0};

    void remove_from_lru(std::size_t slot) {
        for (auto it = lru_.begin(); it != lru_.end(); ++it) {
            if (*it == slot) {
                lru_.erase(it);
                return;
            }
        }
    }

    // 空槽优先，否则淘汰 LRU 尾（未钉帧）；全部被钉则抛（上层 bug）
    std::size_t victim() {
        for (std::size_t i = 0; i < capacity_; ++i) {
            if (!frames_[i].used) {
                return i;
            }
        }
        while (!lru_.empty()) {
            const std::size_t s = lru_.back();
            lru_.pop_back();
            if (frames_[s].pins == 0) {
                return s;
            }
        }
        throw std::runtime_error("all frames pinned");
    }
};

}  // namespace pagelru

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

// 把 8 字符文本写入帧开头（教学页写操作）
static void write_tag(pagelru::page_cache::frame* f, const std::string& tag) {
    std::fill(f->bytes.begin(), f->bytes.end(), 0);
    std::copy(tag.begin(), tag.end(), f->bytes.begin());
    f->dirty = true;
}

int main() {
    // —— 场景 1：装满 + 再取新页触发 LRU 淘汰，且脏页写回 ——
    pagelru::disk disk;
    pagelru::page_cache cache{3, disk};

    for (std::uint64_t id = 1; id <= 3; ++id) {
        auto* f = cache.fix(id);
        write_tag(f, "page" + std::to_string(id));
        cache.unfix(id);
    }
    auto* f = cache.fix(4);  // 容量 3 已满 → 淘汰最久未用（1），写回 "page1"
    write_tag(f, "page4");
    cache.unfix(4);

    std::cout << "[1] 淘汰写回: disk[1] = \"" << disk.read_as_str(1)
              << "\" (期望 page1), 命中/未命/淘汰 = "
              << cache.hits() << '/' << cache.misses() << '/' << cache.evictions() << '\n';
    CHECK(!cache.resident(1));                 // 1 已被顶出
    CHECK(disk.read_as_str(1) == "page1");     // 脏帧写回成功
    CHECK(disk.read_as_str(1).size() >= 5);

    // —— 场景 2：get 命中即提前（证明是 LRU 不是 FIFO）——
    // 当前驻留：2,3,4，LRU 序（头=最近）为 4,3,2
    cache.fix(2);                               // 访问 2 → 提前为最近
    cache.unfix(2);
    auto* f5 = cache.fix(5);                    // 淘汰：最久是 3 而非 2
    CHECK(!cache.resident(3));
    CHECK(cache.resident(2));                   // 2 因刚被访问而活下来
    write_tag(f5, "page5");
    cache.unfix(5);
    std::cout << "[2] 访问 2 后再满: 淘汰的是 3 (非 FIFO 的 2), 2 仍在 = "
              << (cache.resident(2) ? "是" : "否") << '\n';
    CHECK(disk.read_as_str(3) == "page3");

    // —— 场景 3：pin 保护 ——
    // 当前驻留 2,4,5；LRU 尾（最久）= 4（4 最后被访问是场景 1 写入后）
    cache.fix(4);                               // 钉住 4 不 unfix
    auto* f6 = cache.fix(6);                    // 满：只能淘汰未钉中最久的 2（4 被钉跳过）
    CHECK(cache.resident(4));
    CHECK(!cache.resident(2));
    write_tag(f6, "page6");
    cache.unfix(6);
    cache.unfix(4);
    std::cout << "[3] pin 住 4 时请求 6: 淘汰 2, 4 存活 = "
              << (cache.resident(4) ? "是" : "否") << '\n';
    CHECK(disk.read_as_str(2) == "page2");      // 2 也是脏的，淘汰时写回

    std::cout << "checks: " << g_checks << ", failed: " << g_failed << '\n';
    if (g_failed == 0) {
        std::cout << "ph22-sol-04 OK\n";
        return 0;
    }
    return 1;
}
