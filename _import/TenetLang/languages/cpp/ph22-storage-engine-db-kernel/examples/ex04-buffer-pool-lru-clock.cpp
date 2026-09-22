// ex04-buffer-pool-lru-clock.cpp —— Buffer Pool：页帧 + 命中/脏页/pin-unpin + LRU 与 Clock 淘汰
// 对应 ph22 主文档 3.7 与 roadmap §22「Buffer Pool、LRU / Clock Cache」；
// 兑现 ph21 主文档「下一阶段」预告：练习 1 的 LRU 只是淘汰策略，Buffer Pool 还要加
// 脏页位、pin/unpin（被钉住的页不可淘汰）与磁盘页交换——这就是“LRU → 页缓存”的升级。
// 教学点：
//   ① fix(页号)/unfix 语义：读前 fix（计数 +1），读完必须 unfix；pin 住的页是淘汰禁区；
//   ② 脏页：改写后标脏，淘汰前必须写回磁盘（区别于“只读缓存”，Buffer Pool 才要写回）；
//   ③ LRU：维护“未钉帧”的访问顺序（list 头=最近），满时淘汰尾——精确记最近使用；
//   ④ Clock（二次机会/近似 LRU）：环形扫描 + 引用位，ref=1 只清位、ref=0 才淘汰——
//      只给“一圈”的第二次机会，比 LRU 省维护代价，代价是近似误差；
//   ⑤ 教学简化（注明）：页内容用 uint64 占位（真实页为 4/8/16 KiB 字节块），
//      磁盘用 unordered_map 模拟（真实为文件中的偏移）；策略差异是本节主角。
// 资源管理：本示例无裸资源（vector 池），RAII 纪律见主文档代码层说明。
// 验证环境：Apple clang 21.0.0（macOS arm64 + libc++）；命令：
//   clang++ -std=c++20 -Wall -Wextra ex04-buffer-pool-lru-clock.cpp -o /tmp/ph22-ex04 && /tmp/ph22-ex04
// 验证状态：已验证（零警告、断言全绿、退出码 0）

#include <cstddef>
#include <cstdint>
#include <iostream>
#include <list>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace bp {

enum class policy { lru, clock };

// 磁盘模拟：页号 → uint64 内容（“页”简化成 8 字节）
class disk_sim {
public:
    std::uint64_t read(std::uint64_t id) const {
        const auto it = map_.find(id);
        return it == map_.end() ? 0 : it->second;
    }
    void write(std::uint64_t id, std::uint64_t v) { map_[id] = v; }

private:
    std::unordered_map<std::uint64_t, std::uint64_t> map_;
};

class buffer_pool {
public:
    struct frame {
        std::uint64_t id{0};
        std::uint64_t data{0};
        bool used{false};
        bool dirty{false};
        bool ref{false};   // Clock 引用位
        int pins{0};
    };

    buffer_pool(std::size_t capacity, policy pol, disk_sim& disk)
        : capacity_{capacity}, pol_{pol}, disk_{disk}, frames_(capacity) {}

    // fix：取到可写的帧（内部返回指针在 unfix 前有效）。找不到可淘汰帧（全被 pin）则抛异常。
    frame* fix(std::uint64_t id) {
        const auto it = index_.find(id);
        if (it != index_.end()) {
            frame& f = frames_[it->second];
            ++f.pins;
            f.ref = true;                     // Clock：访问即置引用位
            if (pol_ == policy::lru) {
                remove_from_lru(it->second);  // 钉住期间不参与淘汰候选
            }
            ++hits_;
            return &f;
        }
        ++misses_;
        const std::size_t slot = pick_slot(); // 已有空槽 or 淘汰一个未钉帧
        frame& f = frames_[slot];
        if (f.used) {
            if (f.dirty) {                    // 淘汰脏页前必须先写回
                disk_.write(f.id, f.data);
                ++writebacks_;
            }
            index_.erase(f.id);
            victims_.push_back(f.id);
        }
        f.id = id;
        f.data = disk_.read(id);              // 从磁盘载入页
        f.used = true;
        f.dirty = false;
        f.ref = true;
        f.pins = 1;
        index_[id] = slot;
        return &f;
    }

