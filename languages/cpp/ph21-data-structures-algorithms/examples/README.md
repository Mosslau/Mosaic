# examples —— C++ 数据结构与算法阶段完整示例

验证环境（实测）：macOS arm64，Apple clang 21.0.0（`/usr/bin/clang++`，默认 PATH）+ Homebrew clang 21.1.8（`/opt/homebrew/opt/llvm/bin/clang++`，仅 ex05 交叉核对）、libc++。**全部 6 个示例均已在本环境 `clang++ -std=c++20 -Wall -Wextra` 编译零警告、运行断言全绿（退出码 0）**。以下命令在 examples/ 目录内执行；可执行文件一律输出到 /tmp，仓库不落二进制。本阶段代码遵循 cpp-coding-standards：无裸 new/delete（Trie 用 `unique_ptr` 子节点）、容器优先、`enum class`/`const`/RAII 为默认；手写结构带复杂度标注与边界测试。

| 文件 | 对应主文档 | 一句话内容 | 验证状态 |
|------|-----------|-----------|----------|
| `ex01-stl-selection.cpp` | 3.1 | 线性容器工程选型：vector 扩容观察、deque 双端、list 的 splice、queue/stack 适配器 | 已验证（Apple clang 21.0.0） |
| `ex02-hashmap-truth.cpp` | 3.2 | 哈希表工程真相：reserve 免 rehash、不 reserve 时桶数增长、三种插入语义、pair 自定义 hash、max_load_factor | 已验证（Apple clang 21.0.0） |
| `ex03-lru-cache.cpp` | 3.8 | LRU Cache：list + unordered_map 组合，get 命中提前、淘汰最久、cap=0 边界 | 已验证（Apple clang 21.0.0） |
| `ex04-unionfind-trie.cpp` | 3.6/3.7 | 两个无 STL 等价物的手写结构：并查集（两个 vector 的森林）+ Trie（unique_ptr 子节点） | 已验证（Apple clang 21.0.0） |
| `ex05-graph-algos.cpp` | 3.5/3.12 | 图算法三件套：BFS 无权最短路、DFS 可达性、Dijkstra 最小堆 + 懒删除 | 已验证（Apple clang 21.0.0 与 Homebrew clang 21.1.8 双编译器） |
| `ex06-sort-binary.cpp` | 3.9/3.10 | 排序族（sort/stable_sort/partial_sort/nth_element）+ 二分族（lower_bound 家族）+ 双指针/滑动窗口 | 已验证（Apple clang 21.0.0） |

> 本阶段刻意与「裸刷题」错开：ex01/ex02 讲的是「刷题题面里不出现、但工程里决定结构生死的容器行为」（扩容、rehash、失效规则）；ex03/ex04/ex05/ex06 是把 LRU、并查集、Trie、图算法、排序二分当成**要带复杂度标注与边界测试的组件**写，而不是一次性的题解。

## 统一编译运行命令

```bash
# 在 examples/ 目录内执行（产物一律输出到 /tmp）：
clang++ -std=c++20 -Wall -Wextra ex01-stl-selection.cpp -o /tmp/ph21-ex01 && /tmp/ph21-ex01
# 其余示例把 ex01-stl-selection / /tmp/ph21-ex01 替换为下表对应文件名与输出名即可。
```

## 示例 1：线性结构工程选型（ex01-stl-selection.cpp）

对应主文档 3.1 与 roadmap 学习内容「数组、链表、栈、队列」。教学点：① vector 的 capacity 随 push_back 跳跃式翻倍（本机 libc++ 实测输出 1→2→4→8），`reserve` 预分配可消除扩容搬移；② deque 头尾 O(1) 是「要 push_front 时」从 vector 换 deque 的信号；③ list 的 splice/迭代器插入 O(1) 是它唯一不可替代的场景（LRU 组合，见 ex03）；④ `queue`/`stack` 是适配器不是独立结构，BFS/DFS 直接使用。

## 示例 2：哈希表工程真相（ex02-hashmap-truth.cpp）

对应主文档 3.2 与 roadmap 学习内容「哈希表」。本机 libc++ 实测输出：

```text
reserve(64): bucket_count 64 -> 64 (load 0.625)   ← reserve 后插入 40 个元素不 rehash
no reserve: bucket_count 0 -> 1597 (load 0.626)   ← 不 reserve 则反复 rehash 到足够桶数
```

