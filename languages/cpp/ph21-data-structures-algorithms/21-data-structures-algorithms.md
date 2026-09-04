# C++ 数据结构与算法阶段

> 面向「面试 / 工程建模 / 性能优化」三大方向：从 roadmap ph20 的跨语言边界回到「单个进程内用什么结构组织数据」的本源问题——本阶段不裸刷题，而是把每个结构都过一遍同一套工程三问：**STL 有没有现成实现？有则用哪一个？没有则手写时要注意什么**——为 ph22 存储引擎（SkipList MemTable / LRU / Bloom Filter 没有 STL 等价物）与 ph23 向量检索（HNSW 无 STL 等价物）备好结构地基。

## 1. 概述

本阶段是学习路线的第 21 步（roadmap ph21 目标：具备面试、工程建模和性能优化所需的数据结构基础）。ph04（STL）教你「这些容器怎么用」，ph20 告诉你「容器不出二进制边界」——本阶段回答第三个问题：**面对一个真实问题，凭什么选这种结构、为什么另一种不行、复杂度上限由谁决定**。它既补足 ph04 没讲的「每个容器内部的成本结构」，也把 ph18（性能优化）的 cache locality、ph17 的工程权衡落到数据结构决策上。

| 核心维度 | 覆盖内容 |
|---------|---------|
| 结构 × STL 映射 | 每个结构过「三问」：STL 现成？用哪个？手写注意什么？决策总表见下 |
| 线性结构工程选型 | `std::array` / `vector` / `list` / `deque` / `queue` / `stack` 何时用、为何默认 vector |
| 哈希表工程真相 | `std::unordered_map` 的 bucket/load factor/rehash/自定义 hash；开放寻址 vs 链地址 |
| 树与平衡树 | 二叉树遍历、BST、`std::map`/`set` 红黑树、为何工程里几乎不手写红黑树 |
| 堆与优先队列 | `std::priority_queue` 与 heap 算法、自定义比较器、top-k 与调度 |
| 图与图算法 | 邻接表表示；BFS/DFS/Dijkstra 用 STL 组合实现 + 边界输入处理 |
| 手写结构三件套 | 并查集、Trie、LRU Cache——STL 无直接等价物时的手写范式与 RAII |
| 排序与二分 | `std::sort` 内省排序、`stable_sort`、`partial_sort`/`nth_element`、`lower_bound` 家族 |
| 算法模式 | 双指针/滑动窗口；递归/回溯/DP/贪心用 STL 承载时的写法与边界条件 |
| 复杂度心智 | 时间/空间复杂度、摊还分析、迭代器失效、cache 行为、确定性测试 |

**「结构 × STL」三问总表**——本阶段每讲一个结构都回到这张表：

| 结构 | STL 现成？ | 工程推荐 | 何时必须手写（注意什么） |
|------|-----------|---------|------------------------|
| 动态数组 | ✅ `std::vector` | 默认容器，几乎永远先想它 | 几乎不手写（除非要定制分配器/内存池，ph22 Buffer Pool 会用到 arena 思想） |
| 链表 | ✅ `std::list` / `forward_list` | 少用；只有 O(1) 中间删除 + 迭代器稳定是硬需求才选 | LRU 用 `list`+`unordered_map` 组合；要自旋锁并发链表才手写 |
| 栈/队列 | ✅ `std::stack` / `queue` / `deque` | 容器适配器直接上 | 手写单调栈/单调队列是对算法的练习，不是对容器的替代 |
| 哈希表 | ✅ `std::unordered_map` | 默认「快速按键查找」答案 | 高性能/内存敏感时社区用开放寻址（`dense_hash_map`）；Bloom Filter（ph22 用）借「k 个位哈希」思想 |
| 平衡树 | ✅ `std::map`/`set`（红黑树） | 需要有序遍历/范围查询时选 | 几乎不手写；ph22 的 SkipList MemTable 是「要并发友好才弃红黑树」的正面案例 |
| 堆 | ✅ `std::priority_queue` + heap 算法 | 调度、top-k、Dijkstra | 需要 decrease-key 时自己实现（或用懒删除技巧，见 3.12） |
| 并查集 | ❌ 无 | — | 手写：路径压缩 + 按秩合并，代码极短（见 3.6） |
| Trie | ❌ 无 | — | 手写：注意节点所有权用 `unique_ptr`，字符集决定子节点容器（见 3.7） |
| LRU Cache | ❌ 无（需 `list`+`unordered_map` 组合） | 组合即标准答案 | 手写时防迭代器失效、cap=0 边界（见 3.8/ex03/练习 1） |
| SkipList / Bloom Filter | ❌ 无 | — | ph22 存储引擎要用的生产结构：ph21 project 落地 SkipList MemTable 原型，Bloom Filter 见 [ph22 存储引擎与数据库内核专项专项](../ph22-storage-engine-db-kernel/22-storage-engine-db-kernel.md) |
| HNSW | ❌ 无 | — | 属于 [ph23 向量检索与 AI 推理引擎方向 C++ 阶段](../ph23-vector-search-ai-inference/23-vector-search-ai-inference.md)，本阶段只提不展开 |

这个阶段只涉及**在内存中组织和操作数据：线性/哈希/树/堆/图结构、并查集/Trie/LRU 的手写、排序二分与算法模式，以及全部结构的复杂度分析与 STL 工程选型**，**不涉及把结构接进持久化与存储内核（把 SkipList MemTable 接 WAL/SSTable/Compaction、给 SSTable 加 Bloom Filter、Buffer Pool 用 LRU/Clock 管脏页 pin/unpin 是 [ph22 存储引擎与数据库内核专项](../ph22-storage-engine-db-kernel/22-storage-engine-db-kernel.md)的内容——本阶段所有结构都「脱离磁盘」演示）、不涉及向量检索与 AI 推理引擎方向（HNSW 的工业级实现、图库接入、IVF/PQ、SIMD 距离与 Faiss 体系是 [ph23 向量检索与 AI 推理引擎方向 C++ 阶段](../ph23-vector-search-ai-inference/23-vector-search-ai-inference.md)的内容——roadmap §21 推荐项目里的「HNSW toy implementation」本阶段不做，它会被 ph23 作为入门级 demo 吸收；roadmap §21 推荐项目里的「Bloom Filter」「LRU 缓存库」同理，前者本阶段给出结构认知、落地留给 ph22，后者以 examples/ex03 + 练习 1 形式落在本阶段）、不涉及 STL 容器 API 的逐个教学（那是 ph04 的内容，本阶段引用结论不再展开）**。同时本阶段不重复 ph20 的 C ABI 层：所有结构与示例都是纯 C++ 进程内形态；若未来想把这些结构暴露给 Python/Rust 生态，走的正是 ph20 学的 C 包装层路线。

## 2. 来源与演变

数据结构的历史不是一条直线，而是两条线在 C++ 里汇合：**线一，STL 容器库本身的演化——把「用什么结构」从「自己手写」变成「声明式选择」；线二，结构本身的发明史——LRU/Bloom/SkipList/HNSW 各自为解决一个具体性能问题而生**。设计哲学一句话：**数据结构是「对访问模式的显式建模」——数组假设顺序访问、哈希假设按键随机访问、树假设有序范围访问；选型错误不是慢一点，而是复杂度量级错一档**。

线一的源头是 Alexander Stepanov 与 David Musser 在 1980 年代提出的泛型编程。1994 年 Stepanov 在 SGI 完成 STL 参考实现，核心思想「容器（数据）+ 迭代器（指针抽象）+ 算法（操作）三分离」至今仍是 C++ 标准库的骨架；C++98 把它收进标准后，编译器厂商各自实现——**libstdc++（GCC）**直接由 SGI STL 演进而来（早期代码里有 SGI 版权注释），**MSVC 的 STL** 来自 Dinkumware 授权（2016 年微软将其开源为「MSVC STL」由 Stephan T. Lavavej 维护），**libc++（LLVM）**是 Howard Hinnant 2010 年起为 C++11 全新写的实现（它的 `std::string` SSO 布局、`unordered_map` 的 node 形态与本阶段讨论的容器行为直接相关）。三个实现行为略有差异——这正是 ph11（可移植性）的素材，本阶段只在涉及「容量翻倍策略 / rehash 时机」时点名差异。

