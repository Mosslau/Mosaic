// ex02-hashmap-truth.cpp —— 哈希表工程真相：reserve/load factor/rehash/自定义 hash/插入语义
// 对应主文档 3.2。教学点：链式哈希 = bucket 数组 + 冲突链；rehash 让迭代器失效（引用仍有效）；
// reserve 免反复 rehash；operator[] / insert_or_assign / try_emplace 三种语义；pair key 需自定义 hash。
// 验证环境：Apple clang 21.0.0（/usr/bin/clang++），macOS arm64 + libc++
// 编译/运行：clang++ -std=c++20 -Wall -Wextra ex02-hashmap-truth.cpp -o /tmp/ph21-ex02 && /tmp/ph21-ex02
// 验证状态：已验证（编译零警告、断言全绿、退出码 0）
#include <cstddef>
#include <functional>
#include <iostream>
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

struct pair_hash {                       // pair<int,int> 没有 std::hash 特化：自定义
    std::size_t operator()(const std::pair<int, int>& p) const {
        const std::size_t h1 = std::hash<int>{}(p.first);
        const std::size_t h2 = std::hash<int>{}(p.second);
        return h1 ^ (h2 << 1);           // 混合两个哈希，避免对称碰撞
    }
};

void demo_reserve_stability() {
    std::unordered_map<int, int> m;
    m.reserve(64);                       // 预分桶：插入 ≤64 个不触发 rehash
    const std::size_t buckets_before = m.bucket_count();
    for (int i = 0; i < 40; ++i) {
        m.emplace(i, i * i);
    }
    std::cout << "reserve(64): bucket_count " << buckets_before << " -> "
              << m.bucket_count() << " (load " << m.load_factor() << ")\n";
    require(m.bucket_count() == buckets_before, "reserve avoids rehash within budget");
    require(m.load_factor() <= m.max_load_factor(), "load factor stays under max");
}

void demo_no_reserve_growth() {
    std::unordered_map<int, int> m;      // 不 reserve：小桶起步，越界自动 rehash
    const std::size_t buckets_before = m.bucket_count();
    for (int i = 0; i < 1000; ++i) {
        m.emplace(i, i);
    }
    std::cout << "no reserve: bucket_count " << buckets_before << " -> "
              << m.bucket_count() << " (load " << m.load_factor() << ")\n";
    require(m.bucket_count() > buckets_before, "bucket count grows as elements exceed load");
}

void demo_insert_semantics() {
    std::unordered_map<std::string, int> m;
    m["alice"] = 1;                      // operator[]：不存在则默认构造并插入
    m.insert_or_assign("alice", 2);      // 存在则覆盖（C++17）
    m.try_emplace("alice", 3);           // 存在则不覆盖、实参不被移动
    m.try_emplace("bob", 4);             // 不存在才插入
    require(m.at("alice") == 2, "insert_or_assign overwrites, try_emplace keeps");
    require(m.at("bob") == 4 && m.size() == 2, "try_emplace inserts only if absent");
    require(m.contains("alice") && !m.contains("carol"), "contains query (C++20)");
}

void demo_custom_hash_and_load() {
    std::unordered_map<std::pair<int, int>, int, pair_hash> grid;
    grid[{3, 4}] = 1;                    // 网格键：pair 需自定义 hash 才能进 unordered_map
    grid[{3, 5}] = 2;
    require(grid.at({3, 4}) == 1, "custom-hashed pair key lookups");

    std::unordered_map<int, int> m;
    m.max_load_factor(0.5f);             // 更早 rehash = 更短冲突链（空间换时间）
    require(m.max_load_factor() == 0.5f, "max_load_factor settable");
    m.reserve(100);
    require(m.load_factor() <= m.max_load_factor(), "reserve respects custom load factor");
}

}  // namespace

int main() {
    demo_reserve_stability();
    demo_no_reserve_growth();
    demo_insert_semantics();
    demo_custom_hash_and_load();
    std::cout << "ex02-hashmap-truth OK\n";
    return 0;
}
