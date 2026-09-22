# examples —— C++ 存储引擎与数据库内核专项阶段完整示例

验证环境（实测）：macOS arm64，Apple clang 21.0.0（`/usr/bin/clang++`，默认 PATH）+ Homebrew clang 21.1.8（`/opt/homebrew/opt/llvm/bin/clang++`，交叉核对）、libc++。**全部 6 个示例均已在本环境 `clang++ -std=c++20 -Wall -Wextra` 编译零警告、运行断言全绿（退出码 0）**；其中 ex01/ex03/ex04 另做 Homebrew clang 21.1.8 交叉编译核对（零警告，抽查运行退出码 0）。以下命令在 examples/ 目录内执行；可执行文件一律输出到 /tmp，数据文件一律写 /tmp 且退出时自删，仓库不落二进制。

代码遵循 cpp-coding-standards：文件描述符用 RAII 封装（`fd_file`）、无裸 new/delete（R.11，容器与 `unique_ptr` 拥有资源）、`const`/`enum class` 默认、教学性简化均以注释注明。

| 文件 | 对应主文档 | 一句话内容 | 验证状态 |
|------|-----------|-----------|----------|
| `ex01-wal-append-replay.cpp` | 3.1/3.2 | WAL：record 布局（magic/type/长度前缀/CRC32）+ append-only 追加/fsync + replay 四道校验 + 残尾 ftruncate 修复 | 已验证（Apple clang 21.0.0） |
| `ex02-mini-sstable.cpp` | 3.3 | Mini SSTable：数据块（klen/vlen + key/value）+ 稀疏索引（块首 key → 块偏移）+ 定长 footer，点查三步路径 | 已验证（Apple clang 21.0.0） |
| `ex03-bloom-filter.cpp` | 3.4 | Bloom Filter：位数组 + FNV-1a 双哈希；无假阴性、假阳性率实测 vs 理论、k 最优曲线 | 已验证（Apple clang 21.0.0 与 Homebrew clang 21.1.8） |
| `ex04-buffer-pool-lru-clock.cpp` | 3.7 | Buffer Pool：页帧 + 命中/脏页写回/pin-unpin；LRU 与 Clock 淘汰对比（近似误差实测演示） | 已验证（Apple clang 21.0.0 与 Homebrew clang 21.1.8） |
| `ex05-iterator-range-scan.cpp` | 3.9 | Iterator 抽象：MemTable（std::map 站位，project 换 skip_list）与 SSTable 统一读面 + 多源归并 range scan，新层赢旧层 | 已验证（Apple clang 21.0.0） |
| `ex06-compaction-sim.cpp` | 3.5/4.1 | Compaction 模拟：多 run 归并（覆盖丢弃 + tombstone 语义）+ 读/写/空间三放大计量 + 归并节奏对比 | 已验证（Apple clang 21.0.0） |

## 统一编译运行命令

```bash
# 在 examples/ 目录内执行（产物一律输出到 /tmp）：
clang++ -std=c++20 -Wall -Wextra ex01-wal-append-replay.cpp -o /tmp/ph22-ex01 && /tmp/ph22-ex01
# 其余示例把 ex01-wal-append-replay / /tmp/ph22-ex01 替换为对应文件名与输出名即可。
# 每个示例文件头注释里都带它自己的编译运行命令与验证状态。
```

## 示例 1：WAL append + replay（ex01-wal-append-replay.cpp）

对应主文档 3.1/3.2 与 roadmap 练习「append-only WAL 写入与 replay」。教学点：① record 布局四要素（magic 识别垃圾数据、type 表达 PUT/DEL、klen/vlen 长度前缀让 replay 能跳读、CRC 拦损坏），多字节字段显式大端；② append 返回 ≠ 持久化——fsync 才算落盘（macOS 真落盘需 `F_FULLFSYNC`，本示例用 fsync 演示，见注释）；③ replay 校验顺序是「长度够 → magic 对 → 联合长度上限 → CRC 吻合」，任一失败停在残尾并报告偏移，`ftruncate` 修复后还能继续追加；④ CRC 覆盖 magic 之后的整段——replay 端校验范围必须与编码端完全一致（本项目开发时曾在此栽跟头，已在代码注释标出）。实测输出见主文档 6 节。

## 示例 2：Mini SSTable（ex02-mini-sstable.cpp）

对应主文档 3.3 与 roadmap 练习「Mini SSTable writer/reader」。教学点：① SSTable 的不可变性是设计核心——一次写出、只读不改，免锁读 + 崩溃安全 + 可放心缓存；② 布局三分区：数据区（block 内 entry 按 key 升序）、索引区（每块 1 条「块首 key + 块偏移」，稀疏索引可整体载入内存二分）、定长 footer（从文件尾直接定位）；③ 点查三步：读 footer → 索引二分找「最后一个块首 key ≤ 目标」的块 → 块内顺扫 ≤ 4 条，比最小 key 还小的查询零数据区扫描（实测断言 `e2 == 0`）；④ 教学简化注明：整文件读入内存模拟缓存形态，真实引擎走 mmap/页缓存 + Buffer Pool。