线二按时间看：**LRU（Least Recently Used）**思想来自 1960 年代操作系统页置换研究（Belady 的最优算法论证了「未来不可知，过去的最近性是最好的代理」），工程形态「哈希表 O(1) 定位 + 链表 O(1) 调整顺序」在缓存（CPU cache 行、页缓存、Buffer Pool）里是标准件；**Bloom Filter** 是 Burton Bloom 1970 年论文「Space/Time Trade-offs in Hash Coding with Allowable Errors」提出的概率结构——用 k 个哈希位标记存在性，换「绝不漏报、少量误报」，早年在拼写检查词典里省内存，后来成了数据库 LSM 减少无效磁盘读的标准件；**Skip List** 是 William Pugh 1990 年在 CACM 发表的「Skip Lists: A Probabilistic Alternative to Balanced Trees」——用「多层有序链表 + 随机提升层数」把平衡树的查找变成概率意义的 O(log n)，写起来远比红黑树简单、且天然适合并发改造，LevelDB/RocksDB 的 MemTable 与 Redis 的有序集合都选它；**HNSW（Hierarchical Navigable Small World）**是 Malkov & Yashunin 2016 年提出（论文 2018 年正式发表）的近似最近邻图索引——把 NSW 小世界图叠成多层「上粗下细」的金字塔，从高层大跨度起跳、逐层精化，工程上被 FAISS / Milvus 等向量库采用。

**「算法题文化」与「工程结构」的分野**也必须讲清：刷题（LeetCode/ICPC）的场景是「输入规模明确、一次运行、单线程、数据结构当纯算法组件用、容器实现被 API 抽象掉」；工程场景则是「输入是流式的、结构要活在整个进程生命周期里、内存布局影响 cache 与分配次数、迭代器与引用要跨函数存活、可能需要多线程访问、还要考虑 RAII 与异常安全」。所以同一道 LRU 题：刷题答案直接 `std::list` + `unordered_map` 就完了；工程答案要多问——容量是静态还是动态？get 要不要线程安全？节点内存能不能用 arena 摊平？——ph22 的 Buffer Pool 就是在 LRU 上加 pin/unpin 与脏页位。**本阶段刻意把两种视角并排讲**：结构选型与复杂度是刷题给的，容器行为、生命周期与内存布局是工程补的。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| LRU 页置换思想（Belady 等） | 1960s | 操作系统换页算法的理论基础；「最近最少使用」成为缓存标准语义 |
| Bloom Filter（Burton Bloom） | 1970 | 概率性集合成员查询；可调误报率，空间换时间 |
| SGI STL（Stepanov） | 1994 | 容器/迭代器/算法三分离的参考实现；现代 STL 的源头 |
| Skip List（William Pugh） | 1990 | 概率平衡的替代：LevelDB/RocksDB MemTable、Redis zset 的数据结构 |
| C++98 | 1998 | STL 进标准；`std::vector`/`map`/`list` 等成为语言标配 |
| TR1（2005）→ C++11 | 2005~2011 | `unordered_map`/`set`（链式哈希）从 TR1 进标准；move 语义使 vector 扩容可转移元素 |
| libc++（LLVM） | 2010 | 为 C++11 全新实现的标准库；其容器布局（SSO、node 形态）成 libstdc++ 对照面 |
| libstdc++（GCC）/ MSVC STL | 持续 | SGI STL 后继 vs Dinkumware 授权（2016 开源）；三实现行为差异是 ph11 素材 |
| C++14/17/20 | 2014~2020 | 透明异质查找（C++14）、node handle（C++17）、ranges/span（C++20）等容器工程化补丁 |
| HNSW（Malkov & Yashunin） | 2016 | 分层小世界图近似最近邻；FAISS/Milvus 向量索引的主力结构 |
| C++23（展望） | 2023 | `flat_map`/`flat_set`（有序 + 连续存储）、unordered 异质查找——属于 roadmap §11 标准演进 |

本文示例以 **C++20** 为基线（roadmap §6 现代 C++ 之后、range/span 已可用；决定本阶段代码的语法面与标准库形态），验证工具链为 **Apple clang 21.0.0**（`/usr/bin/clang++`，默认 PATH）+ **Homebrew clang 21.1.8**（`/opt/homebrew/opt/llvm/bin/clang++`，交叉编译核对），macOS arm64 + libc++。**本阶段全部代码均为纯 C++（无第三方依赖），已逐个在 Apple clang 21.0.0 下 `-std=c++20 -Wall -Wextra` 编译运行验证**，示例/练习/项目文件头标注各自验证状态。数据结构的语法在 C++20 上是最稳定的部分——本阶段示例除少量 C++20 特性（`std::span`、ranges 头）外几乎全部可在 C++11 编译，读者换编译器时若报错优先检查是否误用 C++20-only API。

## 3. 语法与参数

> 本节代码块是**教学骨架**：聚焦单个主题裁剪。完整可运行文件见第 6 节与 [`examples/`](./examples/)，构建命令见 examples/README.md（全部已在本环境实测）。文档内嵌片段标注来源文件与验证状态。

### 3.1 线性结构工程选型：数组 / vector / list / deque / queue 何时用

所有线性结构的选型问题先回答一个默认项：**没有特殊理由就用 `std::vector`**——它是唯一的「连续内存 + O(1) 下标访问 + 摊还 O(1) 尾插」组合，cache 友好（Per.19：访问内存要有规律）且分配次数可控（reserve）。其它线性容器都是「你的访问模式让 vector 的某个操作变贵了」时的替代品：

```cpp
// examples/ex01-stl-selection.cpp —— 线性容器选型演示（节选）
// 验证环境：Apple clang 21.0.0（对应完整示例已实测；此处教学节选）
std::vector<int> v;
v.reserve(8);                    // 预先分配，避免反复扩容（4.1）
v.push_back(3); v.push_back(1);
v[0] = 2;                        // O(1) 下标访问：vector 的核心优势
// 尾插摊还 O(1)；头插/中间插是 O(n)——大量头插是改用 deque/list 的信号

std::deque<int> dq{1, 2, 3};
dq.push_front(0);                // deque：头尾都是 O(1)，连续内存是分块的
dq.pop_back();

std::queue<int> q;               // 容器适配器：默认 deque 做底层
q.push(10); q.push(20);          // BFS 的标准队列（3.12）
// std::stack 同理：默认 deque，LIFO
```

| 结构 | 底层形态 | 头/尾操作 | 随机访问 | 中间插入 | cache | 工程判断 |
|------|---------|----------|---------|---------|------|---------|
| `std::array` | 连续、栈上/内嵌 | 不支持（定长） | O(1) | 无 | 最好 | 编译期定长、不堆分配；优先于 C 数组（SL.con.1） |
| `std::vector` | 连续、堆 | 尾 O(1) 摊还 | O(1) | O(n) | 好 | **默认容器**；要频繁头插先想 deque |
| `std::deque` | 分块连续（map 中块） | 头尾均 O(1) | O(1) | O(n) | 中 | 双端队列语义；push_front 需要时 |
| `std::list` | 双向链表（每节点堆分配） | O(1) | O(n) | 拿到迭代器后 O(1) | 差 | 只有「迭代器稳定 + O(1) 删除」是硬需求才用（LRU，3.8） |
| `forward_list` | 单向链表 | 仅头 O(1) | O(n) | 拿到前驱后 O(1) | 差 | 最小内存链表；几乎不用 |
| `std::string` | 连续 + SSO | 尾 O(1) | O(1) | O(n) | 好 | 字符序列一律 string/string_view（SL.str.1/2） |

**工程判断的真相是「操作频率 × 复杂度」**：中间插入 O(n) 的 vector 在 n 很小时依旧比 list 快（cache + 单次分配 vs 每节点分配），所以「插入多就用 list」是刷题结论，工程上要先问 n 的量级。queue/stack 作为适配器不自己分配内存，BFS 用 `queue`、表达式求值/DFS 非递归用 `stack`，直接使用即可——它们的正确用法就是本阶段的边界条件教学（空队列 front 是 UB，先判 empty）。