    void unfix(std::uint64_t id) {
        const auto it = index_.find(id);
        if (it == index_.end()) {
            throw std::runtime_error("unfix unknown page");
        }
        frame& f = frames_[it->second];
        if (f.pins <= 0) {
            throw std::runtime_error("unfix without fix");
        }
        --f.pins;
        if (f.pins == 0 && pol_ == policy::lru) {
            lru_.push_front(it->second);      // 解锁即成为“最近未钉帧”
        }
    }

    // 最近一次淘汰序列（教学观察用）
    const std::vector<std::uint64_t>& victims() const { return victims_; }
    void reset_victims() { victims_.clear(); }
    std::size_t hits() const { return hits_; }
    std::size_t misses() const { return misses_; }
    std::size_t writebacks() const { return writebacks_; }
    bool resident(std::uint64_t id) const { return index_.find(id) != index_.end(); }

private:
    std::size_t capacity_;
    policy pol_;
    disk_sim& disk_;
    std::vector<frame> frames_;
    std::unordered_map<std::uint64_t, std::size_t> index_;
    std::list<std::size_t> lru_;              // 仅未钉帧：头=最近，尾=最久
    std::size_t hand_{0};                     // Clock 扫描指针
    std::vector<std::uint64_t> victims_;
    std::size_t hits_{0};
    std::size_t misses_{0};
    std::size_t writebacks_{0};

    void remove_from_lru(std::size_t slot) {
        for (auto it = lru_.begin(); it != lru_.end(); ++it) {
            if (*it == slot) {
                lru_.erase(it);
                return;
            }
        }
    }

    // 找一个可用的槽：先看空槽；没有则按策略淘汰一个未钉帧
    std::size_t pick_slot() {
        for (std::size_t i = 0; i < capacity_; ++i) {
            if (!frames_[i].used) {
                return i;
            }
        }
        if (pol_ == policy::lru) {
            while (!lru_.empty()) {
                const std::size_t slot = lru_.back();
                lru_.pop_back();
                if (frames_[slot].pins == 0) {
                    return slot;
                }
            }
        } else {  // clock：环形扫描，ref=1 只清位，ref=0 且未钉才是受害者
            for (std::size_t n = 0; n < capacity_ * 2; ++n) {
                frame& f = frames_[hand_];
                if (f.pins > 0) {
                    // 钉住的页跳过（不参与淘汰）
                } else if (f.ref) {
                    f.ref = false;  // 给一次“二次机会”，这一圈不淘汰
                } else {
                    const std::size_t slot = hand_;
                    hand_ = (hand_ + 1) % capacity_;
                    return slot;
                }
                hand_ = (hand_ + 1) % capacity_;
            }
        }
        throw std::runtime_error("pool full of pinned pages");
    }
};

}  // namespace bp

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

// 场景 A：同样的访问序列跑 LRU 与 Clock，比较淘汰序列（cap=4）
static void scenario_a() {
    std::cout << "[A] 同一访问序列下 LRU vs Clock 的淘汰分歧 (cap=4):\n";
    auto run = [](bp::policy pol) {
        bp::disk_sim disk;
        bp::buffer_pool pool{4, pol, disk};
        // 预加载 0..3
        for (std::uint64_t id = 0; id < 4; ++id) {
            pool.fix(id);
            pool.unfix(id);
        }
        // 访问 0（时钟置 ref，LRU 提前）→ 触发两次“插入驱逐”
        pool.fix(0);
        pool.unfix(0);
        pool.fix(4);
        pool.unfix(4);
        pool.fix(5);
        pool.unfix(5);
        return pool;
    };

    auto lru = run(bp::policy::lru);
    auto clk = run(bp::policy::clock);
    std::cout << "    LRU  淘汰序列: 4 号 miss -> " << lru.victims()[0]
              << ", 5 号 miss -> " << lru.victims()[1] << '\n';
    std::cout << "    Clock 淘汰序列: 4 号 miss -> " << clk.victims()[0]
              << ", 5 号 miss -> " << clk.victims()[1] << '\n';
    CHECK(lru.victims()[0] == 1 && lru.victims()[1] == 2);  // LRU 按“最久未用”淘汰
    CHECK(clk.victims()[0] == 0 && clk.victims()[1] == 1);  // Clock 把“刚访问过”的 0 先淘汰了
    // 教学结论：Clock 只给“一圈内的第二次机会”。访问 0 置了 ref=1，但随后插入
    // 4 触发的扫描从帧 0 起立刻把它清位，转回帧 0 前没有再次访问 → 0 仍被淘汰；
    // LRU 靠精确的“最近使用”顺序保住了 0（它在 LRU 里是最新，不是最久）。
    CHECK(lru.resident(0) && !clk.resident(0));
}