## 示例 3：Bloom Filter（ex03-bloom-filter.cpp）

对应主文档 3.4 与 roadmap 练习「为 SSTable 增加 Bloom Filter」的过滤器本体。教学点：① 概率语义：无假阴性、有可控假阳性——「说不在就一定不在」是它敢挡磁盘 IO 的根据；② 双哈希法：`(h1 + i·h2) mod m` 用两个基哈希组合出 k 个位位置；③ **m 必须取素数**（或 2 的幂 + 强制 h2 奇数）——本示例开发时用偶数 m 实测假阳性率 4.06% vs 理论 0.82%（双哈希位置奇偶聚集），换素数 m=100003 后 0.774% vs 理论 0.819% 基本吻合，k=4/7/10 的曲线也贴合理论——这是「实现细节决定理论是否成立」的活教材；④ 假阳性率 ≈ `(1-e^(-kn/m))^k`，k 最优点 ≈ `(m/n)·ln2`；⑤ 点查路径集成效果：5000 次不存在查询 99% 被拦截。

## 示例 4：Buffer Pool：LRU vs Clock（ex04-buffer-pool-lru-clock.cpp）

对应主文档 3.7 与 roadmap 练习「LRU Cache」的页缓存形态。教学点：① 升级 ph21 的 LRU：加 `dirty` 脏页位（淘汰前写回）、`pins` pin/unpin（被钉页是淘汰禁区）、页与磁盘交换；② LRU 精确记「未钉帧」的最近使用顺序（list 头=最近），Clock 用环形扫描 + 引用位近似 LRU；③ **实测分歧**：同一访问序列 LRU 淘汰 {1,2}，Clock 淘汰 {0,1}——刚访问过的页 0 因引用位在扫描第一圈被清、转回来前没再被访问，照样被淘汰；LRU 保住了它。Clock 的误差与省维护代价是 4.2 的讨论素材；④ 脏页写回与 pin 保护各自由独立场景断言（B1/B2）。

## 示例 5：Iterator 抽象 + range scan（ex05-iterator-range-scan.cpp）

对应主文档 3.9 与 roadmap 练习「用 Iterator 抽象 MemTable 和 SSTable 的 range scan」。教学点：① `kv_iterator` 接口（Valid/Next/Seek/Key/Value）让内存有序结构与磁盘有序文件露出同一张读面，scan 执行器不关心数据来源；② `mem_iterator` 包 `std::map` 迭代器（ph22 project 换成 ph21 的 `skip_list_map`，接口同款），`sst_iterator` 把文件解析为有序数组用 `lower_bound` seek；③ `merge_iterator` 多路归并：每步取 (key, 源序号) 最小者，同 key 旧源直接跳过——「新层赢旧层」；④ `seek(key)` = lower_bound，是 range scan [lo, hi) 的入口（实测 seek 落在 gap 里时正确跳过小于 key 的所有数据）。

## 示例 6：Compaction 模拟（ex06-compaction-sim.cpp）

对应主文档 3.5/4.1 与 roadmap 学习内容「Compaction、三种放大」。教学点：① 归并一次做三件事：同 key 旧值被新值覆盖丢掉、tombstone 到底层才真删、数据变紧凑；② **tombstone 语义**：非底层归并必须保留删除标记（否则更老 run 里的旧值复活），只有 full compaction 能真删；③ 三放大实测：点查不存在的 key 从探测 3 个 run 变 1 个（读放大 3→1）、物理 92B/有效 31B（空间放大 ≈ 2.97x）；④ 归并节奏 vs 写放大：每次 flush 都归并 13830B vs 攒 4 次归并 3817B——攒批少重写旧历史，写放大更低，代价是未归并前读放大上升（触发策略是调参，见主文档 3.5）。

## 验证状态汇总

| 示例 | 工具链 | 状态 |
|------|--------|------|
| ex01-wal-append-replay | Apple clang 21.0.0（+ Homebrew clang 21.1.8 交叉编译零警告） | 已验证（零警告、断言全绿、退出码 0） |
| ex02-mini-sstable | Apple clang 21.0.0（+ Homebrew clang 21.1.8 交叉编译零警告） | 已验证 |
| ex03-bloom-filter | Apple clang 21.0.0 + Homebrew clang 21.1.8 | 已验证（双编译器） |
| ex04-buffer-pool-lru-clock | Apple clang 21.0.0 + Homebrew clang 21.1.8 | 已验证（双编译器） |
| ex05-iterator-range-scan | Apple clang 21.0.0（+ Homebrew clang 21.1.8 交叉编译零警告） | 已验证 |
| ex06-compaction-sim | Apple clang 21.0.0（+ Homebrew clang 21.1.8 交叉编译零警告） | 已验证 |