> 本阶段只用 C++20 的标准容器；**自定义分配器（arena/内存池）与对容器做内存布局定制属于 [ph22 存储引擎与数据库内核专项阶段](../ph22-storage-engine-db-kernel/22-storage-engine-db-kernel.md)**，练习 4（内存池）只是提前用结构视角碰一次 free-list，不展开 allocator 模板参数。

### 3.2 哈希表：std::unordered_map 的工程真相

`std::unordered_map` 是 C++ 里「按键快速查找」的默认答案，但它的工程真相比 API 表面复杂：**它是「链式哈希」——一个 bucket 数组 + 每个 bucket 挂一条节点链**，元素本身是堆上独立节点。因此有两组行为必须内化：

- **rehash 时机**：元素数超过 `bucket_count() × max_load_factor()`（默认 max_load_factor 为 1.0）时触发 rehash——重新分配 bucket 数组、把每个元素重新挂链。**rehash 使所有迭代器失效，但元素节点的引用/指针保持有效**（节点没被移动）。这是与 `std::map`（节点永不被移动）最不同的地方。
- **预分配**：知道元素量级就 `reserve(n)`（等价于设置桶数使 n 个元素不触发 rehash），避免反复 rehash 的 O(n) 成本。

```cpp
// examples/ex02-hashmap-truth.cpp —— unordered_map 工程真相（节选）
// 验证环境：Apple clang 21.0.0（对应完整示例已实测；此处教学节选）
std::unordered_map<std::string, int> m;
m.reserve(1000);                     // 预分桶：装 ~1000 个元素不 rehash
m.max_load_factor(0.7f);             // 更早 rehash，换更短冲突链（空间换时间）
m["alice"] = 1;                      // operator[]：不存在则默认构造插入
m.insert_or_assign("alice", 2);      // 插入或覆盖（C++17）
m.try_emplace("bob", 3);             // 存在则不覆盖、不移动实参（C++17）

// 自定义 hash：STL 没给 pair<int,int> 提供 std::hash 特化，须自写
struct pair_hash {
    std::size_t operator()(const std::pair<int, int>& p) const {
        const std::size_t h1 = std::hash<int>{}(p.first);
        const std::size_t h2 = std::hash<int>{}(p.second);
        return h1 ^ (h2 << 1);       // 混合两个哈希，避免对称碰撞
    }
};
std::unordered_map<std::pair<int, int>, int, pair_hash> grid;
```

| 问题 | 答案 | 为什么 |
|------|------|--------|
| 默认查找复杂度 | O(1) 平均、O(n) 最坏 | 冲突退化成长链；拒绝服务攻击可故意制造（哈希洪水），工程上可用随机种子哈希缓解 |
| `max_load_factor` 调大 | 桶少链长，省内存、变慢 | rehash 阈值 = bucket × load factor；默认 1.0 是空间/时间折中 |
| 迭代顺序 | **无任何保证**，且 rehash 后全变 | 需要有序遍历/范围查询就别用哈希，用 `std::map`（3.3） |
| 自定义 key | 需要 `std::hash<T>` 特化或自定义 hash 仿函数 | STL 只内置整数/string/指针等；`pair`/`tuple`/自定义 struct 都得自己写（或手动合并字段） |
| 开放寻址 vs 链地址 | 标准库是链地址；开放寻址（元素连续放一个槽数组）在社区库（`dense_hash_map`） | 开放寻址 cache 更好、省节点开销，但删除要 tombstone、rehash 更贵——工程里追求极致性能时换它 |

哈希表是 ph22/ph23 的隐性地基：ph22 的 Bloom Filter 本质是「多个位哈希」、ph23 的向量量化要算哈希桶，但**真正的哈希表用法到此为止**——数据库的点查走的是有序结构（SkipList/B+Tree）+ Bloom 过滤，不是哈希表本身。**何时手写哈希表？几乎从不**——标准库链式实现覆盖 99% 场景，剩下的性能敏感场景换社区开放寻址实现，而不是自己造轮子。

### 3.3 树：二叉树 / 平衡树 / std::map 红黑树

树的工程选型有一条总原则：**「树」作为结构体手写只在两种场合有意义——(a) 结构本身是算法的对象（二叉树遍历、BST 证明题、练习 3 的查询计划树）；(b) STL 没有等价物（Trie，3.7）。要「有序键值容器」直接 `std::map`/`set`，它们的实现是红黑树，你不需要、也不应该手写**。

```cpp
// 教学骨架片段（无对应独立示例文件）：二叉树是递归定义的
struct tree_node {                   // 教学用的裸指针 + 递归（RAII 见 3.7 Trie）
    int value;
    tree_node* left;
    tree_node* right;
};
// std::map 是红黑树：有序迭代、O(log n) 查找/插入/删除
std::map<int, std::string> m{{1, "one"}, {3, "three"}, {5, "five"}};
auto it = m.lower_bound(2);          // 第一个 key >= 2 → key 3（范围查询入口）
// lower_bound/upper_bound 的区间语义在数据库 range scan 里是骨架（ph22 的 Iterator）
for (auto it2 = m.lower_bound(2); it2 != m.end(); ++it2) {
    // 打印 3:three 5:five —— 有序范围扫描
}
```

**平衡树 vs 哈希表的选择**是 3.2/3.3 交汇的工程判断点：

| 需求 | 选 std::map（红黑树） | 选 unordered_map（链式哈希） |
|------|----------------------|------------------------------|
| 按键遍历有序 / 范围查询 | ✅ O(log n) 定位 + 顺序遍历 | ❌ 无顺序 |
| 找前驱/后继、lower_bound | ✅ | ❌ |
| 纯单点查找（无范围需求） | O(log n) | ✅ O(1) 平均 |
| 引用/指针稳定性 | ✅ 插入/删除不影响其他元素 | ⚠️ rehash 使迭代器失效（引用仍有效） |
| 每元素内存 | 高（3 指针 + 红黑位 + 节点头） | 中（节点 + 桶指针） |

`std::multimap`/`multiset` 允许重复键（`equal_range` 取区间）；`std::map` 的节点地址永不移动是它区别于 vector 的稳定性保证——工程里「结构活在整个进程生命周期、外部还持有指向元素的引用」时，`std::map` 比 vector 安全。红黑树本身的五条不变量与旋转细节本阶段不展开：**它是 ph12/ph04 已声明的「用 API 不需要懂实现细节」的教学点**，本阶段只需知道「有序 + O(log n) + 节点稳定」三条结论并会测它。

> 二叉树的遍历与递归模板（pre/in/post 序、层序）是练习 3「查询计划树 demo」与 3.11 递归思想的直接素材；**B+Tree（磁盘友好、扇出高）属于 [ph22 存储引擎与数据库内核专项阶段](../ph22-storage-engine-db-kernel/22-storage-engine-db-kernel.md)**——内存里红黑树、磁盘上 B+Tree 的分工正是 LSM 与 B+Tree 之争的背景。

### 3.4 堆与 priority_queue

`std::priority_queue` 是「堆」的默认答案：默认最大堆（`less<>`），`push`/`pop` O(log n)，`top` O(1)。它是容器适配器，底层默认 `vector`——堆是一棵「结构上完全二叉树、逻辑上满足堆序」的树，但实现上就活在 vector 里（下标 i 的孩子是 2i+1/2i+2）。roadmap §21 的示例正是它的用法：

```cpp
// 教学骨架片段（roadmap §21 示例）：priority_queue 最小盘——完整用法见 ex05 的 Dijkstra
// 与练习 2 的任务调度器；验证环境：Apple clang 21.0.0，已实测
std::priority_queue<int> max_heap;       // 默认：最大堆（roadmap §21 示例）
max_heap.push(10); max_heap.push(3); max_heap.push(7);
// top()=10，pop 顺序 10,7,3 —— 最大堆的弹出序即降序

std::priority_queue<int, std::vector<int>, std::greater<>> min_heap;  // 最小堆
// Dijkstra 用最小堆取「当前最近节点」（3.12）；注意 greater<> 空尖括号 = 透明比较器
```

