# ph04 阶段项目：LRU Cache

对应 Roadmap「4. STL 标准库阶段」推荐项目第一个「LRU Cache」。用 `lru_cache.h`（模板类）+ `main.cpp`（assert 自测）多文件组织。

## 需求

实现一个 LRU（Least Recently Used）Cache：容量固定，`get(key)` / `put(key, value)` 均 **O(1)**；超出容量时淘汰**最久未使用**的条目。

核心是 `std::list` + `std::unordered_map` 的组合：

- `order_`：`std::list<std::pair<Key, Value>>` 维护访问顺序，`front` 最近使用、`back` 最久未使用
- `table_`：`std::unordered_map<Key, list::iterator>` 把 key 直接定位到 list 节点，避免线性扫描

## 功能清单

- [ ] `get(key)`：命中返回 `std::optional<Value>` 并把节点移到 `front`；未命中返回 `std::nullopt`
- [ ] `put(key, value)`：key 已存在则更新值并刷新访问序；不存在则插入到 `front`
- [ ] 超容量淘汰：插入后 `size() > capacity` 时淘汰 `back`（最久未使用）
- [ ] `size()` / `contains(key)`：查询接口（`contains` / `size` 为 const 成员函数）
- [ ] 自测：`main.cpp` 内 assert 覆盖基本路径 / 淘汰 / 刷新序 / 更新 / 容量 0 边界

## 验收标准

- [ ] `g++ -Wall -Wextra -std=c++17 main.cpp -o lru_cache` 编译零警告
- [ ] 运行 `./lru_cache` 全部 assert 通过（输出 `LRU Cache 全部 assert 通过`）
- [ ] 插入顺序 `1,2,3` 后访问 `1`、`2`，再插入 `4` 时被淘汰的是 `3`（最久未使用）
- [ ] 代码遵循 C++ Core Guidelines：不裸 `new`/`delete`、默认 `const`、`std::optional` 表达可缺失返回值

## 扩展方向

- 用 `std::string_view` 作 key 的只读视图，避免短生命周期 key 的拷贝 —— 属于 ph04 零开销视图内容
- 支持遍历缓存内容（暴露只读迭代器）与 `clear()` 清空
- 换成 `std::unordered_map<Key, Value>` + 时间戳的惰性淘汰版本，对比两种实现的命中率与开销
- 加 `std::mutex` 变成线程安全版本 —— 属于 ph08 并发阶段

## 验证环境

Apple clang 17.0.0（g++ 兼容），标准 C++17。编译：`g++ -Wall -Wextra -std=c++17 main.cpp -o lru_cache`；运行：`./lru_cache`。已在本环境验证。
