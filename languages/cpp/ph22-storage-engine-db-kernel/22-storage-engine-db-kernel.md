# C++ 存储引擎与数据库内核专项阶段

> 面向 KV 库、数据库内核与存储引擎方向：把 WAL 崩溃恢复、MemTable 写路径、SSTable 不可变文件、Bloom 过滤、Buffer Pool 页缓存、Compaction 与 Iterator 归并串成一台能跑会恢复的 mini KV——ph22 是 C++ 路线从「单机内存结构」正式转入「存储 / AI 地基」的转折点，ph21 备好的 SkipList/LRU/Bloom 结构在这里第一次接上磁盘与日志。

## 1. 概述

本阶段是学习路线的第 22 步（roadmap §22 目标：理解 C++ 在数据库内核、KV 存储与高性能存储引擎中的使用方式，能实现 Mini KV / Mini LSM 的核心模块）。ph21 的问题是「进程里用什么结构组织数据」，本阶段的问题是同一个问题的升级版：**这些结构要活成「跨崩溃、跨文件、管脏页、管淘汰」的样子，需要补什么**。答案就是一条完整的引擎骨架——写入先落 WAL 再进 MemTable，MemTable 满则 flush 成不可变 SSTable，点查每层先用 Bloom 过滤、再由稀疏索引定位，Buffer Pool 用 LRU/Clock 管页淘汰，Snapshot/版本号把「读一致性」从单值提升到多版本，Iterator 抽象把内存层与磁盘层接成同一张读面做 range scan。最后用 LevelDB/RocksDB 的源码阅读引导把这些概念对回工业实现。

| 核心维度 | 覆盖内容 |
|----------|---------|
| WAL 日志 | record 布局（magic/type/长度前缀/CRC）；append-only 与 fsync 边界；replay 校验链；残尾修复；日志作废重建 |
| MemTable 写路径 | 直接复用 ph21 project 的 skip_list_map；put/覆盖/tombstone 删除语义；flush 有序读面 |
| SSTable | 不可变有序文件；block 内升序 entry；稀疏索引（块首 key → 偏移）；定长 footer；writer/reader |
| Bloom Filter | 位数组 + 双哈希；素数位数组的必要性；假阳性率理论 vs 实测；挂进点查路径与拦截计量 |
| Compaction | 归并语义（覆盖丢弃/tombstone 到底才真删）；读/写/空间三放大；leveled vs tiered 策略与调参 |
| B+Tree | 高扇出/叶子链表/分裂；与 LSM 的适用场景对照（读优 vs 写优） |
| Buffer Pool | 页帧、命中率、脏页写回、pin/unpin、LRU 精确淘汰 vs Clock 近似淘汰 |
| Snapshot / MVCC | 版本号链、可见性判断规则、删除 = 新版本（tombstone 是 MVCC 的亲戚） |
| Iterator 抽象 | 统一读面；多源（MemTable + 多层 SSTable）按序归并；新层赢旧层；range scan |
| 源码阅读引导 | LevelDB/RocksDB 的写/读/恢复调用链；挑一个核心模块（MemTable 或 TableCache）解剖 |

这个阶段只涉及**单机、单线程的存储引擎核心组件语义与串联（WAL/MemTable/SSTable/Bloom/Compaction 原理/Buffer Pool/B+Tree 概念/MVCC 概念/Iterator 归并）**，**不涉及向量检索与 AI 推理引擎方向 C++（HNSW 图索引、IVF/PQ、SIMD 距离、Faiss、KV Cache 与推理服务属于 ph23 向量检索与 AI 推理引擎方向 C++（roadmap 第 23 节，目录待建）——ph22 的磁盘/页管理是为 ph23 的「向量索引持久化」铺的地基，但向量数据结构本身是 ph23 的内容）、不涉及查询执行器与 SQL 层（本路线到 §23 为止没有规划查询阶段，列式存储/向量化执行只出现在 roadmap 尾部的「推荐路线」展望里，不占编号阶段）、不涉及分布式一致性与多机 KV（Raft/分片属 C 路线结尾与通用分布式理论，C++ roadmap 未规划）、不涉及事务 ACID 的 undo 方向（本阶段 WAL 只做 redo——崩溃后重放，不处理「回滚已提交前状态」，undo/隔离完整体系超出路线范围）**。关于同主题的 C 版参照：C 路线 ph16 也做了 WAL/MemTable/SSTable/Bloom/LSM 骨架（languages/c/ph16-storage-engine），主题相近但那是 C 路线的终点阶段、以「字节纪律 + 全手工内存」为主线；本阶段是 C++ 路线**中段的地基转折**、以「RAII/容器/结构复用 + 接 ph21 组件」为主线——分工视角与差异在第 5 节专述，文件格式尽量与 C 版对齐（大端、CRC 覆盖 magic 之后整段、tombstone 语义），便于跨语言对照。
本阶段是路线进入「存储 / AI 地基」的转折：ph21 结束时只能说明结构为什么对，ph22 结束时能说明**整台引擎为什么能跑、崩溃后为什么能回来、哪些读贵在哪儿**——这套心智随后原样平移到 ph23 的向量库与推理服务的存储/缓存问题上。

## 2. 来源与演变

存储引擎的两条主线——**先写日志再改数据（WAL）**与**就地更新还是追加合并（B+Tree vs LSM）**——分别来自 1970~1990 年代的数据库研究，又在 2006 年 Bigtable 之后被 KV 时代重新点燃。**设计哲学一句话：磁盘（乃至 SSD）的随机写远贵于顺序写，存储引擎的每个结构都是在「读成本」与「写成本」之间选边，WAL 与 LSM 把随机写变成顺序写，B+Tree 与 Buffer Pool 把磁盘读摊成可缓存的页读**。

先写日志（WAL）的传统要回溯到 1970 年代系统 R 以来的崩溃恢复研究：磁盘上的数据页可以滞后落盘，但「我打算做什么」的意图必须先持久化——崩溃后按日志重放（redo）就能把内存态补回来。1992 年 Mohan 等人的 **ARIES** 把 WAL + redo + undo 完整系统化，此后「先写日志」成为关系库与 KV 的默认纪律。Bloom Filter 是 Burton Bloom 1970 年的论文「Space/Time Trade-offs in Hash Coding with Allowable Errors」，用位数组 + 多哈希换「无假阴性、可控假阳性」，半个世纪后成为 LSM 减少无效磁盘读的标准件。**LSM Tree**（Log-Structured Merge-Tree）是 O'Neil 等 1996 年的论文：把随机写先收进内存有序结构、再批量落成不可变有序文件、后台归并整理——用「写放大 + 读放大」的代价换掉「随机写」。Google 2006 年的 **Bigtable** 论文把 MemTable/SSTable 这两个词带进工程词汇表；**LevelDB**（2011，Google 开源）把 LSM 做成单机嵌入式库，**RocksDB**（2013 开源，2012 起 Facebook 内部开发）在其上加了列族、合并算子与可调参数，成为今天 KV 基础设施的参考实现——C++ 写存储引擎的「为什么这样设计」答案大部分要回到这两个项目。B+Tree 是另一条线：1972 年 Bayer & McCreight 提出 B-Tree，1979 年 Comer 的综述把「数据全在叶子 + 叶子链表」的 B+Tree 变体系统化，此后五十年关系库索引几乎都长这样。**MVCC 的概念史**与存储布局不同，它来自并发控制理论：1981 年 Bernstein & Goodman 的「Multiversion Concurrency Control—Theory and Algorithms」把「让读写不互相等待」变成理论对象；1995 年 Berenson 等（SQL 标准组）定义 **Snapshot Isolation**；工程上 PostgreSQL（1990s 起）与 MySQL InnoDB 各自实现，把「旧版本留在原地、新版本另起一行」变成数据库默认——这个「删除/更新 = 写一条新版本」的模型，正是 LSM 里 tombstone 的精神祖先。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| Bloom Filter（Burton Bloom） | 1970 | 位数组 + 多哈希：无假阴性、可控假阳性；后成 LSM 点查过滤标准件 |
| B-Tree（Bayer & McCreight） | 1972 | 高扇出平衡树；磁盘页粒度索引的起点 |
| B+Tree 变体（Comer 综述） | 1979 | 数据全在叶子 + 叶子链表；关系库索引的最终形态 |
| MVCC / SI（Bernstein-Goodman；Berenson 等） | 1981/1995 | 多版本并发控制理论化；Snapshot Isolation 进 SQL 标准讨论 |
| ARIES（Mohan 等） | 1992 | WAL + redo/undo 完整范式；崩溃恢复的教科书答案 |
| LSM Tree（O'Neil 等） | 1996 | 随机写转顺序写 + 分层归并；写吞吐优先的 KV 主线 |
| Google Bigtable | 2006 | MemTable/SSTable 工程命名普及；「tablet = MemTable + 一串 SSTable」 |
| LevelDB | 2011 | LSM 单机嵌入式库成熟：WAL + MemTable + SSTable + Bloom + Compaction 成标配 |
| RocksDB | 2013 | LevelDB 的 Facebook 增强：列族、合并算子、可调参数，KV 基础设施参考实现 |
| C++20 | 2020 | 本阶段基线：`std::string_view`/range/泛型已稳定可用，支撑存储层抽象代码 |