| 场景 | 用什么 | 说明 |
|------|--------|------|
| 动态取最大/最小 | `priority_queue` | 默认最大堆；自定义类型要定义 `<` 或传比较器 |
| 取前 k 大（流式） | 最小堆容量 k | 新元素比堆顶大则替换：O(n log k)，工程标准答案 |
| 取前 k 大（一次性数组） | `std::partial_sort` 或 `nth_element` | 后者只保证第 k 位就位，O(n)；前者前 k 有序 |
| 排序 | `std::sort` | 别把 priority_queue 当排序用（3.9） |
| 需要 decrease-key | 无 STL 现成 | 见下：优先选懒删除技巧 |

**priority_queue 缺一个接口：decrease-key**（Dijkstra 里「发现更短路径后要把节点的键调小」）。工程上有两条路：① 手写二叉堆并在元素上记 index——能拿到真 O(log n) decrease-key，但要维护元素位置；② **懒删除**：直接再 push 一个 (新距离, 节点)，取出时若距离与节点当前记录不符则丢弃。② 是工程默认——代码简单且摊还仍是 O(log n)，只是堆里可能有冗余条目（内存略增）。手写结构本身属于「性能关键路径且需要真 decrease-key」时的最后手段。

堆在后续阶段是隐形的：ph22 的 Buffer Pool 淘汰、ph22 之后的 KV 合并（k-way merge，多路归并）都靠堆选「当前最小」，**ph21 把堆的三种打开方式（priority_queue/partial_sort/懒删除）练熟，多路归并只是「堆顶是哪个文件的最小值」**。

### 3.5 图与邻接表

图在 C++ 工程里几乎只用**邻接表**表示：`vector<vector<int>>`（无权、每个邻居一个整数）或 `vector<vector<pair<int, int>>>`（带权，邻居 + 边长）。为什么邻接表是默认：稀疏图（边远少于 n²）是绝大多数真实图的形态，邻接表空间 O(V+E)，矩阵 O(V²) 且遍历邻接是 O(V) 而非 O(degree)。

```cpp
// examples/ex05-graph-algos.cpp —— 邻接表构建（节选）
// 验证环境：Apple clang 21.0.0（对应完整示例已实测；此处教学节选）
struct graph {                        // 带权无向图
    int n;                            // 顶点数 0..n-1
    std::vector<std::vector<std::pair<int, int>>> adj;  // adj[u] = {(v, w), ...}

    explicit graph(int vertices) : n{vertices}, adj(static_cast<std::size_t>(vertices)) {}

    void add_edge(int u, int v, int w) {
        adj[static_cast<std::size_t>(u)].push_back({v, w});
        adj[static_cast<std::size_t>(v)].push_back({u, w});  // 无向：双向
    }
};
```

**图的三个工程注意点**：① 用邻接表要「谁引用谁」清楚——`vector<pair<...>>` 比 `list` 省内存快遍历，图的构建期插入、运行期只读，正好适配 vector；② 顶点编号从 0 开始、用 `std::size_t` 避免符号比较告警；③ 稠密图或「频繁问某两边是否相邻」才考虑矩阵/集合。图的完整遍历与最短路径（BFS/DFS/Dijkstra）统一放 3.12，因为它们的边界条件（孤立点、自环、负权、大图栈溢出）值得集中讲。

### 3.6 并查集（Union-Find / Disjoint Set）

并查集是「STL 没有、但代码极短、必须手写」的第一课。它维护一组不相交集合，支持两个操作：`find(x)`（x 属于哪个集合）与 `unite(x, y)`（合并两集合）。两个优化缺一不可：**路径压缩**（find 时把沿途节点直接挂到根）与**按秩/按大小合并**（小树挂大树）——合起来每次操作均摊 O(α(n))，α 是反阿克曼函数，可视为常数。

```cpp
// examples/ex04-unionfind-trie.cpp —— 并查集（节选）
// 验证环境：Apple clang 21.0.0（对应完整示例已实测；此处教学节选）
class union_find {
public:
    explicit union_find(int n) : parent_(static_cast<std::size_t>(n)),
                                 size_(static_cast<std::size_t>(n), 1) {
        for (int i = 0; i < n; ++i) parent_[static_cast<std::size_t>(i)] = i;
    }

    int find(int x) {                            // 路径压缩（迭代写法，防深递归）
        int root = x;
        while (parent_[static_cast<std::size_t>(root)] != root) {
            root = parent_[static_cast<std::size_t>(root)];
        }
        while (parent_[static_cast<std::size_t>(x)] != x) {   // 第二遍：沿途压平
            const int next = parent_[static_cast<std::size_t>(x)];
            parent_[static_cast<std::size_t>(x)] = root;
            x = next;
        }
        return root;
    }

    void unite(int a, int b) {                   // 按 size 合并：小树挂大树
        int ra = find(a);
        int rb = find(b);
        if (ra == rb) return;
        auto ua = static_cast<std::size_t>(ra);
        auto ub = static_cast<std::size_t>(rb);
        if (size_[ua] < size_[ub]) std::swap(ua, ub);
        parent_[ub] = static_cast<int>(ua);
        size_[ua] += size_[ub];
    }

private:
    std::vector<int> parent_;    // parent 数组即森林
    std::vector<int> size_;      // 仅根有效：集合大小
};
```

并查集的标准用途是「连通性」：无向图连通分量计数、网格中的岛屿合并、Kruskal 最小生成树的成环判断。它也是最典型的「数组即结构」示例——没有指针、没有节点分配，两个 vector 就装下整个结构；手写注意点是 find 的两段式路径压缩（或递归 + 但防深度）与按大小合并的顺序。练习题按「能说出均摊复杂度的来源」验收。

### 3.7 Trie（前缀树 / 字典树）

Trie 是第二个「STL 没有、必须手写」的结构：按字符串前缀组织字符路径，适合「前缀查询」「自动补全」「字典序批量」场景。工程与刷题的写法差别在**所有权**——刷题常裸 `new` 子节点，工程里节点必须 RAII：子节点用 `std::unique_ptr` 数组或容器持有，析构自动递归释放。

```cpp
// examples/ex04-unionfind-trie.cpp —— Trie（节选）
// 验证环境：Apple clang 21.0.0（对应完整示例已实测；此处教学节选）
class trie {
public:
    void insert(std::string_view word) {
        node* cur = &root_;
        for (const char ch : word) {
            const auto idx = static_cast<std::size_t>(ch - 'a');  // 教学假设：小写 a-z
            if (!cur->children[idx]) {
                cur->children[idx] = std::make_unique<node>();    // R.11：智能指针而非裸 new
            }
            cur = cur->children[idx].get();
        }
        cur->terminal = true;
    }

    bool search(std::string_view word) const {   // 精确匹配
        const node* cur = find_prefix(word);
        return cur != nullptr && cur->terminal;
    }

    bool starts_with(std::string_view prefix) const {
        return find_prefix(prefix) != nullptr;
    }

private:
    struct node {
        std::array<std::unique_ptr<node>, 26> children{};  // 26 叉；析构自动递归
        bool terminal{false};
    };
    node root_;
    // find_prefix 实现见完整示例：沿字符下行，中途缺子节点返回 nullptr
};
```

| 手写决策点 | 说明 |
|-----------|------|
| 子节点容器 | 定小字符集（26 字母）用固定数组最快；字符集大/稀疏用 `unordered_map<char, node*>`（又要自定义所有权） |
| 所有权 | `unique_ptr` 数组即可 RAII；注意递归析构深度 = 最长词长，超深词考虑显式栈析构 |
| 复杂度 | 插入/查找 O(词长)，与词条总数无关；空间 O(总字符数 × 每字符指针开销)——这就是它与哈希表的本质取舍 |
| 与哈希表分工 | 哈希表回答「词在不在」O(1)；Trie 回答「有共同前缀的都在哪」——前缀查询哈希表做不到 |

