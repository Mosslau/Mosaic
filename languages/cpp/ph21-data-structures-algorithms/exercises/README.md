# ph21 C++ 数据结构与算法阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。题目与参考实现分离：本 README 只出题，答案在 `sol-*` 文件里，做完再看。

完成顺序建议：按 1~4 顺序完成。练习 1~4 与 roadmap §21「练习」小节一一对应（LRU Cache / 任务调度器 / 查询计划树 demo / 内存池）。练习里卡住先看 examples/ 的手法：LRU 组合看 `ex03`、堆/priority_queue 看 `ex06`、树递归看 `ex04` 的 Trie、池的「数组即结构」思路看 `ex04` 的并查集与主文档 4.1（vector 的容量 vs 大小）。**每题参考实现均已实测**（验证命令与状态见文末汇总）。

> ⚠️ 通用验收基线：`clang++ -std=c++20 -Wall -Wextra` 编译零警告、运行断言全绿、退出码 0；手写结构必须带复杂度注释；产物输出到 /tmp（仓库不落二进制）。

## 练习 1：LRU Cache（★★）

- **目标**：实现一个 LRU 缓存，并把「访问顺序」暴露成可断言接口，证明自己写的是 LRU 不是 FIFO
- **要求**：
    - 模板类 `resizable_lru<K, V>`：`get(key)`、`put(key, value)`、`set_capacity(n)`（动态改容量，**变小要立即淘汰**到符合新容量）、`keys_in_recent_order()`（头=最近 → 尾=最久）
    - `get` 命中要改变访问顺序（命中即最近）；`get` 未命中返回无值且不改顺序
    - 显式处理 `capacity == 0`（put 不保留任何东西），且支持从 0 调大后正常工作
    - 不允许抄 examples/ex03 的测试序列——自拟一组能证明「淘汰的是最久未用、而非最老插入」的序列
- **验收**：容量 3 下 put 1/2/3 后顺序为 [3,2,1]；get(2) 后顺序 [2,3,1]；put(4) 淘汰 1；`set_capacity(2)` 后立即只剩 2 个且淘汰的是尾（最久）者；能口头说清「map 里为什么存 list 迭代器」「淘汰时为什么要先删索引再删节点」
- **提示**：list 的 splice 与「增删不使其他迭代器失效」是组合的根；测试顺序快照比只测 contains 更能抓「漏了 get 命中提前」的 bug（参考实现 `sol-01-resizable-lru.cpp`）

## 练习 2：任务调度器（★★）

- **目标**：用 `std::priority_queue` 实现单核抢占式最短剩余时间优先（SRTF）调度模拟，输出每个任务的完成时间
- **要求**：
    - 输入：`(id, release_time, burst)` 任务表；输出：`finish[id]`（完成时刻）
    - 最小堆存「{剩余时长, id}」；剩余相同时按 id 小者优先（**确定性 tie-break**，否则无法断言）
    - 抢占语义：运行中若有「剩余更短」的新任务就绪，下个时间片换它
    - 边界必须覆盖：空任务集、任务之间有 CPU 空闲期（要跳时间，别一格一格空转）
- **验收**：对 `{0,0,3},{1,1,2},{2,2,1},{3,4,5}`（id, release, burst）断言完成时间为 A=3、B=6、C=4、D=11（A 在 t=3 先完成，C 比 B 更短因此先于 B 完成）；另造一条带真实抢占的用例（长任务运行中短任务到达）断言两个完成时间
- **提示**：事件循环每个时间片「先释放已就绪 → 再取堆顶跑 1 片」；空闲期找「下一个最小 release」直接跳；priority_queue 用 `std::greater<>` 就是最小堆（主文档 3.4/3.12）（参考实现 `sol-02-task-scheduler.cpp`）

## 练习 3：查询计划树 demo（★★★）