本文示例以 **C++20** 为基线（与 ph21 同口径——本阶段代码大量用 `std::string_view`（Iterator 读面不拷贝）、`std::unique_ptr`（组件所有权）、泛型与 range 逻辑；C++20 在这些面上是稳定且充分的最小版本），验证工具链为 **Apple clang 21.0.0**（`/usr/bin/clang++`，默认 PATH）+ **Homebrew clang 21.1.8**（`/opt/homebrew/opt/llvm/bin/clang++`，交叉核对），macOS arm64 + libc++。**本阶段全部代码均为纯 C++（无第三方依赖）**：examples/（6 个）、exercises/（5 题参考实现）、project/（Mini LSM KV）已逐个在本环境 `-std=c++20 -Wall -Wextra` 编译运行验证（零警告、断言全绿），project 另过 ASan/UBSan；每个文件头标注验证状态。存储内核的写法是 C++ 里最稳定的一档——record 布局与 WAL 纪律与 C 版 ph16 五十年不变的部分一致，换编译器风险主要来自「字节序/位数假设」（本阶段统一大端 + `std::uintXX_t` 规避），这一点与 C 路线 ph12/ph16 是同一套纪律。

## 3. 语法与参数

> 本节代码块是**教学骨架**：聚焦单个组件裁剪。完整可运行文件见第 6 节与 [`examples/`](./examples/)（全部已在本环境实测，命令见 examples/README.md）；内嵌片段标注来源文件与验证状态。本阶段的「语法与参数」不指向 C++ 语言特性，而是指向**存储组件的接口与布局参数**——这正是 roadmap §22 学习内容的形态。

### 3.1 WAL：record 格式 / 校验 / replay / 崩溃恢复

WAL（Write-Ahead Log）的第一性原理：**任何状态变更，先把「我打算做什么」追加到日志并落盘，再改内存结构**。崩溃后 replay 日志即可重建内存态——代价是每次写多一次顺序追加，换来的是「把随机写的崩溃窗口收窄到一条记录」。record 是原子单位，布局参数全在「为什么这样设计」里（examples/ex01 与 C 版 ph16 同款格式，可直接对照）：

| record 字段 | 作用 | 没有它会怎样 |
|------|------|-------------|
| magic u32 | 识别「这是我们的记录」 | 垃圾/错位数据被当成合法记录解析 |
| type u8 | 区分 PUT / DEL（删除 = tombstone 记录，不是擦除） | 删除无法表达，日志只能增不能删 |
| klen/vlen u32 | 长度前缀 → replay 能逐条跳读 | 解析器必须理解 payload 才能找下一条 |
| key/value | payload | — |
| crc32 u32（覆盖 magic 之后的整段） | 校验完整性（残写、位衰减在此现形） | 半条记录被当完整记录，数据悄悄错乱 |

```cpp
// examples/ex01-wal-append-replay.cpp —— WAL 编码（节选，已验证）
// record = [magic u32][type u8][klen u32][vlen u32][key][value][crc32]
// 多字节显式大端；crc 覆盖「type..value」整段（跳过 magic 自身）
std::vector<std::uint8_t> encode(const record& r) {
    const std::size_t total = k_hdr_size + r.key.size() + r.value.size();
    std::vector<std::uint8_t> buf(total + k_crc_size);
    put_u32be(buf.data(), k_magic);
    buf[4] = static_cast<std::uint8_t>(r.op);
    put_u32be(buf.data() + 5, static_cast<std::uint32_t>(r.key.size()));
    put_u32be(buf.data() + 9, static_cast<std::uint32_t>(r.value.size()));
    // ... key/value 拷贝 ...
    const std::uint32_t crc = crc32(buf.data() + 4, total - 4);  // ★ 校验范围与 replay 端必须一致
    put_u32be(buf.data() + total, crc);
    return buf;
}
```

**WAL 在两条路径里的位置**（把它放进引擎看更清楚，project/ 即按此实现）：

```text
写路径：put/del ──▶ WAL append + fsync ──▶ MemTable put（tombstone 语义）
                             崩溃？──是──▶ 丢最后一条残记录（可修复），其余 op 在日志里安然无恙
恢复路径：open ──▶ WAL replay（四道校验，遇残尾 ftruncate）──▶ 重建 MemTable
flush 之后：SSTable 已固化 ──▶ 旧 WAL 作废重建（日志只增不改，清理靠整体重建）
```

**replay 的校验顺序是四道防线，且顺序有讲究**：① 剩余长度够一个头 → ② magic 吻合 → ③ klen/vlen 联合长度上限（各自 ≤ 上限 **且** 合计 ≤ 上限，否则两项各接近上限时固定缓冲会被越界写坏）→ ④ CRC 吻合。任一失败就停在**残尾（torn tail）**，报告偏移；修复手段是 `ftruncate` 截到干净位置，之后日志还能继续追加——这就是崩溃恢复的「最多丢最后一条」承诺的来源。examples/ex01 实测了三条路径：

```text
[1] 追加 3 条后 replay: 3 条全对
[2] 塞 6 字节残尾 → replay 停在偏移 73；ftruncate 修复后回到干净态且可继续追加
[3] 翻转第二条 payload 一字节 → CRC 拦截，torn 偏移 = 第二条起始 23
```

**三条工程纪律**（ex01 逐一演示）：① 追加必须 O_APPEND + 短写循环（EINTR 重试）；② **append 返回 ≠ 持久化**——数据只到内核 Page Cache，`fsync` 返回才算「可承诺」；③ 校验范围在编码端与 replay 端**必须逐字节一致**——本项目开发时曾因 replay 漏算 klen/vlen 段导致全部记录被判损坏，这是最容易犯的错，注释已标出。关于 fsync 的成本与组提交（group commit）见 4.3——工程上绝不是每条都 fsync，而是攒批一次落盘。

**replay 的「残尾」判定有一个隐性坑**：当文件尾恰好剩下不足一个头的字节、且这些字节又都读得出来时，不能凭「读到的字节数 < 头大小」判干净——要用「**文件尾 > 已解析位置**」判残尾（exercises/sol-01 曾把「读完的 8 字节残尾」误判成干净 EOF，注释有记录）。同类陷阱还有：编码端与 replay 端用同一个长度公式（别一头写 `magic+type+长度`、另一头只校验 `type+payload`），以及 payload 上限必须是 klen/vlen 的**联合**上限。

> 崩溃恢复的 undo 方向（回滚未提交事务）不在本阶段：WAL 只做 redo——**完整事务的 ACID 属于数据库事务理论（本路线未规划），本阶段只需理解「重放日志重建内存态」这一半**。

### 3.2 MemTable：SkipList 写路径（链接 ph21 project）

MemTable 是 LSM 的内存层：**所有写入先进它，保持 key 有序，写满后整体 flush 成 SSTable**。为什么选 Skip List 而不是红黑树（ph21 的 `std::map`）？因为 MemTable 的工程约束是「写路径简单 + 并发可改造 + 天然有序迭代」——Skip List 用随机层数替代旋转，层次结构对无锁并发友好，LevelDB/RocksDB 的 MemTable 就是 skip-list。**本阶段直接复用 ph21 project 的 `skip_list_map`**（头文件按任务要求整体复制到 project/ 并注明来源，未改功能），这是 ph21「下一阶段」预告的兑现点之一：

```cpp
// project/skip_list.h —— 复制自 ph21-data-structures-algorithms/project/skip_list.h（原样）
// 读面：begin()/end()/lower_bound() 有序扫描；find_value 返回非拥有指针（erase 前有效）
namespace ph21 {
template <typename K, typename V, typename Compare = std::less<K>>
class skip_list_map { /* put/erase/find_value/lower_bound/begin/end/check_invariants */ };
}
```