Trie 是「从手写结构到工程结构」的样板：结构简单、教学价值高、但工业上常被「排序后数组 + 二分前缀」或后缀自动机等替代——选它正是因为它是练习 3（查询计划树的节点遍历）之外最能练「指针 + 递归 + RAII」综合的教材。

### 3.8 LRU Cache：手写 + 工程考量

LRU 是「STL 没有直接等价物，但组合 STL 就是标准答案」的典型。它需要三个语义：O(1) 按键取到值、O(1) 知道「最近用过谁」、容量满时 O(1) 淘汰最久未用。STL 没有任何单一容器同时给这三个——组合是 `std::list`（记录访问顺序，头=最近）`+ std::unordered_map<Key, list::iterator>`（按键 O(1) 定位到列表节点）：

```cpp
// examples/ex03-lru-cache.cpp —— LRU：list + unordered_map 组合（节选）
// 验证环境：Apple clang 21.0.0（对应完整示例已实测；此处教学节选）
template <typename K, typename V>
class lru_cache {
public:
    explicit lru_cache(std::size_t capacity) : capacity_{capacity} {}

    std::optional<V> get(const K& key) {
        auto it = index_.find(key);
        if (it == index_.end()) return std::nullopt;
        order_.splice(order_.begin(), order_, it->second);  // 移到头部：list O(1)
        return it->second->second;                          // 命中即「最近用过」
    }

    void put(const K& key, V value) {
        auto it = index_.find(key);
        if (it != index_.end()) {                           // 已存在：更新值 + 提前
            it->second->second = std::move(value);
            order_.splice(order_.begin(), order_, it->second);
            return;
        }
        order_.emplace_front(key, std::move(value));        // 新节点放头
        index_[key] = order_.begin();
        if (order_.size() > capacity_) evict_tail();        // 超容淘汰尾部
    }

private:
    std::size_t capacity_;
    std::list<std::pair<K, V>> order_;          // 头=最近，尾=最久
    std::unordered_map<K, typename std::list<std::pair<K, V>>::iterator> index_;

    void evict_tail() {
        const K& victim = order_.back().first;
        index_.erase(victim);                   // 先删索引再删节点：顺序别反
        order_.pop_back();
    }
};
```

| 工程考量点 | 内容 |
|-----------|------|
| 复杂度标注 | get/put 均摊 O(1)：unordered_map O(1) + list splice/pop O(1)；容量 O(capacity) |
| 迭代器失效 | map 的 value 存 list 迭代器；list 的 splice/增删不失效其他迭代器（list 稳定性），这是组合成立的根 |
| **cap = 0 边界** | 任何 put 都超容：要么禁止构造、要么 put 即丢——必须在实现里显式处理，不能靠循环兜底（练习 1 的坑） |
| 顺序语义 | 「访问即最近」：get 命中也要提前——漏掉这一点就是「LRU 退化成 FIFO」的经典 bug |
| 多线程 | 本阶段单线程；ph22 的 Buffer Pool LRU 要加 mutex + pin/unpin 引用计数（区别于纯淘汰的 LRU） |
| 自定义类型 | K 需要 `operator==` + `std::hash`；生产里键多半是 int64/slice |

工程里 LRU 的「兄弟」值得知道但不展开：LFU（按频率，淘汰访问最少的）与 Clock（近似 LRU，避免每次访问都改链表，ph22 会作为 LRU 的廉价替代出现）。**LRU 的完整手写（不用 std::list、自建双向链表 + 哈希指向节点）属于练习 1 的加难度分支**——教学上先写组合版建立正确语义，再手写链表版体会「链表节点被哈希索引」的内存模型。

### 3.9 排序与二分：std::sort 内省排序 / stable_sort / lower_bound

排序是 STL 算法区的核心，也是「用 STL 别自己写快排」的第一课。三个函数分场景：

```cpp
// examples/ex06-sort-binary.cpp —— 排序族与二分族（节选）
// 验证环境：Apple clang 21.0.0（对应完整示例已实测；此处教学节选）
std::vector<int> xs{5, 2, 9, 1, 7};
std::sort(xs.begin(), xs.end());                    // 升序：内省排序 O(n log n)
std::sort(xs.begin(), xs.end(), std::greater<>{});  // 降序：传比较器
// 稳定性：std::stable_sort（需要保持相等元素原序，如按分数排序后同名次保持学号序）
// 部分排序：std::partial_sort(前 k 个就位有序, O(n log k))；std::nth_element(第 k 位就位, O(n))
// nth_element 是「找中位数/第 k 小」的工程答案——别先全排序再取第 k 个

std::sort(v.begin(), v.end());
auto it = std::lower_bound(v.begin(), v.end(), x);  // 第一个 >= x
// upper_bound: 第一个 > x；equal_range: 两者成对 → [lower, upper) 是 x 的完整区间
if (std::binary_search(v.begin(), v.end(), x)) { /* 只问在不在 */ }
```

| 函数 | 复杂度 | 保证 | 用途 |
|------|--------|------|------|
| `std::sort` | O(n log n) | **不稳定**；内省排序保最坏 O(n log n)（见 4.3） | 默认排序 |
| `std::stable_sort` | O(n log n)（内存不足时 O(n log²n)） | 稳定 | 需要相等元素保序 |
| `std::partial_sort` | O(n log k) | 前 k 有序 | 「排行榜前 k」 |
| `std::nth_element` | O(n) 平均 | 第 k 位就位，两侧无序 | 中位数、第 k 小 |
| `lower_bound`/`upper_bound` | O(log n)（随机访问迭代器） | 前提：已排序 | 二分查找的工程入口 |
| `binary_search` | O(log n) | 只回答「在不在」 | 别用它拿位置 |

**三个高频陷阱**：① `std::sort` 要求随机访问迭代器——`list` 不能用 sort（它有自己的 `list::sort`），而 `lower_bound` 对 `list` 的迭代器虽然能编译，但复杂度退化成 O(n)（每次 advance 是线性的）——**二分只对随机访问容器是真的 O(log n)**；② `std::map` 有成员版 `find`/`lower_bound`（O(log n)），不要对 map 的迭代器调 `std::lower_bound`（那会用线性步进破坏复杂度）；③ `binary_search` 返回 bool，需要位置用 lower_bound，需要「有几个」用 equal_range 的差。

### 3.10 双指针与滑动窗口

双指针与滑动窗口是「单调性省掉一层循环」的算法模式，容器用 vector、边界处理是全部考点：

```cpp
// examples/ex06-sort-binary.cpp 姊妹题（节选，滑动窗口在完整示例）
// 验证环境：Apple clang 21.0.0（对应完整示例已实测；此处教学节选）
// 滑动窗口：找「和 <= S 的最长连续子数组」（正整数数组，窗口右扩左缩）
std::vector<int> a{3, 1, 2, 1, 1, 1, 4, 2};   // S = 5 的最长窗口长 4（{1,2,1,1}，窗口右扩左缩）
std::size_t left = 0;
long long win_sum = 0;
std::size_t best_len = 0;
for (std::size_t right = 0; right < a.size(); ++right) {   // 右指针每轮前进一次
    win_sum += a[right];
    while (win_sum > 5) {                                  // 超了才收左指针
        win_sum -= a[left];
        ++left;
    }
    best_len = std::max(best_len, right - left + 1);
}
// 双指针模板：有序数组两数之和 —— 左右夹逼，单调性保证每个指针最多走 n 步 → O(n)
```

| 模式 | 特征 | 典型题 | 复杂度来源 |
|------|------|--------|-----------|
| 左右夹逼 | 有序数组，一头一尾 | 两数之和、盛水容器 | 每指针至多走 n 步 → O(n) |
| 快慢指针 | 同向不同速 | 链表环检测、去重 | O(n)，空间 O(1) |
| 滑动窗口 | 子数组/子串连续段 | 最长无重复子串、最短覆盖子串 | 窗口每端至多走 n 步 → O(n) |
| 单调队列/栈 | 窗口内最值、下一个更大 | 滑动窗口最大值 | 每个元素进出一次 → O(n) |

