// sol-01-resizable-lru.cpp —— 练习 1 参考实现：可动态改容量的 LRU Cache
// 对应主文档 3.8 与 roadmap §21 练习「LRU Cache」。
// 相对 examples/ex03 的增量要求：① 提供「按键访问顺序快照」接口，让 LRU 语义可被断言；
// ② 支持 set_capacity 动态改容量（变小立即淘汰到符合新容量）；③ cap=0 显式处理。
// 复杂度：get/put/set_capacity 均摊 O(1)（set_capacity 的总淘汰量为 O(淘汰数)）。
// 验证环境：Apple clang 21.0.0（/usr/bin/clang++），macOS arm64 + libc++
// 编译/运行：clang++ -std=c++20 -Wall -Wextra sol-01-resizable-lru.cpp -o /tmp/ph21-sol01 && /tmp/ph21-sol01
// 验证状态：已验证（编译零警告、断言全绿、退出码 0）
#include <cstddef>
#include <iostream>
#include <list>
#include <optional>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

void require(bool cond, const char* what) {
    if (!cond) {
        std::cerr << "FAIL: " << what << '\n';
        std::exit(1);
    }
}

template <typename K, typename V>
class resizable_lru {
public:
    explicit resizable_lru(std::size_t capacity) : capacity_{capacity} {}

    std::optional<V> get(const K& key) {
        const auto it = index_.find(key);
        if (it == index_.end()) {
            return std::nullopt;
        }
        order_.splice(order_.begin(), order_, it->second);   // 命中即最近
        return it->second->second;
    }

    void put(const K& key, V value) {
        if (capacity_ == 0) {
            return;                                          // cap=0：什么都不缓存
        }
        const auto it = index_.find(key);
        if (it != index_.end()) {
            it->second->second = std::move(value);
            order_.splice(order_.begin(), order_, it->second);
            return;
        }
        order_.emplace_front(key, std::move(value));
        index_[key] = order_.begin();
        if (order_.size() > capacity_) {
            evict_tail();
        }
    }

    // 动态改容量：变小则立即淘汰尾部直到符合新容量（O(淘汰数)）
    void set_capacity(std::size_t capacity) {
        capacity_ = capacity;
        while (order_.size() > capacity_) {
            evict_tail();
        }
    }

    // 访问顺序快照：头(最近) → 尾(最久)。让 LRU 语义可被测试断言
    std::vector<K> keys_in_recent_order() const {
        std::vector<K> out;
        out.reserve(order_.size());
        for (const auto& kv : order_) {
            out.push_back(kv.first);
        }
        return out;
    }

    std::size_t size() const { return order_.size(); }

private:
    std::size_t capacity_;
    std::list<std::pair<K, V>> order_;
    std::unordered_map<K, typename std::list<std::pair<K, V>>::iterator> index_;

    void evict_tail() {
        const K& victim = order_.back().first;
        index_.erase(victim);                                // 先删索引再删节点
        order_.pop_back();
    }
};

}  // namespace

int main() {
    resizable_lru<int, int> cache(3);
    cache.put(1, 100);
    cache.put(2, 200);
    cache.put(3, 300);
    // 顺序（头→尾）：3, 2, 1
    require(cache.keys_in_recent_order() == std::vector<int>({3, 2, 1}),
            "initial order head=most-recent");

    require(cache.get(2) == std::optional<int>{200}, "get hit returns value");
    require(cache.keys_in_recent_order() == std::vector<int>({2, 3, 1}),
            "get hit promotes key to head");

    require(cache.get(9) == std::nullopt, "get miss returns nullopt");
    require(cache.keys_in_recent_order() == std::vector<int>({2, 3, 1}),
            "get miss does not change order");

    cache.put(4, 400);                                       // 满：淘汰尾部 1
    require(cache.keys_in_recent_order() == std::vector<int>({4, 2, 3}),
            "put over capacity evicts least-recent (1)");

    cache.set_capacity(2);                                   // 缩小容量：立即淘汰 3
    require(cache.size() == 2, "set_capacity shrinks immediately");
    require(cache.keys_in_recent_order() == std::vector<int>({4, 2}),
            "shrink evicts from tail until within capacity");

    cache.put(5, 500);                                       // 再次淘汰尾部 2
    require(cache.keys_in_recent_order() == std::vector<int>({5, 4}),
            "after shrink, next put still respects capacity");
    require(cache.get(2) == std::nullopt && cache.get(4) == std::optional<int>{400},
            "evicted key gone, live key reachable");

    resizable_lru<int, int> zero(0);
    zero.put(1, 10);
    require(zero.size() == 0 && zero.get(1) == std::nullopt, "capacity-0 stores nothing");
    zero.set_capacity(2);
    zero.put(1, 10);
    require(zero.keys_in_recent_order() == std::vector<int>({1}), "grow from 0 works");

    std::cout << "sol-01-resizable-lru OK\n";
    return 0;
}