但引擎层不能在 MemTable 上直接 erase 节点来表示删除——**删除必须写成 tombstone（deleted 标记的条目）**，否则「删除」这个意图在 flush 成 SSTable 时就会消失（节点没了就什么都没了）。于是引擎给值类型包一层：

```cpp
// project/lsm.h —— MemTable 的值形态（节选，已验证）
struct mem_value {
    bool deleted{false};   // 删除 = tombstone 写入，不是 erase 节点
    std::string value;
};
using mem_table = ph21::skip_list_map<std::string, mem_value>;
// put("k", v)      → mem_->put(k, mem_value{false, v});
// del("k")         → mem_->put(k, mem_value{true, ""});   // 删除也是一种写入
// find_value 命中后：deleted 为真 → 上层判「不存在」（并遮挡更旧层，见 3.9）
```

三条语义必须立住（project 自测 [1] 实测）：**保序**（乱序写入内部仍按 key 有序——这是 flush 成 SSTable 与 range scan 的前提）、**覆盖**（同 key 再 put 换值）、**tombstone 删除**（del 后该 key 的内存态是「已删」而不是「不存在」——get 时它要挡住旧层同名值）。flush 的读面正是 ph21 就备好的有序迭代：

```cpp
// project/lsm.h —— flush（节选，已验证）：MemTable 有序扫描 = SSTable 的输入
for (auto it = mem_->begin(); it != mem_->end(); ++it) {
    snapshot.push_back(sst::rec{std::string(it.key()), it.value().value, it.value().deleted});
}
sst::write_sstable(path, snapshot);   // 整体落成不可变文件
mem_->reset(); wal_->reset();         // flush 后旧 WAL 作废（op 已全部固化）
```

注意 flush 之后的顺序：**先写 SSTable（fsync），再把 MemTable 与 WAL 一起清空**——若反过来，清完 WAL 才写表，中间崩溃会两头空。WAL「作废重建」而不是「删除单条」也回答了 3.1 的一个问题：日志只增不改，清理靠整体重建。

**MemTable 的三种实现档位**（本阶段用 skip-list 是因为它同时满足写路径简单 + 有序扫描 + 并发可改造）：

| 实现 | 插入定位 | 范围扫描 | 并发友好 | 谁在用 |
|------|---------|---------|---------|--------|
| 有序数组 + 二分 + memmove | O(log n) 定位 + O(n) 搬移 | 天然 | 差 | C 路线 ph16 教学版（30 行讲清语义） |
| 红黑树（`std::map`） | O(log n) | 天然 | 差（无锁难） | STL 通用场景 |
| Skip List | O(log n) 期望 | 天然（层间子序列） | **好（Pugh 1992 无锁版）** | LevelDB/RocksDB MemTable |
| 哈希表 | O(1) | ❌ 无顺序 | — | 不是 MemTable 的选项（丢有序） |

选择 skip-list 的**决定性理由是有序 + 可并发**，不是插入复杂度本身——这正是 ph21「三问表」里「SkipList 何时必须手写」的工程答案。

### 3.3 SSTable：block 布局 / 不可变有序文件 / writer + reader

SSTable（Sorted String Table）= **不可变有序文件**：MemTable flush 时把有序内容一次写成新文件，之后只读不改。「不可变」是它一切优点的来源——**并发读不用锁、崩溃不会半改（写不完整整文件丢弃即可）、缓存随便做（缓存里永远只有干净页，不用写回）**。本阶段文件布局（examples/ex02 / sol-02 / project 三处同一套语言，两处带 block header/校验）：

```text
[数据区]  block*（每块 k_block_cap 条，key 升序）
           entry = [klen u32][vlen u32][key][value]           ← examples/ex02 最小版
           block header = [count u16][reserved u16][crc32]    ← sol-02 进阶版（块级校验）
[索引区]  每数据块 1 条：块首 key + 块在文件中的偏移（稀疏索引）
[bloom 区] Bloom 位数组（k、m 精确持久化）                    ← project/ 版
[footer]  定长：data_off/index_off/index_size/bloom_off/.../magic
```

| 布局参数 | 设计理由 |
|---------|---------|
| entry 带长度前缀 | 变长 key/value 可跳读；replay/scan 不需要理解内容 |
| 索引只记「块首 key + 偏移」 | 稀疏索引：全量索引内存装不下，无索引只能全扫；每块跳一次 + 块内扫 ≤ 容量条 |
| 索引项记「块起点」 | 若记成块尾（本项目开发时的真实 bug），二分定位后必然读错一块 |
| footer 定长放文件尾 | 打开文件只要读最后几十字节就能拿到全部区段的位置 |
| 数据整体一次 fsync | 不可变文件要么完整可见、要么不存在 |

**writer/reader 的资源管理纪律**（cpp-coding-standards R.1/R.11 在文件层的样子）：文件描述符必须 RAII 封装（`fd_file` 构造拿 fd、析构自动 close、禁用拷贝、移动转移），writer 在函数内持有 fd 直到 fsync 完成，异常路径靠析构兜底——不存在「手动 close 被跳过导致泄漏」的路径；文件字节归 `std::vector<uint8_t>` 所有，reader 全程无裸指针越界（所有切片都走「偏移 + 长度 + 边界检查」）。教学简化（已注明）：reader 整文件读入内存，真实引擎是页粒度读入 Buffer Pool（3.7）。

点查路径三步（examples/ex02 实测：10 条记录 3 个 block、文件 232 字节）：**读 footer（文件尾定长定位）→ 载入索引对「块首 key」二分 → 跳到命中块内顺序扫 ≤ 4 条**。比全文件最小 key 还小的查询零数据区扫描（实测断言 `e2 == 0`）；比最后一块首 key 大的查询定位到末块扫完即 miss。sol-02 给 block 加了校验和：**SSTable 不可变 → 读到损坏块只能「拒绝服务」不能静默错数据**——实测篡改一个字节后点查抛异常。project/ 版在此基础上把 Bloom 区也编进文件（布局见 3.4）。

```text
SSTable 点查路径（每步是磁盘/内存的一次"跳转"）：
  读 footer（文件尾 28/32 字节，定长）──▶ 拿到 index_off / bloom_off / 各段长度
  ──▶ 载入 bloom（"不在" → 返回，零数据区 IO；见 3.4）
  ──▶ 载入索引，对"块首 key"二分（O(log 块数)）
  ──▶ 跳到命中块的起始偏移，块内顺扫 ≤ 8 条（block cap）──▶ 命中/越界/miss
```

> 页粒度读盘、mmap、压缩块（snappy/lz4）属于工程进阶——C 路线 ph13（mmap 与可靠文件 IO）给了更系统的视角，本阶段所有 reader 采用「整文件读入内存」的教学简化并注明，重点在偏移解析与索引跳转，不在 IO 调度。

### 3.4 Bloom Filter：位数组 / 多哈希 / 假阳性率，加进点查路径

SSTable 越多，「查一个不存在的 key」越贵——每层都可能白读一次。Bloom Filter 挂在每个 SSTable 的查询最前面：**「肯定不在」直接跳过（零数据区 IO），「可能在」才真去读**。它的概率承诺是：无假阴性（说过不在就一定不在）+ 可控假阳性。假阳性率的闭式解：`p ≈ (1 - e^(-kn/m))^k`（m 位数组大小、k 哈希数、n 已插入 key 数），k 的最优点 ≈ `(m/n)·ln2`。

```cpp
// examples/ex03-bloom-filter.cpp —— 双哈希法（节选，已验证）
void add(std::string_view key) {
    const auto [h1, h2] = bases(key);               // FNV-1a(key,1) 与 FNV-1a(key,2)
    for (std::size_t i = 0; i < k_; ++i) {
        set_bit((h1 + static_cast<std::uint64_t>(i) * h2) % m_);  // 一个基哈希序列 = k 个位
    }
}
```

**两个必须在实现里踩过的坑**（本阶段全部代码实测并注明）：① **m 必须取素数**（或 2 的幂 + 强制 h2 奇数）——本项目开发时用偶数 m=100000 实测假阳性率 4.06% vs 理论 0.82%（双哈希序列全部同奇偶，位置聚集），换成素数 100003 后降到 0.774%，k=4/7/10 曲线也贴合理论（k=4 实测 1.079% vs 1.181%、k=10 实测 1.022% vs 1.018%）——这是「实现细节决定理论是否成立」的活教材；② **Bloom 的 m 要精确落盘**——位数组字节数是 ceil(m/8)，reader 若用字节数反推 m 会因进位错位（sol-03 注释有完整教训）。