工程里滑动窗口是**限流/聚合窗口**的直接模型（时间窗口内计数、滑动平均），刷题价值与工程价值在此重合。边界注意点统一是三个：**窗口为空（left > right）时别解引用、求和用 64 位防溢出、while 收缩条件的边界值（<= 还是 <）在纸上先定**。

### 3.11 递归、回溯、DP、贪心：算法模式与 STL 的配合

这四个模式不是结构，而是「怎么遍历解空间」的元算法；STL 在这里提供的是骨架工具——`sort`（贪心的预处理）、`queue`（层序）、`vector`（状态表）、`unordered_map`（记忆化）。先给一个统一视角：**回溯 = 递归 + 现场还原（状态撤销）；DP = 递归 + 记忆化（无后效性时）；贪心 = 有「局部最优 = 全局最优」证明时才敢用的 DP 特例**。递归必须显式写清边界（空输入、越界、已访问），否则栈溢出或无限递归。

```cpp
// 递归 + 记忆化：第 n 个斐波那契（教学最小例子）
std::vector<long long> memo(n + 1, -1);
// 递推式 f(n) = f(n-1) + f(n-2)；DP 的本质是自底向上填这张表，避免重复子问题
std::function<long long(int)> fib = [&](int k) -> long long { /* 见完整示例 */ };

// 回溯模板（子集枚举）：选/不选两分支 + 撤销
void backtrack(std::vector<int>& cur, std::size_t i, const std::vector<int>& xs,
               std::vector<std::vector<int>>& out) {
    if (i == xs.size()) { out.push_back(cur); return; }
    cur.push_back(xs[i]);                  // 分支一：选
    backtrack(cur, i + 1, xs, out);
    cur.pop_back();                        // ★ 撤销：回到「没选它」的状态
    backtrack(cur, i + 1, xs, out);        // 分支二：不选
}
```

| 模式 | 判断特征 | 复杂度记号 | STL 承载 |
|------|---------|-----------|---------|
| 递归 | 问题能拆成同构子问题 | 看分支 | 调用栈即隐式栈 |
| 回溯 | 解空间是树/格，需要枚举+剪枝 | O(分支^深度) | vector 当路径栈，pop_back 即撤销 |
| DP | 最优子结构 + 重叠子问题 | O(状态数 × 转移) | vector/二维 vector 状态表；`unordered_map` 稀疏状态 |
| 贪心 | 需证明局部最优推广到全局 | 取决于证明 | 先 `sort` 是贪心的 90% 工程动作 |
| 迭代加深/剪枝 | 深解空间搜可行解 | — | 练习 3 的查询计划树会用到 DFS + 剪枝 |

**工程与刷题的最大差异在 DP 的维度**：刷题的 DP 表是 int 二维数组；工程里的「状态」往往是稀疏的（键是字符串/组合），用 `unordered_map` 或「排序后压缩索引」更实在。另一个工程坑是**递归深度**——默认栈 ~8MB，深递归（10 万层）会栈溢出，工程里要么显式改写成迭代 + 显式栈，要么把递归深度压到可控（分治深度 O(log n) 安全，线性深度的 DFS 对大树危险，3.12 会再提）。

### 3.12 图的遍历与最短路径：BFS / DFS / Dijkstra

BFS/DFS/Dijkstra 是「结构 + STL 组合」的综合训练：它们本身是算法，但工程实现全押在正确使用 `queue`（BFS）、`stack`/递归（DFS）、`priority_queue`（Dijkstra）上，且**边界条件是主要失分点**。

```cpp
// examples/ex05-graph-algos.cpp —— BFS 无权最短路径（节选）
// 验证环境：Apple clang 21.0.0（对应完整示例已实测；此处教学节选）
std::vector<int> bfs_shortest(const graph& g, int src) {
    std::vector<int> dist(static_cast<std::size_t>(g.n), -1);  // -1 = 不可达
    std::queue<int> q;
    dist[static_cast<std::size_t>(src)] = 0;
    q.push(src);
    while (!q.empty()) {
        const int u = q.front();
        q.pop();
        for (const auto& [v, w] : g.adj[static_cast<std::size_t>(u)]) {  // 无权也走邻接表
            if (dist[static_cast<std::size_t>(v)] == -1) {               // 首次到达即最短路
                dist[static_cast<std::size_t>(v)] = dist[static_cast<std::size_t>(u)] + 1;
                q.push(v);
            }
        }
    }
    return dist;
}
```

```cpp
// examples/ex05-graph-algos.cpp —— Dijkstra + 懒删除（节选）
// 验证环境：Apple clang 21.0.0（对应完整示例已实测；此处教学节选）
std::vector<long long> dijkstra(const graph& g, int src) {
    std::vector<long long> dist(static_cast<std::size_t>(g.n), k_inf);
    using item = std::pair<long long, int>;              // {距离, 节点}：距离在前才能按距离排
    std::priority_queue<item, std::vector<item>, std::greater<>> pq;   // 最小堆
    dist[static_cast<std::size_t>(src)] = 0;
    pq.push({0, src});
    while (!pq.empty()) {
        const auto [d, u] = pq.top();
        pq.pop();
        if (d != dist[static_cast<std::size_t>(u)]) continue;  // ★ 懒删除：过期条目直接丢
        for (const auto& [v, w] : g.adj[static_cast<std::size_t>(u)]) {
            if (dist[static_cast<std::size_t>(u)] + w < dist[static_cast<std::size_t>(v)]) {
                dist[static_cast<std::size_t>(v)] = dist[static_cast<std::size_t>(u)] + w;
                pq.push({dist[static_cast<std::size_t>(v)], v});  // 改进就压新条目
            }
        }
    }
    return dist;
}
```

| 算法 | 适用 | 实现要点 | 复杂度 |
|------|------|---------|--------|
| BFS | 无权图最短路、层序 | `queue` + visited 在**入队时**标记（别在出队时，否则重复入队） | O(V+E) |
| DFS | 可达性、拓扑排序、连通分量 | 递归或显式 `stack`；标记 visited 防环 | O(V+E) |
| Dijkstra | 非负权最短路 | 最小堆 + 懒删除（见上）；**负权不能用**（那要 Bellman-Ford/SPFA，roadmap 未列，不展开） | O((V+E) log V) |

**边界清单（全部在 ex05 的断言里）**：孤立点不可达返回 -1/inf；`src` 自身距离 0；稠密图自环/平行边（dist 更新条件用严格 `<` 天然免疫平行边）；`pair` 比较先比距离——所以必须 `{dist, node}` 顺序而不是 `{node, dist}`；距离用 `long long` 防 int 溢出（1e5 节点 × 1e9 边权）。DFS 递归深度的栈溢出风险在 3.11 已提，图的线性深度退化（如一条长链）同样危险——深图优先显式栈。

## 4. 底层原理

### 4.1 vector 扩容与迭代器失效：摊还 O(1) 的物理来源

`vector` 的「摊还 O(1) 尾插」不是魔法，是**容量翻倍策略**的数学结论：容量满时新分配一块更大的连续内存（libc++/libstdc++ 约 2 倍，MSVC 约 1.5 倍）、把旧元素 move/copy 过去、释放旧块。每轮扩容成本 O(n)，但 n 个元素累计只扩容 O(log n) 次，摊到每次 push_back 上是常数——**代价是扩容瞬间的延迟尖峰与所有指向元素的引用/迭代器集体失效**。

```text
capacity 增长（grow 因子 2）：1 → 2 → 4 → 8 → 16 ……
push_back 第 5 个元素时扩容：分配 8 槽 → 搬 4 个 → 释放旧 4 槽
累计搬移 = 1+2+4+8 = 2n-1 ≈ O(n)，n 次插入摊还 O(1)
代价：任何扩容点之后，旧迭代器/引用/指针全部悬空（元素搬了新地址）
```

