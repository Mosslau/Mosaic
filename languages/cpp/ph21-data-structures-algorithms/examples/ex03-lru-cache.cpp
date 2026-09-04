// ex03-lru-cache.cpp —— LRU Cache：list + unordered_map 组合实现
// 对应主文档 3.8。教学点：STL 无单一容器同时给「O(1) 按键定位 + O(1) 顺序调整 + O(1) 淘汰」，
// 标准工程答案是 std::list（记录访问顺序）+ unordered_map<Key, list 迭代器>（按键定位）；
// list 的「增删不使其他迭代器失效」是组合成立的根。
// 复杂度：get/put 均摊 O(1)；空间 O(capacity)。边界：cap=0、get 命中也要提前、重复 put。
// 验证环境：Apple clang 21.0.0（/usr/bin/clang++），macOS arm64 + libc++
// 编译/运行：clang++ -std=c++20 -Wall -Wextra ex03-lru-cache.cpp -o /tmp/ph21-ex03 && /tmp/ph21-ex03
// 验证状态：已验证（编译零警告、断言全绿、退出码 0）
#include <cstddef>
#include <iostream>
#include <list>
#include <optional>
#include <string>
#include <unordered_map>
#include <utility>

namespace {

void require(bool cond, const char* what) {
    if (!cond) {
        std::cerr << "FAIL: " << what << '\n';
        std::exit(1);
    }
}

template <typename K, typename V>
class lru_cache {
public:
    explicit lru_cache(std::size_t capacity) : capacity_{capacity} {}

    // get：命中即「最近用过」，O(1)
    std::optional<V> get(const K& key) {
        const auto it = index_.find(key);
        if (it == index_.end()) {
            return std::nullopt;
        }
        order_.splice(order_.begin(), order_, it->second);   // list O(1)：移到头部
        return it->second->second;
    }

    void put(const K& key, V value) {
        if (capacity_ == 0) {
            return;                                          // ★ 边界：cap=0 时缓存不存任何东西
        }
        const auto it = index_.find(key);
        if (it != index_.end()) {                            // 已存在：更新值 + 提前
            it->second->second = std::move(value);
            order_.splice(order_.begin(), order_, it->second);
            return;
        }
        order_.emplace_front(key, std::move(value));         // 新节点放头部
        index_[key] = order_.begin();
        if (order_.size() > capacity_) {
            evict_tail();                                    // 超容淘汰最久未用
        }
    }

    std::size_t size() const { return order_.size(); }
    bool contains(const K& key) const { return index_.contains(key); }

private:
    std::size_t capacity_;
    std::list<std::pair<K, V>> order_;   // 头 = 最近，尾 = 最久
    std::unordered_map<K, typename std::list<std::pair<K, V>>::iterator> index_;

    void evict_tail() {
        const K& victim = order_.back().first;
        index_.erase(victim);            // 先删索引再删节点：顺序别反（erase 会改 list 结构）
        order_.pop_back();
    }
};

}  // namespace

int main() {
    // 场景：容量 3；get 命中提升；满时淘汰最久未用
    lru_cache<int, std::string> cache(3);
    cache.put(1, "one");
    cache.put(2, "two");
    cache.put(3, "three");
    // 顺序（头→尾）：3, 2, 1
    require(cache.get(1) == std::optional<std::string>{"one"}, "get hit returns value");
    // get(1) 之后顺序：1, 3, 2 → 最久是 2
    cache.put(4, "four");                // 淘汰 2
    require(!cache.contains(2), "evict least recently used (was 2)");
    require(cache.contains(1) && cache.contains(3) && cache.contains(4),
            "remaining keys after eviction");
    require(cache.get(2) == std::nullopt, "evicted key get -> nullopt");

    // 重复 put：更新值且提前
    cache.put(3, "THREE");
    require(cache.get(3) == std::optional<std::string>{"THREE"}, "re-put updates value");
    // 顺序（头→尾）：3, 4, 1 → 最久是 1
    cache.put(5, "five");                // 淘汰 1
    require(!cache.contains(1), "second eviction kicks least recent (1)");
    require(cache.size() == 3, "capacity never exceeded");

    // cap = 0 边界：任何 put 都不保留
    lru_cache<int, int> zero(0);
    zero.put(1, 10);
    require(zero.size() == 0 && zero.get(1) == std::nullopt, "capacity-0 cache stores nothing");

    std::cout << "ex03-lru-cache OK\n";
    return 0;
}