**假阳性率为什么长这样**（一段可手推的直觉）：插了 n 个 key、每个打 k 位，某一位被置 1 的概率是 `1 - (1 - 1/m)^(kn) ≈ 1 - e^(-kn/m)`。探测一个不存在的 key 要撞 k 个位、全部撞在 1 上才误报，所以 `p ≈ (1 - e^(-kn/m))^k`。对 k 求导找极值：最优 `k = (m/n)·ln2 ≈ 0.693·(m/n)`——m/n=10 时最优 k≈6.9，所以本阶段代码取 7；k 太小每个 key 只打几个位、撞位概率高，k 太大位数组很快被塞满、处处都是 1——实测 k=4/7/10 的曲线完美展示这个 U 形。

```text
examples/ex03 实测（n=10000, m=100003 位, k=7）:
  已插入 key 回查漏报: 0                ← 无假阴性的实证
  100000 个未插入 key: 误判 774 次 = 0.774% (理论 0.819%)
  5000 次不存在点查: 拦截 4952 次 = 99.04% 无需读数据
```

**怎么「加进点查路径」**：建表时把全部 key add 进位数组随表落盘；点查先 `maybe_contains`，false 直接返回「无」，true 才走索引 + 数据区。**关键语义：tombstone 的 key 也必须 add**——Bloom 只回答「表里有没有这个 key」，不回答「活着还是已删」，漏加会让删除被误拦、旧值从更旧层「复活」。project/ 与 sol-03 都实现了可计数的拦截统计：project 自测里 300 次不存在点查让 bloom 拦截计数从 1 涨到 600（每层各拦一次）；sol-03 在带 91 条 tombstone 的 1000 条表上测得 20000 次不存在查询拦截率 99.25%。Bloom 的另一条边界是**不能删**：清一个位会误伤共享该位的其他 key——所以它永远随 SSTable 重建（不可变文件重建一次、Bloom 也重建一次），而不是试图支持删除。

### 3.5 Compaction：leveled vs tiered / 读写放大是核心成本

compaction 是 LSM 的「后台整理」：多个有序 run（SSTable）归并成更少的 run。一次归并做三件事（examples/ex06 实测）：**旧值被新值覆盖（丢弃）、tombstone 真正删掉 key、数据更紧凑**。归并规则里最微妙的是 tombstone 的生存期（ex06 [2] 实测）：

- **非底层归并必须保留删除标记**——下面还有更老的 run，若把 tombstone 丢掉，更老 run 里那个 key 的旧值就会「复活」；
- **full compaction（归并到底）才能真删**——没有任何更老数据了，删除标记落地为「key 不存在」。

```text
examples/ex06 实测（3 个 run，6 条含重复与删除）:
  full compaction: 6 条 92B → 2 条 31B（覆盖丢 3、tombstone 真删 1）
  读放大: 点查不存在的 key 从探测 3 个 run → 1 个
  空间放大: 物理 92B / 有效 31B ≈ 2.97x
  归并节奏: 每次 flush 都归并累计写 13830B；攒 4 次归并一次 3817B ← 攒批降写放大
```

三种放大是 LSM 的成本语言（数学直觉见 4.1），而 **leveled vs tiered 是「用哪种放大换哪种」的两种策略**：

| 维度 | leveled（LevelDB/RocksDB 默认） | tiered / size-tiered（RocksDB universal 近似） |
|------|-------------------------------|----------------------------------------------|
| 层内 run 数 | 每层尽量只有 1 个大 run | 每层可以多个，靠 run 大小分组 |
| 触发规则 | L0 文件多/下层重叠多时挑文件归并下去 | 同尺寸 run 攒够 N 个就整体归并成一个更大的 |
| 写放大 | 偏高（数据沿层下移反复重写，约 O(log) 且常数大） | 较低（同尺寸批量归并，历史重写次数少） |
| 读放大 | 低（每层一个大文件，点查每层至多一次） | 高（一层多个 run，点查要逐 run 探测） |
| 空间放大 | 低（文件都整过） | 较高（大 run 等待合并期间物理占用翻倍） |
| 典型代价 | 更新密集时写放大 ~20-30x | 读放大随 run 数线性涨 |

**ex06 [3] 的「每次 flush 都归并 vs 攒批归并」就是这两个策略的代价本质**：归并越勤，每层越「干净」（读放大低、空间低），但同样的历史数据被反复重写（写放大高）；归并越懒，写放大越低，代价是没归并前点查要跨更多 run、空间上大 run 在排队。**「何时触发 compaction」本身就是调参**——RocksDB 的可调旋钮（level 大小乘数、L0 文件数上限、触发文件数）全是在这三个放大之间搬砖。工程上还有两个本阶段不展开的优化：compaction 挑「与新区间重叠的文件」而不是全量（leveled 的关键，避免重写不相交区间）；以及 LSM 的删除最终要靠 compaction 落地，所以墓碑堆积（tombstone 积压）是运维要盯的指标。

```text
leveled 的层结构（数字示意，T=10）：
  L0  : [memflush 生成的小文件们，允许重叠]        ← 写入第一站，最乱
  L1  : [──────────── 一个大 run ────────────]     ← 每层只维护一个大文件
  L2  : [───────────────────────────── 大 run ─]   ← 容量约为上一层的 T 倍
  L3  : [──────────── 更大的 run，可再分区间文件 ─] 
  点查：从 L0 往下每层至多探测 1 个文件 → 读放大 ≈ 层数（Bloom 先挡）
  写入：新数据从 L0 一路下移到与它 key 区间重叠的地方 → 数据被重写 ≈ 层数次
```

堆墓碑类比：LSM 的 compaction 很像**堆内存的 GC**——内存 GC 回收「不再可达的对象」，compaction 回收「不再可见的版本」；触发时机都是「空间不够/积压太多时」，代价都是 stop-the-world 式的停顿（compaction 的 I/O 尖峰）。这个类比能帮你理解为什么运维 LSM 会聊「compaction 风暴」——GC 风暴的磁盘版。

### 3.6 B+Tree：结构 / 与 LSM 场景差异对照

LSM 之外的另一条主线，也是关系库索引五十年不变的默认结构。三条特征（C 版 ph16 3.6 有同款展开，本阶段给 C++ 视角的对照结论）：

1. **高扇出**：每节点存几十~几百个 key，树高 = log 级——按 4 KiB 页、key 8 字节 + 子指针 8 字节粗算，内节点可放约 256 个槽；扇出决定树高 ≈ 一次点查的页读取次数。
2. **数据全在叶子**：内节点只存路标 key，叶子间用链表串联——range scan 定位起点叶后沿链表顺序走，这是 B+Tree 读路径「可预测」的来源。
3. **插入分裂保平衡**：叶分裂上提的是**副本**（叶子自己保留该 key，因为数据在叶子），内节点分裂上提的是**本体**——一字之差是 B+Tree 实现最易错点（exercises 侧的 sol-02 用 SSTable block 练了类似的分块读写，B+Tree 本身的插入实现超出本阶段范围）。

| 对照维度 | LSM（本阶段主线） | B+Tree（概念对照） |
|---------|------------------|-------------------|
| 写入形态 | 顺序追加：WAL → MemTable → 不可变 SSTable | 就地更新：沿树找到叶子改写/插入（页级随机写） |
| 写吞吐 | 高（随机写转顺序写） | 中（每次更新命中 1~2 页随机 IO） |
| 点查读 | 差一点：跨多层逐层探测（靠 Bloom 挡） | 好：树高次数页读，路径确定 |
| 范围查询 | MemTable/各层归并，需合并多源 | 叶子链表天然有序 |
| 空间 | 写放大/空间放大要 compaction 打理 | 页内空闲低时即分裂，无全局整理需求 |
| 负载适配 | **写多读多、追加为主**（日志、时序、KV 写入密集） | **读多写少、点查/范围明确**（关系库 OLTP 索引） |

**结论不是「谁更好」而是「读与写谁优先」**：写入是主要矛盾 → LSM（磁盘随机写远贵于顺序写）；读延迟是硬指标且更新稀疏 → B+Tree。两个阵营都离不开 WAL（就地更新的 B+Tree 同样要先写日志才能崩溃恢复）——WAL 不是 LSM 的专利，是「任何要先改页的引擎」的共同前提。给 ph23 的伏笔：向量库（Milvus 等）的文件层大量借鉴这两者的磁盘管理形态。