| vector 操作 | 迭代器失效范围 | 引用/指针 |
|------------|---------------|----------|
| `push_back`/`emplace_back`（扩容时） | 全部失效 | 全部失效 |
| `push_back`（未扩容，还有 spare capacity） | 仅 end()（新元素的位置） | 已有的保持有效 |
| `insert`（中间） | 插入点及之后全失效 | 同上 |
| `erase` | 删除点及之后全失效 | 同上 |
| `reserve`/`resize` | 视是否扩容 | 视是否扩容 |

工程应对三条：① 预知规模就 `reserve`（3.1/3.2 已用）；② 循环里 erase 不要用迭代器步进（用「先收集再统一删」或 `std::remove`/`erase_if` 惯用法）；③ **把「容量」与「大小」分开想**——`size()` 是逻辑元素数，`capacity()` 才是已分配内存，`shrink_to_fit()` 只是请求、不保证生效（ph11 会讲为何不同实现行为不同）。`deque` 用分块存储规避了「扩容搬全部元素」，换来的是引用有效但迭代器在头尾插入时仍可能失效——**每种容器的失效规则是选型时要查的那张表**。

### 4.2 红黑树 vs 哈希表：内存与缓存行为的差距从哪来

同样是「按 key 找 value」，`std::map`（红黑树）与 `std::unordered_map`（链式哈希）的物理差距决定了 3.3 那张选型表背后的原因。核心是**指针追逐次数**：红黑树一次查找要沿树下降 O(log n) ≈ 30 层（对 10 亿元素），每层都是一次「读取一个节点 → 解引用指针 → 跳到孩子」，节点在堆里任意散布，几乎每次都是一次 cache miss；链式哈希则是「哈希桶数组一次命中（连续内存，cache 友好）→ 沿桶内链走冲突几个节点」，冲突链短时 miss 次数显著少。这就是为什么纯单点查找哈希表快、而范围遍历/找前驱树完胜。

```text
std::map（红黑树，n=1000）           unordered_map（链式，bucket=1000）
  每个节点：key+value+左右父 3 指针      桶数组：连续，一次命中
            + 红黑颜色位，24~40 字节     命中后沿链走 avg 1~2 节点
  查找 = log2(n)≈10 次指针跳跃           查找 = 1 次连续读 + 0~1 次链跳跃
  遍历有序但指针追逐（cache 差）           遍历无序但桶扫描连续（cache 好）
```

**每元素内存的账**：红黑树每节点额外 3 个指针（24 字节 on 64-bit）+ 对齐；链式哈希每节点一个 next 指针 + 桶数组（每桶 8 字节）；开放寻址实现无节点开销但槽数组要留空位（load factor ~0.5~0.7）。对「存几百万个小键值」的服务，这个差距就是几百 MB 与几百 MB 的差——ph18 的 Per.19「访问内存要有规律」在这里是选型第一性原理。**结论落回 3.3 的表**：点查密集 + 不 care 顺序 → 哈希（且内存敏感换开放寻址）；有序遍历/范围查询 → 树；两者都频繁 → 工程答案往往是「两个结构各存一份引用」而非指望一个容器两头通。

### 4.3 std::sort 的内省排序：为什么最坏也是 O(n log n)

`std::sort` 的标准保证是平均 O(n log n)，但主流实现（libstdc++/libc++/MSVC）都是 **introsort（内省排序，David Musser 1997）**——它把复杂度保证从「平均」提到「最坏」：先当快排跑（选基准、分区、递归），但**递归深度超过 2·floor(log2 n) 就切换到堆排序**（用已经调好的分区/堆代码），小分区（长度 < 16 左右）不再递归而改用插入排序。纯快排会退化成 O(n²)（比如对已排序数组选到最差基准），内省排序用「深度哨兵」掐死了这条退化路径：

```text
introsort(n)：
  分区深度 ≤ 2·log2(n)？──是──▶ 快排分区，递归两半
          │否（退化信号）
          ▼
      对当前段直接 heap sort（O(k log k)，k 为段长）
  段长 < 16？──是──▶ 插入排序（常数级小数组最快，cache 友好）
复杂度：最优/平均/最坏均 O(n log n)，辅助空间 O(log n)（递归栈）
```

**为什么标准不强制 introsort 却都这么做**：标准只约束复杂度（C++11 后要求 O(n log n) 平均、允许实现自由选算法），而 introsort 是「工程上同时满足最坏保证与常数因子」的最优解，三家实现不约而同。衍生认知：① `std::sort` **不稳定**——相等元素的相对序可能被分区打乱，要稳定就 `stable_sort`（归并 + 插入混合，最坏 O(n log²n)），代价写在 3.9 的表里；② `nth_element` 是同一家族的「阉割版」（只保证第 k 位就位），它也是内省式但不需要排完——所以它是「找中位数」而不是「排序」的答案。

## 5. 使用场景

**刷题视角与工程视角的结构选择**，用一张表对照（同一需求两侧答案不同，差异本身即教学点）：

| 需求 | 刷题的标准答案 | 工程的标准答案 | 差异原因 |
|------|--------------|--------------|---------|
| 「字典」按键查值 | `unordered_map` | 同左；大数据量换开放寻址或排序数组 + 二分 | 工程多问内存与 cache |
| 有序键值 + 范围查询 | `map` | 同左；量级小换排序 vector（cache 碾压树） | 刷题固定容器，工程先算 n |
| LRU | `list` + `unordered_map` | 同左；加容量上限、线程策略、arena | 刷题验收「功能」，工程验收「生命周期」 |
| top-k | 先全排序取前 k | `partial_sort`/`nth_element`/容量 k 的最小堆 | 工程知道 n 与 k 的比值 |
| 图 | 邻接表 vector 或手写 | 邻接表 + reserve 已知度；边是结构体数组 | 工程结构要活过多次遍历 |
| 最短路径 | Dijkstra 手写堆或 priority_queue | priority_queue + 懒删除 | 工程避免维护 decrease-key 的复杂度 |
| 动态规划 | 二维 int 表 | 状态稀疏时 unordered_map / 滚动数组压维 | 工程状态空间常远小于理论值 |

**通用判断顺序（可复述的口诀）**：① 先问访问模式——顺序 / 按键随机 / 有序范围 / 只增不减 / 窗口滑动？② 再问有没有 STL 现成——有就用，别手写；③ 没有（并查集/Trie/LRU 组合/SkipList/Bloom）才手写，手写时所有权用 RAII、复杂度与边界写进注释；④ 最后用「n 是多少、cache 差多少、引用/迭代器要活多久」做现实检验——**刷题答案是复杂度的下界，工程答案还要加常数与生命周期两个维度**。

**与 Rust std / Go container 的对照**（为 analysis/ 与 Tenet 合成积累素材）：

| 结构 | C++（本阶段） | Rust std | Go 标准库 |
|------|--------------|----------|----------|
| 动态数组 | `std::vector` | `Vec`（同思路：翻倍扩容 + 摊还） | `slice`（append 翻倍，语言内建） |
| 双端队列 | `std::deque` | `VecDeque` | 无（用 slice 手动，或第三方） |
| 链表 | `std::list` | `LinkedList`（提示：几乎不用） | `container/list`（同样低频） |
| 哈希表 | `std::unordered_map` | `HashMap`（SipHash 防洪水，默认随机种子） | `map`（内建，随机遍历序） |
| 有序映射 | `std::map`（红黑树） | `BTreeMap`（B 树，有序） | 无（想有序自己 sort + 维护） |
| 优先队列 | `std::priority_queue` | `BinaryHeap`（默认最大堆） | `container/heap`（接口式，自己实现 Less） |
| 堆/树/图手写 | 无 STL，用 vector/unique_ptr 手写 | `BinaryHeap` 之外同样手写 | 全部手写或用第三方 |

三条跨语言观察：① **Rust 没有 std::map，用 BTreeMap**——它选择「有序用 B 树、无序用 SipHash 哈希」，是把 ph21 的「树 vs 哈希选型表」直接编码进标准库；② **Go 只有一个内建 map + slice**，连泛型容器都是 1.18 后才讨论的事——用 Go 写图/堆时 container 包要自己补接口，这反衬 C++ STL 的「容器即语言资产」；③ 三个语言对「手写结构」的态度一致：**链表/红黑树都被判低频，哈希与有序映射是高频抽象**——数据结构课教的是原理，生产库里活下来的永远是那几个高频结构的高质量实现（这正解释了 ph22 为什么敢把 SkipList/HNSW 押在「无 STL 等价物」的手写结构上）。