// 场景 B1：脏页写回（cap=2, LRU）
static void scenario_b1() {
    std::cout << "[B1] 脏页淘汰前写回 (cap=2, LRU):\n";
    bp::disk_sim disk;
    disk.write(10, 1);
    disk.write(11, 2);
    bp::buffer_pool pool{2, bp::policy::lru, disk};

    auto* f = pool.fix(10);
    f->data = 11;  // 页 10: 1 → 11，标脏
    f->dirty = true;
    pool.unfix(10);

    f = pool.fix(11);
    f->data = 22;  // 页 11: 2 → 22，标脏
    f->dirty = true;
    pool.unfix(11);

    // LRU：10 更久未用 → 请求 12 时先淘汰 10，写回 11
    pool.fix(12);
    pool.unfix(12);

    std::cout << "    淘汰 10 后: 磁盘 disk[10] = " << disk.read(10)
              << " (期望 11), disk[11] = " << disk.read(11)
              << " (期望 2, 还脏在池里没写回), 11 仍在池 = "
              << (pool.resident(11) ? "是" : "否") << '\n';
    CHECK(pool.victims().size() == 1 && pool.victims()[0] == 10);
    CHECK(disk.read(10) == 11);   // 脏页被淘汰 → 值已落盘
    CHECK(pool.resident(11));     // 没被淘汰的脏页保持内存态
    CHECK(disk.read(11) == 2);    // 它的写回要等它自己被淘汰或主动 flush
}

// 场景 B2：pin 保护（cap=2, LRU）
static void scenario_b2() {
    std::cout << "[B2] pin 住的页不可淘汰 (cap=2, LRU):\n";
    bp::disk_sim disk;
    disk.write(20, 5);
    disk.write(21, 6);
    bp::buffer_pool pool{2, bp::policy::lru, disk};

    pool.fix(20);   // 钉住 20（不 unfix）：即使它是最久未用也不许淘汰
    pool.fix(21);
    pool.unfix(21);

    pool.fix(22);   // 只能淘汰 21
    pool.unfix(22);
    pool.unfix(20);

    std::cout << "    请求 22 时: 淘汰 " << pool.victims()[0] << " (期望 21), "
              << "20 仍在池 = " << (pool.resident(20) ? "是" : "否") << '\n';
    CHECK(pool.victims().size() == 1 && pool.victims()[0] == 21);
    CHECK(pool.resident(20));   // 钉住的页活了下来
    CHECK(!pool.resident(21));
}

// 场景 C：命中率统计（热集工作负载：LRU 应该高命中）
static void scenario_c() {
    std::cout << "[C] 热集工作负载命中率:\n";
    for (const bp::policy pol : {bp::policy::lru, bp::policy::clock}) {
        bp::disk_sim disk;
        bp::buffer_pool pool{8, pol, disk};
        // 固定 6 页热集反复访问（20 轮 × 6 次 = 120 次 fix）
        for (int round = 0; round < 20; ++round) {
            for (std::uint64_t id = 0; id < 6; ++id) {
                pool.fix(id);
                pool.unfix(id);
            }
        }
        const std::size_t total = pool.hits() + pool.misses();
        const double hr = static_cast<double>(pool.hits()) / total;
        std::cout << "    " << (pol == bp::policy::lru ? "LRU  " : "Clock")
                  << ": hits=" << pool.hits() << " misses=" << pool.misses()
                  << " 命中率=" << hr * 100.0 << "%\n";
        CHECK(pool.misses() <= 8);  // 热集一旦装满就不再 miss
        CHECK(hr > 0.9);
    }
}

int main() {
    scenario_a();
    scenario_b1();
    scenario_b2();
    scenario_c();
    std::cout << "checks: " << g_checks << ", failed: " << g_failed << '\n';
    if (g_failed == 0) {
        std::cout << "ph22-ex04 OK\n";
        return 0;
    }
    return 1;
}