### 3.7 Buffer Pool：页缓存 / 命中率 / 脏页 / pin-unpin / LRU 与 Clock

Buffer Pool 是「把磁盘页缓存在内存帧里」的层，也是 ph21 练习 1 的 LRU 预告兑现点。**LRU 只是淘汰策略，页缓存还要回答三个追加问题**（examples/ex04 逐条实测）：

| 追加维度 | 内容 | 没有它会怎样 |
|---------|------|-------------|
| 脏页 dirty | 页在帧里被改写后标脏；淘汰/写回前必须落盘 | 改动只在内存帧里，进程一退就丢 |
| pin/unpin | 读页前 fix（引用计数 +1），用完必须 unfix；pin>0 的帧是淘汰禁区 | 正持着帧内指针改数据时被换页，写进别人家的页 |
| 帧与淘汰策略 | 帧数组定长、地址稳定；淘汰只发生在未钉帧 | 帧重分配/悬空引用 = use-after-free 级别灾难 |

```cpp
// examples/ex04-buffer-pool-lru-clock.cpp —— 帧与淘汰骨架（节选，已验证）
frame* fix(uint64_t id) {
    if (hit) { ++f.pins; f.ref = true; remove_from_lru(slot); return &f; }  // 命中即钉
    const size_t slot = pick_slot();          // 空槽优先，否则按策略淘汰未钉帧
    if (frames_[slot].dirty) disk.write(f.id, f.data);   // ★ 脏页写回
    ... load(id) -> f; index_[id]=slot;
}
```

**LRU 与 Clock 的差异是本节的实测主角**（ex04 场景 A，cap=4，同一访问序列）：

```text
LRU   淘汰序列: 4 号 miss -> 1, 5 号 miss -> 2    ← 精确按「最久未用」
Clock 淘汰序列: 4 号 miss -> 0, 5 号 miss -> 1    ← 刚访问过 0，却被先淘汰
```

Clock（二次机会算法）用一个引用位近似 LRU：扫描时针走到 ref=1 的帧只清位不给淘汰，ref=0 才淘汰——代价是**只给「一圈内的第二次机会」**：页 0 刚被访问、ref=1，但随后插入新页触发的扫描从帧 0 起立刻把它清位，转回它之前没有再次访问 → 照样被淘汰；LRU 靠精确顺序保住了它。为什么 Clock 仍然值得用：LRU 每次访问都要动链表（cache miss + 锁竞争），Clock 只需要一个位 + 周期扫描，命中路径便宜得多——**用一点淘汰精度换命中路径的常数额**。脏页写回与 pin 保护由 ex04 的 B1/B2 场景独立断言（脏页被淘汰时磁盘值正确、被钉页活过一轮淘汰）。

热集工作负载下两者命中率相当（ex04 场景 C 实测同为 114 hits/6 misses = 95%）——Clock 的误差在「访问模式稳定」时几乎不体现，在「访问突发 + 扫描恰逢其时」时现形。工程选择通常不是二选一：多数系统用 Clock/近似变体当主淘汰（命中路径便宜），配合显式 pin 保护长持有。**给 ph23 的伏笔**：向量库的 page cache 同样要「缓存命中/脏页/pin」这套——SSTable 部分见 ph22 project 的 reader「整文件读入内存」简化，接上本示例的帧缓存即真实形态。

**命中率是 Buffer Pool 的唯一 KPI**，其余一切设计（帧数、淘汰策略、预读）都为了它：`命中率 = hits / (hits + misses)`。工程里它分两档看：**逻辑命中率**（帧命中，省一次 read 系统调用）与**物理命中率**（落到 Page Cache 命中，省一次设备 IO，见 4.2）。提升路径从便宜到贵依次是：调大帧数（容量）、换更贴访问模式的淘汰策略（LRU/Clock/分层）、按访问模式显式预读/钉住。ex04 场景 C 的演示负载（固定 6 页热集、容量 8）把两策略都推到 95%——这告诉我们：**热集稳定时淘汰策略的差别被容量掩盖**，淘汰策略的价值在「冷热混合、容量紧张」时才显形。

### 3.8 Snapshot 与 MVCC 基础：版本链 / 可见性判断点到为止

前面所有组件都在回答「当前最新值是什么」；Snapshot/MVCC 把问题升级成「**在时刻 T 看来，值是什么**」——允许不同读者看到不同版本而互不阻塞。理解它的最小认知模型只有三句话（C++ 路线只到概念与点到为止的规则，完整事务隔离体系超出路线）：

1. **写不改旧、只添新**：每次更新/删除产生一条带版本号的新记录，旧记录留在原地——这正是 LSM tombstone 的远亲：**删除 = 写一条「已删」的新版本**，本阶段的 MemTable tombstone 已经是在用 MVCC 的「写新版本」心智。
2. **版本链**：同一 key 的多个版本按时间连成链，最新在链头。工程上 InnoDB 用 undo log 存旧版本、PostgreSQL 用堆内多版本；**LSM 的天然版本链就是「多层文件」**——同一 key 在不同代 SSTable 里的不同值就是一条物理版本链，本阶段 `get` 的「新层赢旧层」就是最朴素的可见性判断。
3. **可见性规则**：读操作带一个快照版本号 S，只认 `version ≤ S` 且「最新的那一条」；删除（tombstone）对 S 的可见性 = 「该版本是 tombstone → 看作不存在」。判断点到为止的三态返回（none/deleted/value）已经在 project/ 与 sol-05 里实现了——`get` 遇 deleted 立即判不存在、不再下探更旧层，就是「可见性判断」的引擎版。

```text
同一 key 的版本链（物理形态 = 多层文件，每层一条该 key 的记录）：
  更旧层 L3: k="v1" (seq=5)   ← 最老版本
  更旧层 L2: k="v2" (seq=9)   ← 后来覆盖
  更旧层 L1: k=DEL  (seq=12)  ← 删除标记（tombstone）
  最新层 L0: k="v3" (seq=15)  ← 删了又写？不——上面只是「链的可能形态」
  实际引擎 get("k") = 从 L0 往下找第一条 → 各层各有自己的结论；
  若 L0 有则取 L0（v3 覆盖一切）；L0 没有、L1 是 tombstone → 判不存在（不查 L2/L3）
```

把「多层文件」换成「同表多版本行」就是数据库的 MVCC 版本链——**LSM 只是把版本按时间物理分到了不同的代文件里，而 MVCC 把它们按时间串在一条链上**，判断规则同构：都是「从新往旧找第一个满足快照条件的版本」。

为什么数据库需要这套而非「读最新」：读写并发时，「读最新」要么让读者看到写到一半的状态（脏读），要么让写者等读者（互斥）。MVCC 让**每个读者各看各的快照**，写者永不阻塞读者。给 ph23 的伏笔：向量库的 metadata filter 与并发 upsert 同样要「版本可见性」来决定「这个向量在 T 时刻算不算数」。

> 完整隔离级别（读已提交/可重复读/串行化）、事务与 undo log 属于数据库理论（本路线未规划独立阶段）——**本阶段只需建立「多版本 + 按快照号选版本」的心智，并在引擎里看到 tombstone 就是它的最小实现**。

### 3.9 Iterator 抽象：连接 MemTable/SSTable 做 range scan（兑现 ph21 有序扫描预告）

roadmap 的 Iterator 愿景（§22 示例区即给出接口形态）：MemTable 与 SSTable 各自实现统一读面，上层 scan 不关心数据在内存还是磁盘。ph21 project 预告的有序扫描兑现点：skip_list 的 `begin()/end()/lower_bound()` 是单表读面，本阶段补上**多表归并**：

```cpp
// examples/ex05-iterator-range-scan.cpp —— 统一读面（节选，已验证）
class kv_iterator {
public:
    virtual ~kv_iterator() = default;
    virtual bool valid() const = 0;
    virtual void next() = 0;                        // 前提 valid()
    virtual void seek(std::string_view key) = 0;    // lower_bound：第一个 >= key
    virtual std::string_view key() const = 0;
    virtual std::string_view value() const = 0;
};
// mem_iterator 包 std::map（project/ 换成 ph21 skip_list，接口同款）
// sst_iterator 包有序文件（内部 lower_bound 定位 = 「索引定位块 → 块内顺扫」的抽象）
```

**merge_iterator（多路归并）每步做三件事**（ex05 [1] 实测全表扫描）：