## 6. 代码示例

> 说明：`examples/` 目录共 6 个主题文件，**全部已在 Apple clang 21.0.0 下 `clang++ -std=c++20 -Wall -Wextra` 编译零警告、运行断言全绿**，其中 ex05 另做 Homebrew clang 21.1.8 交叉核对。每个示例文件头标注验证环境、命令与状态。构建/运行命令与教学要点见 [`examples/README.md`](./examples/README.md)，以下展示关键片段并标注对应正文小节。

```bash
# 通用命令（在 examples/ 目录内执行；产物一律输出到 /tmp，仓库不落二进制）：
clang++ -std=c++20 -Wall -Wextra exNN-<名>.cpp -o /tmp/ph21-exNN && /tmp/ph21-exNN
# 把 exNN 换成下表各文件名即得对应示例的编译运行命令（预期断言见下表「断言内容」）。
```

| 示例文件 | 对应小节 | 断言内容 |
|---------|---------|---------|
| `ex01-stl-selection.cpp` | 3.1 | vector 尾插/中间插成本观察、deque 双端、queue/stack 适配器行为断言全绿 |
| `ex02-hashmap-truth.cpp` | 3.2 | reserve 后无 rehash、load factor 生效、三种插入语义、自定义 pair hash 断言 |
| `ex03-lru-cache.cpp` | 3.8 | get 命中即提前、容量满淘汰最久、重复 put 更新、cap=0 边界全部断言 |
| `ex04-unionfind-trie.cpp` | 3.6/3.7 | 并查集连通/合并/路径压缩深度、Trie 前缀与精确匹配断言 |
| `ex05-graph-algos.cpp` | 3.5/3.12 | BFS 无权最短路、Dijkstra 带权最短路、孤立点/不可达/自环边界断言（另过 Homebrew clang 交叉核对） |
| `ex06-sort-binary.cpp` | 3.9/3.10 | sort/stable_sort 稳定性对照、nth_element、lower_bound 区间语义、双指针/滑动窗口断言 |

## 7. 总结

### 关键要点

1. **每个结构先过「三问」**：STL 有没有现成 → 有则用哪个 → 无则手写注意什么；默认容器是 `std::vector`，默认哈希是 `std::unordered_map`，默认有序映射是 `std::map`，默认堆是 `std::priority_queue`（3.1~3.4）
2. **选型的第一性原理是访问模式 × 操作频率 × 复杂度量级**，工程还要加 cache 与生命周期两维——刷题答案是复杂度下界，工程答案要过现实检验（5 节口诀）
3. **哈希表工程真相三条**：rehash 使迭代器失效但引用有效、`reserve` 免反复 rehash、迭代顺序无保证；要顺序就换 map（3.2）
4. **手写结构的完整清单与理由**：并查集（代码极短）、Trie（前缀查询）、LRU（list+map 组合即标准答案）、SkipList/Bloom（STL 无等价物，ph22 用）；红黑树与堆几乎永不手写（3.6~3.8）
5. **LRU 的四个工程考量点**：get 命中也要提前、map 存 list 迭代器（list 稳定性是组合的根）、cap=0 显式处理、淘汰时先删索引再删节点（3.8）
6. **排序分场景**：默认 `sort`（内省、不稳定）、要稳定用 `stable_sort`、前 k 用 `partial_sort`、第 k 位用 `nth_element`；二分只对随机访问容器真 O(log n)，map 用成员版（3.9）
7. **图算法是 STL 组合的综合训练**：BFS 入队时标记 visited、Dijkstra 最小堆 + 懒删除 + 距离用 long long、负权不属于本阶段（3.12）
8. **边界条件清单是结构的一部分**：空容器 front 是 UB、滑动窗口 left>right 别解引用、递归深度的栈溢出风险、vector 迭代器失效规则表（4.1）
9. **复杂度的三种「实现视角」**：vector 翻倍扩容的摊还 O(1)、哈希表 load factor 的均摊、introsort 深度哨兵的最坏 O(n log n)——把「平均」做成「保证」是实现的活（4.1~4.3）
10. **本阶段是为 ph22/ph23 备结构**：SkipList MemTable / Bloom Filter / LRU（Buffer Pool）/ HNSW 全部没有 STL 等价物，ph21 的手写范式（RAII + 复杂度注释 + 边界测试）会原样搬进存储引擎与向量库

### 阶段验收清单

- [ ] 能对任意需求按 5 节口诀排出「结构选择」并给出复杂度：线性/哈希/树/堆/图各举一例说清何时用、何时换（3.1~3.5）
- [ ] 能徒手写并查集（路径压缩 + 按秩合并）与 Trie（unique_ptr 子节点），并说出各自复杂度（3.6/3.7）
- [ ] 能写出 LRU 的 list + unordered_map 组合版并处理 cap=0 与 get 命中提前（3.8）
- [ ] 能用 STL 组合实现 BFS / DFS / Dijkstra，覆盖孤立点、自环、不可达等边界输入（3.12）
- [ ] 能说清 `sort`/`stable_sort`/`partial_sort`/`nth_element` 的适用与复杂度，以及二分族的迭代器前提（3.9）
- [ ] 能解释 vector 扩容为什么摊还 O(1)、为什么扩容让引用失效、reserve 何时该用（4.1）
- [ ] 能解释红黑树与哈希表在内存/cache 上的物理差距，并落到选型表（4.2）
- [ ] 能解释 introsort 如何用深度哨兵把最坏复杂度压到 O(n log n)（4.3）
- [ ] 手写结构都带复杂度标注与边界测试（examples/ex03/ex04 与 project 为样板）

### 跨语言对比

见第 5 节末对照表。给 analysis/ 与 Tenet 合成的启示：**Rust 把「树 vs 哈希」的选型直接编进标准库（有序 = BTreeMap，无序 = HashMap + SipHash），Go 则只有内建 map/slice、把结构自由留给第三方**——两种设计哲学夹着 C++ 的「全都要但全手工选」。若 Tenet 语言想要「容器即语言资产」又不重复 C++ 的选择负担，可以尝试：默认容器显式声明访问模式（`map` 直接区分 ordered/unordered/vec 三种实现）、对「无 STL 等价物」的结构（LRU/SkipList/Bloom）提供标准组件而不仅是算法题——这正是 ph22 存储引擎需要的结构，语言层给不给决定了引擎写得动写不动。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看），共 4 题，与 roadmap §21「练习」小节一一对应：LRU Cache（练习 1）/ 任务调度器（练习 2）/ 查询计划树 demo（练习 3）/ 内存池（练习 4）。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**SkipList MemTable**——手写概率平衡的有序键值结构（STL 无等价物），自带 put/get/delete/有序扫描与边界测试，直接为 ph22 存储引擎铺路（roadmap §21 推荐项目取「SkipList MemTable」，另三个推荐项目的去向见 project/README「扩展方向」与 1 节边界声明）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`make clean && make test` 退出码 0、结构断言 + 边界断言全绿）

### 下一阶段

[**ph22 存储引擎与数据库内核专项**](../ph22-storage-engine-db-kernel/22-storage-engine-db-kernel.md)（roadmap 第 22 节，现已建成） — 本阶段预告的兑现点：把 SkipList MemTable 接上 WAL 的写入与 replay、把有序扫描喂给 SSTable 的 flush、给 SSTable 点查加 Bloom Filter、让 Buffer Pool 用 LRU/Clock 管淘汰——结构已在 ph21 备好（练习 1 的 LRU = Buffer Pool 的心、project 的 SkipList MemTable = 存储引擎的写路径、3.2 的哈希 = Bloom 位哈希的思想原型），ph22 把它们从「内存结构」变成「磁盘上的引擎模块」，并回答 ph21 刻意回避的问题：结构要活成「跨崩溃、跨并发、管脏页、管淘汰」的样子需要补什么。