- **目标**：用「运算符树 + 递归」建模查询计划：后序遍历自底向上估行数、先序遍历打印计划、递归统计结构指标——roadmap 第 22 节（目录待建）的查询/存储引擎会反复用到这棵「树」
- **要求**：
    - `plan_node`：`op_kind`（scan/filter/join）+ 名字 + 子节点（`unique_ptr` 持有，RAII）；scan 叶子存源行数
    - 估算规则（写进注释）：filter 输出 = 唯一子估算 / 10；join 输出 = 各子估算之积；scan 输出 = 自身行数
    - 实现：`estimate_rows()`（后序递归）、`print()`（先序缩进）、`node_count()`/`leaf_count()`/`max_depth()`（递归统计）
    - **结构校验**：filter 子节点数 ≠ 1、join 子节点数 < 2 时必须抛 `std::logic_error`，不许静默算错
- **验收**：对 `join( filter(scan users, 1000), scan orders, 5000 )` 断言 root 估算 = 500000、节点数 4、叶子数 2、最大深度 3；并断言一条非法树（无子的 filter/join）确实抛异常；能说出「为什么用后序估行数、先序打计划」
- **提示**：递归先写「叶子基线」（children 空怎么办）再写内部节点；估算沿孩子→父方向流（后序），打印沿父→孩子（先序）；行数用 double 便于教学除 10（参考实现 `sol-03-query-plan-tree.cpp`）

## 练习 4：内存池（★★★）

- **目标**：实现定长块内存池——free-list 结构 + chunk 化增长，alloc/free O(1)，体会「数组/池即结构」与 RAII 的配合
- **要求**：
    - `fixed_block_pool(block_size, blocks_per_chunk, grow)`：管理**字节块**（不构造对象），`alloc()` 返回块索引、`free_block(idx)` 归还、`at(idx)` 给非拥有 `unsigned char*`
    - 空闲块用**栈式 free-list**：先释放的后复用（LIFO）；`grow=false` 是有界池（耗尽 `alloc()` 返回空值），`grow=true` 时按 chunk 追加 slab
    - chunk 内存用 `std::unique_ptr<char[]>` 持有，**全程无裸 new/delete**（R.11）；池自身 Rule of Zero
    - 边界：`block_size=0` 构造抛 `invalid_argument`；越界索引抛 `out_of_range`；不允许 double-free 的用例（注释说明为什么真实池必须防）
- **验收**：有界池（8 字节 × 4 块）连续分配 4 次成功、第 5 次得空值；释放 b1、b0 后下一次分配拿回 b0 的同一块索引（LIFO）；增长池跨 chunk 分配的指针互不重叠且第三块触发新 slab；两条非法输入断言通过
- **提示**：free-list 存「块索引」而不是裸指针最干净（避免指针→索引导航）；索引→地址 = `chunk = idx / per_chunk`、`offset = (idx % per_chunk) * block_size`；把「只管理块、不管理对象生命周期」写进注释，衔接 ph22 的 arena/内存池方向（参考实现 `sol-04-memory-pool.cpp`）

## 验证状态汇总

| 练习 | 参考实现 | 工具链 | 状态 |
|------|---------|--------|------|
| 1 LRU Cache | `sol-01-resizable-lru.cpp` | Apple clang 21.0.0 | 已验证（`clang++ -std=c++20 -Wall -Wextra sol-01-resizable-lru.cpp -o /tmp/ph21-sol01 && /tmp/ph21-sol01`，零警告、断言全绿） |
| 2 任务调度器 | `sol-02-task-scheduler.cpp` | Apple clang 21.0.0 | 已验证（同上命令换文件名，断言全绿） |
| 3 查询计划树 | `sol-03-query-plan-tree.cpp` | Apple clang 21.0.0 | 已验证（同上命令换文件名，断言全绿） |
| 4 内存池 | `sol-04-memory-pool.cpp` | Apple clang 21.0.0 | 已验证（同上命令换文件名，断言全绿） |