```text
全表: apple=mem avocado=f1 banana=mem cherry=mem date=f2 fig=f1
      ↑ 同 key 三层都有值（apple 在 mem/f1/f2）→ 只保留序号最小（最新）源的值
```
① 跨源取 (key, 源序号) 最小者；② 同 key 的旧源直接跳过（新层赢旧层——这是「读一致性」在无锁下的实现）；③ 每次前进后重新选最小。`seek(key)` = 下界定位，是 range scan [lo, hi) 的入口——实测 seek 落在 gap 里时正确跳过小于 key 的全部数据。sol-05 再把 tombstone 语义并入归并层：**最新一份是删除标记 → 整个 key 从读面消失**（先前进所有同 key 源、再重新选），点查与 scan 共用同一套遮挡规则。

工程放大：真实引擎的 scan = 「MemTable 迭代器 + 每层一个 block 迭代器」的 k-way 堆归并（堆顶永远是最小 key 的提供者）；ph21 学的 priority_queue 在这里第二次上岗（第一次是 Dijkstra 懒删除）——**多路归并只是「堆顶是谁的最小值」**。project/ 用「旧 → 新」顺序把各层应用进有序结果（删除 erase、真实值覆盖）得到跨层一致的 range scan，自测 [3] 用 2 个 SSTable + 内存层验证了重启后与 ground truth 完全一致。

归并迭代器的骨架（无论堆版还是线性版，四条语义是硬约束，examples/ex05/sol-05 断言覆盖）：

```text
merge_iterator 语义清单：
  ① valid = 存在候选（不是"全部源都空"）
  ② next = 前进当前赢家 → 吞掉同 key 的更旧源 → 重新选最小
  ③ 同 key：序号最小（最新）的源赢，其余同 key 源在赢家输出时同步前进
  ④ 删除遮挡：若赢家是 tombstone，整个 key 消失——所有源的该 key 一起前进，继续选下一个
约束本质：输出序列必须严格有序、无重复、且每个 key 只来自「最新的活版本」
```

### 3.10 LevelDB/RocksDB 源码阅读引导：调用链 / 一个核心模块解剖

读源码不是从头读到尾，而是**沿一条调用链走到底、再解剖一个模块**。本阶段给你的最小阅读路径：

**写路径调用链（LevelDB，约 6 个文件就能讲清）**：
`DB::Put` → `DBImpl::Write`（写队列 + `Writer` 串行化）→ `Log::AddRecord`（WAL 追加，见 3.1 的 record）→ `MemTable::Add`（skip-list 插入，见 3.2）→ 后台 `DBImpl::MaybeScheduleCompaction` → `WriteLevel0Table`（把不可变 MemTable flush 成 SSTable，见 3.3）。**读路径调用链**：`DB::Get` → `DBImpl::Get` → `Version::Get`（自新层向旧层找）→ `TableCache::Get`（**每层先查 `FilterBlockReader::KeyMayMatch` 的 Bloom，见 3.4**）→ `Table::InternalGet`（index block 二分 → data block 定位）。**恢复路径调用链**：`DB::Open` → `DBImpl::Recover` → `VersionSet::Recover`（读 MANIFEST，本阶段未展开的元数据文件）→ `Log::Reader` 重放 WAL（见 3.1 的 replay）→ 重建 MemTable。

**建议解剖的第一个核心模块：`MemTable`（或它背后的 `SkipList`）**。为什么是它：① 你已经在本阶段手写/复用过一个 skip_list（ph21 project），代码能直接对上；② 它同时出现在写路径（Add）、读路径（Get 的第一站）、flush 路径（有序迭代）三条链里，解剖它 = 一次看懂三个调用点；③ 它的并发形态（RocksDB 的并发 MemTable / 无锁 skip-list）是「本阶段单线程版之后加什么」的标准答案。解剖时带着三个问题：`key 的编码里为什么带 sequence number`（那是 3.8 MVCC 可见性判断的载体——同 key 多版本按 seq 排序，最新在前）、`为什么用 comparator 而非 operator<`（接口可替换，为了 internal key 的比较规则）、`immutable MemTable 与 mutable MemTable 为什么是两个`（flush 期间写入不能停——写新表、旧表只读等 flush）。

> 阅读建议：先只读 LevelDB（代码量小、结构清晰）；再对比 RocksDB 同名文件看它加了什么（列族、合并算子、并发 flush）。**目标不是读完，而是能把「DB::Put 到 SSTable 落盘」这条链上的每个环节标出本阶段学过的概念**——对标第 7 章验收清单最后一条。

建议的阅读文件清单（拿本阶段概念当目录，10 个文件讲完一条主线）：

| LevelDB 文件 | 本阶段概念 | 重点看什么 |
|-------------|-----------|-----------|
| `db/write_batch.cc` | WAL + 批 | 一条 WriteBatch 如何序列化成连续 record（3.1） |
| `db/log_writer.cc` / `log_reader.cc` | WAL 读写 | record 的 CRC/长度前缀与 replay 的残尾处理（3.1） |
| `memtable.cc` | MemTable | key 编码（`internal key = user key + seq + type`）与 Add/Get（3.2/3.8） |
| `skiplist.h` | skip-list | 与本阶段 ph21 头文件对照，看生产版加了什么（3.2） |
| `table/table_builder.cc` | SSTable writer | data block → index block → footer 的落盘顺序（3.3） |
| `table/filter_block.cc` | Bloom | 位数组如何随文件布局（policy 与数据分离的设计）（3.4） |
| `table/block.cc` | block 解码 | restart 数组：稀疏索引的块内版（3.3） |
| `db/version_set.cc` | 分层与 Compaction | L0..Ln 与「新层赢旧层」的读路径（3.5/3.9） |
| `db/db_impl.cc` | 三路径总装 | Put/Get/Recover 调用链的入口（3.10 主线） |
| `db/table_cache.cc` | 页缓存 | 已打开 table 的 LRU 缓存（3.7 的工程形态） |

## 4. 底层原理

### 4.1 LSM 三种放大的数学直觉

三放大是 LSM 全部调参的度量衡，直觉比公式重要：

- **写放大 = 一次逻辑写最终在物理上被写了多少字节**。数据从 MemTable flush 进 L0，然后被 compaction 一层层往下搬，每层都可能把这条数据重写一遍。数学直觉：若每层容量比下层小 T 倍（leveled 的典型 T=10），数据大约要下移 O(log_T(总数据/单层)) 层，每层重写一次的期望就是 O(log N) 次重写——但 leveled 的常数很大（每层边界都要挑重叠文件重写），实测里更新密集负载写放大可达 ~20-30x；tiered 按「同尺寸批量归并」，每次归并摊薄重写次数，写放大更低，代价见下。examples/ex06 [3] 的简化对比（每次 flush 归并 13830B vs 攒 4 次归并 3817B）就是这条直觉的直译：**归并频率 × 历史长度 = 写放大的来源**。
- **读放大 = 一次逻辑读要碰多少个物理单位**。点查不存在或跨层数据：每层一个 SSTable 时读放大 = 层数（+ Bloom 挡掉大部分数据区 IO）；tiered 一层多个 run 时读放大随 run 数线性涨——所以 **Bloom 是读放大的第一道止损**（ex03 实测 99% 不存在查询零数据区 IO），**compaction 是第二道**（把多层并为单层后读放大归 1）。
- **空间放大 = 物理占用 / 逻辑有效数据**。重复更新留下的旧版本、tombstone、等待合并的大 run 都在占空间（ex06 实测 3 run 物理 92B vs 有效 31B ≈ 2.97x）。空间放大只靠 compaction 收——所以 tombstone 堆积和更新密集的 key 会让空间涨到不可忽视，这是 LSM 运维的第一课。

三者不是独立旋钮：**调低写放大（少归并）→ 读放大与空间放大上升；调低读/空间放大（勤归并）→ 写放大上升**。LevelDB/RocksDB 的全部触发参数都是在这个三角形上选点。

### 4.2 页缓存与 OS 页缓存的两层关系

「Buffer Pool 缓存页」和「OS 也在缓存页」是两层缓存，搞混它们会得出错误性能结论。第一层：**应用 Buffer Pool**（本阶段 3.7 的帧缓存）——管「逻辑页号 → 内存帧」，淘汰策略是应用自己的 LRU/Clock，写回时机是应用自己的脏页规则。第二层：**OS Page Cache**——应用 `read()/write()` 后数据先进内核页缓存，`fsync` 才真正推向存储设备。两层关系：

