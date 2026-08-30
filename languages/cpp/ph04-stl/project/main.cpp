// 来源：project/ —— LRU Cache 自测（assert 全过则无输出）
// 一句话说明：覆盖 put/get 基本路径、LRU 淘汰、get 刷新访问序、更新值、
//             容量 0 边界共 6 组断言。
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 main.cpp -o lru_cache
// 运行：./lru_cache
// 验证状态：已验证
#include <cassert>
#include <iostream>
#include <optional>
#include <string>

#include "lru_cache.h"

int main() {
    // 1. 基本 put / get
    LruCache<int, std::string> cache(3);
    assert(cache.size() == 0);
    cache.put(1, "one");
    cache.put(2, "two");
    cache.put(3, "three");
    assert(cache.size() == 3);
    assert(cache.get(1) == std::optional<std::string>("one"));
    assert(cache.get(2) == std::optional<std::string>("two"));

    // 2. 淘汰最久未使用：已访问 1、2，3 最久未使用 → 插入 4 时淘汰 3
    cache.put(4, "four");
    assert(cache.get(3) == std::nullopt);   // 3 被淘汰
    assert(cache.get(4) == std::optional<std::string>("four"));

    // 3. get 命中刷新访问序：当前最久为 1 → 插入 5 时淘汰 1
    assert(cache.get(2).has_value());       // 2 被刷新为最近使用
    cache.put(5, "five");
    assert(cache.get(1) == std::nullopt);   // 1 被淘汰
    assert(cache.get(2) == std::optional<std::string>("two"));

    // 4. put 已存在 key = 更新值 + 刷新访问序
    cache.put(2, "TWO");
    assert(cache.get(2) == std::optional<std::string>("TWO"));

    // 5. contains / size 边界
    assert(cache.contains(2));
    assert(!cache.contains(99));
    assert(cache.size() == 3);

    // 6. 容量 0 边界：不缓存任何内容
    LruCache<int, int> empty(0);
    empty.put(1, 100);
    assert(empty.size() == 0);
    assert(empty.get(1) == std::nullopt);

    std::cout << "LRU Cache 全部 assert 通过\n";
    return 0;
}
