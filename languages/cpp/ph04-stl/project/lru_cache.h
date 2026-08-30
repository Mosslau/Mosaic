// 来源：project/ —— LRU Cache 模板类头文件（std::list + std::unordered_map）
// 一句话说明：LRU（Least Recently Used）Cache，order_ 维护访问序、table_ 做 O(1) 定位，
//             get/put 均 O(1)，超容量时淘汰最久未使用项。
// 模板类实现必须放在头文件（实例化时需要完整定义），这是模板与普通类 .cpp/.h 分离的差异。
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 main.cpp -o lru_cache
// 验证状态：已验证
#ifndef TENET_CPP_PH04_LRU_CACHE_H
#define TENET_CPP_PH04_LRU_CACHE_H

#include <cstddef>
#include <list>
#include <optional>
#include <unordered_map>
#include <utility>

template <typename Key, typename Value>
class LruCache {
public:
    explicit LruCache(std::size_t capacity) : capacity_(capacity) {}

    std::size_t size() const { return order_.size(); }

    bool contains(const Key& key) const { return table_.find(key) != table_.end(); }

    // 命中：把节点 splice 到 front 并返回值；未命中返回 std::nullopt
    std::optional<Value> get(const Key& key) {
        auto it = table_.find(key);
        if (it == table_.end()) return std::nullopt;
        order_.splice(order_.begin(), order_, it->second);   // O(1) 移到最前
        return it->second->second;
    }

    // 插入或更新；超过容量时淘汰最久未使用（back）
    void put(const Key& key, const Value& value) {
        auto it = table_.find(key);
        if (it != table_.end()) {
            it->second->second = value;                       // 更新值
            order_.splice(order_.begin(), order_, it->second); // 刷新访问序
            return;
        }
        order_.emplace_front(key, value);                     // 新节点放到 front
        table_.emplace(key, order_.begin());                  // map 定位到该节点
        if (order_.size() > capacity_) evict();
    }

private:
    void evict() {
        table_.erase(order_.back().first);  // 从 map 删除最久未使用 key
        order_.pop_back();                  // 从 list 移除节点
    }

    using ListType = std::list<std::pair<Key, Value>>;
    std::size_t capacity_;
    ListType order_;                                            // front 最近使用
    std::unordered_map<Key, typename ListType::iterator> table_;
};

#endif  // TENET_CPP_PH04_LRU_CACHE_H