```text
应用 Buffer Pool（帧，页粒度） ──read/write──▶ 内核 Page Cache ──fsync──▶ 存储设备
        │ 命中：零系统调用                    │ 命中：零设备 IO
        │ miss：一次 read/write（落 Page Cache）│ fsync：真正落盘点
```

三个必须内化的推论：① **Buffer Pool miss ≠ 磁盘 IO**——第一次读页可能只是从 Page Cache 复制进帧，真正的设备 IO 发生在 Page Cache miss 时；所以「缓存命中率」要分两层看。② **Buffer Pool 的脏页写回 ≠ 持久化**——write() 只把脏页推进 Page Cache，崩溃仍然会丢（数据在 OS 内存里）；**持久化承诺的边界是 fsync**，这正是 WAL 为什么必须 fsync 而不是「write 完就算」（3.1 的第二条纪律）。③ **两层淘汰是竞争关系**：应用 Buffer Pool 用 LRU 把某页留在帧里，OS 可能早就把它从 Page Cache 挤出去了——所以对「读后即弃」的大扫描，刻意绕过应用缓存（O_DIRECT）反而省掉一层复制；对热数据，两层命中叠加才是理想。工程简化（本阶段所有 reader 注明）：整文件读入内存 ≈ 显式利用了 Page Cache 后的一次性物化，教学重点在应用层偏移逻辑而非 IO 调度——mmap/Page Cache 的系统级展开在 C 路线 ph13 更完整。

### 4.3 WAL fsync 与组提交

fsync 是「可承诺」的边界，也是写入吞吐的第一杀手。物理机制：一次 fsync 的耗时主要是「把内核脏页刷到设备 + 等待设备确认」的固定往返，与写多少字节几乎无关——所以**摊薄 fsync 的唯一办法是减少次数，不是减少每次的量**。C 路线 ph16 在 C 版 ex02 实测过：结尾一次 fsync 与每条都 fsync 相差约 11~18 倍（本阶段不重复测，引用其数据并注明）。工程解法是**组提交（group commit）**：

```text
无组提交：   写1 →fsync→ 写2 →fsync→ 写3 →fsync→ ...     每条付一次固定往返
组提交：     写1 写2 写3 攒批 ──▶ 一次 fsync ◀── 写4 写5 写6 攒批
          代价：单条延迟变大（要等组齐），但吞吐=一次固定往返摊 N 条
```

WAL 为什么能组提交而不破坏恢复语义：replay 是「整日志重放」，一组记录要么整组 fsync 成功、要么整组在崩溃时变残尾被截断——**没有「组中间成功」的状态需要区分**，因为恢复只看 fsync 过的前缀。本阶段的代码里处处体现这条边界：ex01 的 `append_sync` 是单条同步的教学形态，exercises/sol-01 把 `append` 与 `fsync_all` 拆开让调用方攒批（注释指明这就是 group commit 雏形），project/ 的引擎保持逐条 append_sync 以把语义做对——**把语义做对之后，把「每次 put 都 fsync」改成「定时/攒批 fsync」是一行代码的事，顺序不能反过来**。macOS 上 fsync 只到设备缓存、真落盘要 `F_FULLFSYNC` 的细节属于 C 路线 ph13 的范畴，本阶段不展开。

## 5. 使用场景

**KV 存储引擎工程落点**——本阶段组件各自回答一个真实问题：

| 场景 | 用什么 | 依据 |
|------|--------|------|
| 任何需要崩溃恢复的嵌入式写入（配置库、队列、时序缓冲） | WAL（先写日志再改状态） | 崩溃最多丢最后一条残记录，replay 重建（3.1/project [2]） |
| 写多读多的 KV / 本地缓存 / 日志类存储 | LSM：WAL + MemTable + SSTable + Bloom | 随机写转顺序写；project/ Mini LSM KV 即最小可用版 |
| 点查「不存在」的 key 很多 | Bloom Filter 挡每层 | 实测 99% 不存在查询零数据区 IO（3.4/ex03） |
| 数据量超过内存的页式访问 | Buffer Pool + LRU/Clock | 命中/脏页/pin 语义齐全才能当引擎缓存（3.7/ex04） |
| 读多写少、范围/点查明确 | B+Tree 而非 LSM | 读路径确定、页级就地更新（3.6 对照表） |
| 后台整理、空间回收 | Compaction（触发频率是调参） | 归并丢旧值/真删 tombstone；三放大权衡（3.5/ex06） |
| 范围导出、跨层一致性读 | Iterator 抽象 + 多源归并 | MemTable/SSTable 统一读面、新层赢旧层（3.9/ex05） |
| 并发读写一致性 | Snapshot/MVCC 心智 | tombstone 即「删除 = 新版本」的最小实现（3.8） |

**不适合**的场景：强事务/多语句原子性（WAL 只做单条 redo，undo 与隔离完整体系超出本路线）；内存装得下的极低延迟点查（直接哈希表/全内存结构，别碰磁盘层）；更新集中且空间敏感（LSM 空间放大失控，选 B+Tree 或调高归并频率）；多线程高并发写入（本阶段单线程——并发 MemTable 与并行 compaction 属工程进阶，源码阅读引导已指出方向）。

**跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）：

| 维度 | C++（本阶段） | Go | Rust |
|------|--------------|-----|------|
| 代表实现 | RocksDB / LevelDB | Badger（bbolt 为 B+Tree） | sled（log-structured） |
| 所有权/资源 | RAII + unique_ptr；页/文件/记录全显式 | GC 管理内存，RWMutex 管共享 | 借用检查器静态保证无悬空；无锁结构用 unsafe 收口 |
| 内存布局 | vector/帧数组/位数组，零隐式拷贝 | slice/结构体；GC 会搬对象 | 与 C++ 同级直控（Vec/Box） |
| 抽象成本 | 迭代器/多态少量虚函数；hot path 可控 | interface 有间接调用成本 | trait 泛型单态化，接近零成本 |
| 磁盘纪律 | 大端 + 定宽类型手工摆（与 C 路线同纪律） | encoding/binary 显式 | byteorder crate；同样手工 |
| 谁更适合 | 要极致控制与工业生态（RocksDB 体量） | 交付快、与云原生 Go 栈同语言 | 要内存安全又不要 GC 停顿（sled 定位） |

三条观察：① **存储引擎是三门语言里最像 C 的领域**——GC 语言（Go）在这里要付「GC 停顿 + 对象移动」的代价，所以 Badger 用 value log + 值外置减少 GC 压力；② Rust 的 sled 与 C++ 分享同一份心智（log-structured、immutable segment、分代回收），但把「引用不能悬空」变成编译期事实——这正是 storage 这类长生命周期、结构间互相引用的代码里最容易翻车的地方；③ 给 Tenet 的启示：如果 Tenet 想服务存储/AI 地基，**「所有权」必须是语言级而非约定级**，同时保留 C++/Rust 式的布局直控与「无 GC 可选路径」。

**与 C 版 ph16 的分工视角**（任务要求注明）：C 路线的 ph16 也实现了一台 mini LSM（lsmkv），主题高度相近但两者的教学分工不同——**C 版把存储引擎当作 C 路线终点**：全部结构（位数组、链表、文件布局）手工摆内存，主线是 ph12/ph13 累积的「字节序/varint/可靠落盘」纪律如何收口成一台引擎，强调零抽象税与每字节去向的掌控；**本阶段（C++ ph22）把存储引擎当作 C++ 路线中段的「地基转折」**：复用 ph21 的结构资产（skip_list 直接搬进 project、Bloom/LRU 由 ph21 的结构认知升级成引擎模块）、用 RAII 与容器管资源、用 Iterator/多态收口「跨内存跨磁盘」的读面，主线是「ph21 的内存结构如何长成 ph22 的引擎模块、并继续作为 ph23 存储/AI 地基」——同样的 record 布局、同样的 tombstone 语义、同样的大端纪律，保证跨语言可对照；差异在代码形态与阶段定位，不在主题结论。

## 6. 代码示例

> 完整可运行文件在 [`examples/`](./examples/)，构建/运行命令与逐文件教学点见其 README；**全部 6 个示例已在 Apple clang 21.0.0 下 `clang++ -std=c++20 -Wall -Wextra` 编译零警告、运行断言全绿**（ex03/ex04 另过 Homebrew clang 21.1.8）。通用命令：`clang++ -std=c++20 -Wall -Wextra exNN-<名>.cpp -o /tmp/ph22-exNN && /tmp/ph22-exNN`（产物一律在 /tmp）。以下给出示例与主文档小节的映射及关键实测输出。

