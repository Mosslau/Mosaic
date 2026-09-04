# ph21 阶段项目：SkipList MemTable（有序内存 KV 结构）

对应 roadmap §21「推荐项目」之一，**落地选择「SkipList MemTable」**：roadmap §21 推荐了四个项目——LRU 缓存库（已由 examples/ex03 + 练习 1 覆盖）、Bloom Filter（结构认知见主文档 3.2/5 节，生产落地属 ph22 的 SSTable 过滤，roadmap 第 22 节，目录待建）、HNSW toy implementation（属 ph23 向量检索，roadmap 第 23 节，目录待建）、SkipList MemTable（本 project）。**边界声明：本项目交付的是「内存有序 KV 结构」——把 Skip List 写成 RAII 的生产级组件并证明它正确；不涉及把 MemTable 接 WAL/SSTable/Compaction（那是 ph22 存储引擎与数据库内核专项，roadmap 第 22 节，目录待建）**——但结构的接口（put/get/erase + 有序扫描）就是按「ph22 的 MemTable 读面」设计的，flush 方向已在 demo 第 3 节演示。

## 需求

手写一个无 STL 等价物的有序键值结构：**Skip List**（William Pugh 1990 的概率平衡有序结构），包装成 MemTable 语义的内存 KV 存储，并用「与 std::map 随机对拍 + 内部不变量校验」证明正确性。为什么选它而不选 `std::map`（红黑树）：MemTable 在生产存储引擎里选 Skip List 是因为它**层结构对并发友好**（可做无锁并发改造，RocksDB/LevelDB 的 MemTable 即 skip-list）且写路径简单——ph21 先把单线程正确版本做扎实，ph22 的并发层才有地基可加。

## 功能清单

- [x] `skip_list.h`：模板 `skip_list_map<K, V, Compare>`——`put`（存在则更新返回 false）/`erase`/`find_value`（返回非拥有指针，erase 前有效）/`contains`/`size`/`lower_bound` + `begin()/end()` 有序扫描迭代器
- [x] **RAII 内存模型**：level-0 真链由 `unique_ptr` 持有（插入/删除/析构全自动回收，无裸 new/delete，R.11）；level≥1 的 skip 指针是 raw 非拥有快捷指针；拷贝禁用、移动默认（C.21 注释说明）
- [x] **概率平衡**：p=1/2 逐层提升、16 层上限；期望 O(log n)；内部随机种子可注入（确定性测试的前提）
- [x] **复杂度与边界标注**：头文件注释写明各操作期望复杂度；`check_invariants()` 校验全部内部不变量（严格升序、层间子序列一致、fwd[0]==next、计数==size）
- [x] `memtable_demo.cpp` 驱动三层验证：① MemTable 基础语义 + 边界（空表扫描、lower_bound 越界、erase 不存在、put 更新）；② **4000 次随机操作与 std::map 逐点对拍**（插入/删除/查询结果一致 + 定期全量有序扫描一致 + 不变量全绿）；③ flush 读面演示（升序读出 = SSTable 有序输入，ph22 预告兑现）

## 验收标准

- [ ] `make clean && make test` 退出码 0，输出含 `[1] memtable basic semantics passed`、`[2] random replay vs std::map: 4000 ops, all checkpoints passed`、`[3] flush-read shape`、末行 `ph21-project-memtable OK`（已验证）
- [ ] Apple clang 21.0.0 与 Homebrew clang 21.1.8 双编译器 `-std=c++20 -Wall -Wextra` 零警告、断言全绿（`make cross`，已验证）
- [ ] 能口头说清：Skip List 为什么是「概率平衡」、p=1/2 时期望高度 2、`find_value` 返回的指针为什么在 erase 前有效（节点不搬家）、`unique_ptr` 链如何让析构/删除自动回收、为什么拷贝要禁用
- [ ] 能画出项目与 ph22 的接缝：本项目的 `put/get/erase` = MemTable 写读路径，`begin()/end() + lower_bound` 有序迭代 = 向 SSTable flush 的读面——接 WAL 的 replay 与 Compaction 是 ph22 的事（roadmap 第 22 节，目录待建）

## 扩展方向（与 ph22/ph23 的关系）

- **接 WAL**（ph22 起点）：MemTable 的每次 put/erase 前先写 append-only WAL（记录 + checksum），崩溃后重放重建 MemTable——需要给结构加「重放构造」接口，本项目的有序语义让重放天然按序
- **SSTable flush**：把有序扫描的结果按固定 block 写入不可变有序文件，并维护 index——本项目 `begin()/end()` 迭代器就是 flush 循环的骨架
- **Bloom Filter**：给 SSTable 的点查加「可能不存在」过滤（roadmap 第 22 节学习内容）——用位数组 + 两个哈希，避免无效磁盘读
- **并发改造**：单节点锁 vs 无锁 skip-list（Pugh 1992 的并发算法是 RocksDB memtable 无锁化的基础）——本项目把单线程正确性做扎实后，ph22/并发专题再加锁才有对照基准
- **arena/内存池化**：练习 4 的固定块池 + `std::pmr`（或自定义分配器）把节点分配摊平成 slab——ph22 Buffer Pool / 写入路径的标配
- **对比 std::map 的实测**：用 `std::chrono` 对相同操作集计时（Per.6：先测再说），体验「红黑树 vs skip-list 常数因子」——属于 ph18 性能优化思路在本结构的应用
- 若选做另三个 roadmap §21 推荐项目：LRU 缓存库 = examples/ex03 + 练习 1 的收口形态；Bloom Filter 见 ph22；HNSW toy implementation 正式归 ph23（roadmap 第 23 节，目录待建）

## 验证环境与状态

- 实测环境：macOS arm64，Apple clang 21.0.0（`/usr/bin/clang++`）+ Homebrew clang 21.1.8（`/opt/homebrew/opt/llvm/bin/clang++`），libc++，make 3.81+
- 构建：`make`（等价单行：`clang++ -std=c++20 -Wall -Wextra -I. memtable_demo.cpp -o /tmp/ph21-project-memtable`）
- 测试：`make clean && make test`（验收入口）；交叉核对：`make cross`；清理：`make clean`（产物一律在 /tmp，仓库不落二进制）
- 验证状态：**已验证**（`make clean && make test` 与 `make cross` 均退出码 0：双编译器编译零警告、MemTable 语义与边界断言全绿、4000 次随机操作与 std::map 逐点对拍一致、内部不变量全绿）