教学点：① `max_load_factor` 默认 1.0，元素数越过阈值触发 rehash——**迭代器全失效但元素引用仍有效**（链式哈希的节点不搬家）；② `reserve(n)` 让 n 个元素不触发 rehash，是「知道量级就先分桶」的工程动作；③ `operator[]`（默认构造插入）/`insert_or_assign`（覆盖）/`try_emplace`（不覆盖、不移动实参）三种语义要按场景挑；④ `std::hash` 没给 `pair<int,int>` 做特化，网格/复合键必须自定义 hash（教学实现：两个哈希错位异或）。

## 示例 3：LRU Cache 组合实现（ex03-lru-cache.cpp）

对应主文档 3.8 与 roadmap 练习「LRU Cache」。标准工程答案 = `std::list`（记录访问顺序，头=最近，尾=最久）+ `std::unordered_map<Key, list::iterator>`（按键 O(1) 定位）。get/put 均摊 O(1)。教学点：① **list 的「增删不使其他迭代器失效」是组合成立的根**——map 里存 list 迭代器才能安全长期持有；② get 命中也要 `splice` 提前，漏掉就是「LRU 退化成 FIFO」；③ `cap=0` 必须显式处理（put 直接丢弃）；④ 淘汰顺序「先删 map 索引再 pop list 节点」，顺序反了会在 list 节点销毁后仍被 map 引用。

## 示例 4：并查集与 Trie（ex04-unionfind-trie.cpp）

对应主文档 3.6/3.7。两个「STL 没有、必须手写」的结构：

- **并查集**：`parent_` + `size_` 两个 vector 就是整棵树——「数组即结构」。路径压缩（find 两遍：先找根再沿途压平）+ 按大小合并（小树挂大树），均摊 O(α(n))。实测断言：链路 0-1-4-5 联通、与 2-3 分离、合并后全联通。
- **Trie**：26 叉指针树，但子节点所有权用 `std::array<std::unique_ptr<node>, 26>` 持有——**析构自动递归释放，无裸 new/delete（R.11）**。插入/查找 O(词长)，`starts_with` 前缀查询是哈希表做不到的。教学约定：输入限定小写 a-z（代码注释说明），大字符集场景改用 `unordered_map<char, unique_ptr>`。

## 示例 5：图的遍历与最短路径（ex05-graph-algos.cpp）

对应主文档 3.5/3.12 与 roadmap 学习内容「图、BFS、DFS、Dijkstra」。图结构是 `vector<vector<pair<int,int>>>` 邻接表。教学点：① BFS **入队时**标记 visited（出队时标记会重复入队）、无权最短路用距离数组 -1 表不可达；② Dijkstra = 最小堆（`std::greater<>`）+ **懒删除**（弹出时 `d != dist[u]` 即过期条目直接丢）——避免手写 decrease-key；③ `pair` 必须 `{距离, 节点}` 顺序才能按距离排序；④ 距离用 `long long` 防 int 溢出；⑤ 平行边（严格 `<` 天然免疫）、自环、孤立点（保持 INF/-1）都在断言里覆盖。DFS 给出递归版并在注释里说明深图要换显式栈（主文档 3.11 栈溢出风险）。**本示例用 Apple clang 21.0.0 与 Homebrew clang 21.1.8 双编译器实测通过**。

## 示例 6：排序族与二分族（ex06-sort-binary.cpp）

对应主文档 3.9/3.10 与 roadmap 学习内容「排序、二分、双指针、滑动窗口」。教学点：① `std::sort`（内省排序，不稳定）默认；要稳定用 `stable_sort`——实测断言同分 `(90,1)` 在 `(90,3)` 前；② `partial_sort` 只排前 k、`nth_element` 只把第 k 位就位（找中位数别先全排序）；③ `lower_bound`/`upper_bound`/`equal_range` 组成 `[lo, hi)` 区间语义，`lower_bound(8)` 越过全部元素返回 `end()`；④ 双指针左右夹逼找两数之和 O(n)；⑤ 滑动窗口「和 ≤ S 最长子数组」（该例最长为 4：`{1,2,1,1}`）+ 单调队列求滑动窗口最大值（deque 存下标，O(n)）。

## 验证状态汇总

| 示例 | 工具链 | 状态 |
|------|--------|------|
| ex01-stl-selection | Apple clang 21.0.0 | 已验证（零警告、断言全绿、退出码 0） |
| ex02-hashmap-truth | Apple clang 21.0.0 | 已验证（含 libc++ 桶数/负载实测输出） |
| ex03-lru-cache | Apple clang 21.0.0 | 已验证 |
| ex04-unionfind-trie | Apple clang 21.0.0 | 已验证 |
| ex05-graph-algos | Apple clang 21.0.0 + Homebrew clang 21.1.8 | 已验证（双编译器交叉核对） |
| ex06-sort-binary | Apple clang 21.0.0 | 已验证 |