| 示例文件 | 对应小节 | 实测输出关键行（本环境运行） |
|---------|---------|------------------------------|
| `ex01-wal-append-replay.cpp` | 3.1/3.2 | 3 条追加 replay 全对；残尾偏移 73 修复后可续写；翻转字节 torn=23 |
| `ex02-mini-sstable.cpp` | 3.3 | 232 字节 / 3 块；跨块与末块命中；`get("aaa")` 零数据区扫描 |
| `ex03-bloom-filter.cpp` | 3.4 | k=7 实测 0.774% vs 理论 0.819%；k=4/7/10 曲线贴合；99.04% 拦截 |
| `ex04-buffer-pool-lru-clock.cpp` | 3.7 | LRU 淘汰 {1,2} vs Clock {0,1}；热集 95% 命中；脏页写回/pin 保护断言 |
| `ex05-iterator-range-scan.cpp` | 3.9 | 全表合并去重新赢旧；seek 落 gap 正确跳过 |
| `ex06-compaction-sim.cpp` | 3.5/4.1 | 92B→31B、覆盖 3 + 真删 1；tombstone 保留断言；13830 vs 3817 字节 |

```cpp
// examples/ex01-wal-append-replay.cpp —— replay 校验链（节选，已验证）
// 验证环境：Apple clang 21.0.0；命令见文件头
if (get_u32be(hdr.data()) != k_magic) { *torn_at = pos; break; }   // 2. magic
if (klen > k_max_kv || vlen > k_max_kv || klen + vlen > k_max_kv)  // 3. 联合上限
    { *torn_at = pos; break; }
if (crc32(check.data(), check.size()) != expect)                   // 4. CRC
    { *torn_at = pos; break; }
```

exercises/ 的 5 题参考实现与 project/（Mini LSM KV）同样全绿：练习参考实现双编译器验证（`sol-01` WAL replay / `sol-02` block header + 校验 / `sol-03` SSTable+Bloom 拦截计量 99.25% / `sol-04` 页帧 LRU / `sol-05` 带删除遮挡的归并）；project `make test` 323 项断言全绿，ASan/UBSan 零报告。全部代码遵循 cpp-coding-standards：文件描述符 RAII 封装（`fd_file`）、无裸 new/delete、`const`/`enum class` 默认、教学性简化以注释注明。

## 7. 总结

### 关键要点

1. **WAL = 先写意图再改状态**：record = magic/type/长度前缀/CRC（大端）；append 返回 ≠ 持久化，fsync 才是承诺边界；replay 四道校验后停在残尾，ftruncate 修复即继续（3.1）
2. **删除是写入不是擦除**：MemTable/SSTable 里删除 = tombstone 记录；Bloom 里必须包含已删 key，否则删除被误拦、旧值复活（3.2/3.4）
3. **SSTable 不可变是设计核心**：免锁读、崩溃安全、可放心缓存；稀疏索引（块首 key → 块起点偏移）是空间/速度的平衡（3.3，索引记块尾是真实踩过的 bug）
4. **Bloom 的概率承诺**：无假阴性 + 可控假阳性；**m 取素数**（偶数 m 双哈希聚集，实测 4.06% vs 理论 0.82%）；k 最优点 ≈ (m/n)·ln2（3.4）
5. **Compaction 一次做三件事**：丢覆盖旧值、tombstone 到底才真删、数据变紧凑；非底层归并必须保留 tombstone（3.5/ex06）
6. **三放大是 LSM 的成本语言**：写放大来自历史被反复重写、读放大来自跨层探测、空间放大靠 compaction 收；三个旋钮互相牵制（4.1）
7. **Buffer Pool = LRU 淘汰 + 脏页写回 + pin 禁区**；Clock 用引用位近似 LRU，只给「一圈内第二次机会」，命中路径便宜（3.7/ex04）
8. **MVCC 最小模型 = 写新版本 + 按快照选版本**：LSM 的多层文件就是物理版本链，tombstone 就是「删除 = 新版本」的最小实现（3.8）
9. **Iterator 让内存与磁盘长同一张脸**：多源归并每步取最小、同 key 新赢旧；删除遮挡由「最新一份是 tombstone 则整 key 消失」表达（3.9/sol-05）
10. **读源码沿调用链走**：Put→WAL→MemTable→flush→SSTable、Get→Bloom→index→block、Open→replay——每条链都是本阶段学过的概念（3.10）

### 阶段验收清单

- [ ] 能解释 WAL、MemTable、SSTable、Compaction 的关系并画出写/读/恢复三条路径（3.1~3.5）
- [ ] 能通过 WAL 恢复 put/del：replay 四道校验、残尾识别与 ftruncate 修复、修复后日志可续写（3.1/练习 1）
- [ ] 能按 key 查询 SSTable：footer → 稀疏索引二分 → 块内顺扫；说出「不可变」的三个好处；设计 block header 并加校验（3.3/练习 2）
- [ ] 能给 SSTable 加 Bloom：无假阴性、假阳性可控（素数位数组 + m 精确持久化）、拦截计数可测（3.4/练习 3）
- [ ] 能实现 LRU 并升级为页帧缓存：命中即提前、脏页写回、pin 保护（3.7/练习 4）
- [ ] 能用 Iterator 抽象串 MemTable 与 SSTable 做 range scan：跨层一致、删除遮挡、seek 下界语义（3.9/练习 5）
- [ ] 能解释 LSM 的读放大、写放大、空间放大各自来源与对症手段（4.1）
- [ ] 能说明 B+Tree 与 LSM 的适用场景差异（3.6）
- [ ] 能读懂 LevelDB 至少一个核心模块（建议 MemTable）的调用链，并把每环标上本阶段概念（3.10）
- [ ] 能把 WAL + MemTable + SSTable + Bloom 串成 mini KV：重启后 WAL replay 恢复、range scan 跨层一致、ASan 零报告（project/）

### 跨语言对比

见第 5 节末对照表。给 analysis/ 与 Tenet 合成的启示：**存储引擎是「内存安全最难、抽象税最敏感」的领域**——C++ 用纪律（RAII + 显式所有权约定）换零抽象税，Rust 用类型系统把约定变事实，Go 用 GC 换掉手工管理但付出停顿与对象移动的代价；本阶段所有「读面不拷贝」（string_view）、「所有权清楚」（unique_ptr 组件）、「无 GC 可选」的写法，都是为这条权衡提供 C++ 侧的样本。若 Tenet 想成为存储/AI 地基语言，LRU 与页缓存这类「既要有序又不许悬空」的结构应该享受语言级支持而非手动再实现一遍（ph21 跨语言对比已埋过同款伏笔）。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看），共 5 题，与 roadmap §22「练习」小节一一对应：append-only WAL 写入与 replay（练习 1）/ SSTable block header + writer/reader（练习 2）/ 为 SSTable 增加 Bloom Filter（练习 3）/ LRU Cache 升级页帧缓存（练习 4）/ Iterator 抽象 range scan（练习 5）。卡住时回看 examples/ 对应文件的手法。完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**Mini LSM KV**——roadmap §22 推荐项目取「Mini LSM KV」（另五个推荐项目的去向见 project/README：Mini WAL、Mini SSTable、Buffer Pool toy 已分别由 examples/ex01/ex02/ex04 与练习 1/2/4 落地，简化 B+Tree 属 3.6 概念对照，LevelDB 源码分析见 3.10 阅读引导）：WAL + MemTable（**复用 ph21 project 的 skip_list.h，复制进 project/ 并注明来源**）+ SSTable（内嵌 Bloom）串成可重启恢复的 mini KV，`make test` 4 组场景 323 项断言覆盖写/读/恢复路径、自动 flush、tombstone 跨层遮挡与 Bloom 拦截计数，`make cross`/`make sanitize` 全绿。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`make clean && make test` 退出码 0、ASan/UBSan 零报告、`make clean` 零残留）

### 下一阶段

**ph23 向量检索与 AI 推理引擎方向 C++（roadmap 第 23 节，目录待建）** — 本阶段把「磁盘页与缓存管理、不可变文件、版本可见性」的地基打好后，ph23 把这些心智平移到向量库与推理服务：距离计算与 SIMD、HNSW/IVF/PQ 的图索引与量化、向量索引持久化（直接复用本阶段 SSTable/Buffer Pool 的磁盘形态）、Faiss 阅读、以及 KV Cache/batching/serving 里的缓存与内存布局问题——ph21 预告 HNSW 无 STL 等价物、ph22 预告「向量索引持久化需要存储地基」，两个预告在 ph23 汇合。




