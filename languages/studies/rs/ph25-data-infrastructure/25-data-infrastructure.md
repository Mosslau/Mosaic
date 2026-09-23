# Rust 数据基础设施专项阶段

> 面向 KV / LSM 存储、Raft 一致性、向量检索与 Agent 工具后端的方向：把 WAL append/replay 与崩溃恢复、MemTable、SSTable + Bloom Filter、Compaction、Snapshot 与 MVCC 简化模型、Mini Raft 单节点日志复制状态机、HNSW 向量检索基础、Axum/Tonic 数据服务、pyo3 Python 加速模块、Agent 工具后端（权限 / 超时 / 审计 / 可观测）织成一张「**安全可信的数据基础设施**」能力网——它是 Rust 学习路线（roadmap 第 25 节，即最后一节）的收官阶段，ph01~ph24 攒下的所有权、错误处理、并发、字节解析、性能、FFI、供应链手艺在这里全部上场。

## 1. 概述

本阶段对应 roadmap 第 25 节，是整个 **Rust 学习路线的终点**：ph19 把「字节解析纪律」交给了我们，ph21 把「fmt/clippy/test 的质量门禁与 CI 模板」立了起来，ph23 把「FFI 的 unsafe 审查纪律」止步在 soundness 前提层，ph24 刚把「依赖、许可、漏洞、SBOM、可复现构建」织成一条发布流水线——**ph25 不再学新语法，而是把这些手艺组合成数据基础设施组件**：先写日志再改内存（WAL + MemTable），满了落成不可变有序文件并挂 Bloom（SSTable），后台归并整理（Compaction），让状态机在崩溃后能重放（Mini Raft 单节点形态），再把向量检索的图索引 toy 跑成可测数字（HNSW），最后用 HTTP/工具 API 把它们暴露出去（Axum + Agent 工具），并用 pyo3 让 Python 也能吃到 Rust 的热路径。

| 核心维度 | 覆盖内容 |
|----------|---------|
| WAL append / replay | 先日志后内存、append 与 fsync 的边界、重放四道校验、残尾（torn tail）截断修复（3.1） |
| MemTable | 内存有序表做写缓冲；BTreeMap 实现 vs C++ Skip List 的取舍；tombstone 删除语义（3.2） |
| SSTable | 不可变有序文件、block 内升序 entry、稀疏索引（块首 key → 偏移）、writer/reader（3.3） |
| Bloom Filter | 位数组 + 双散列、无假阴性 / 可控假阳性、挂进点查路径的拦截计量（3.4） |
| Compaction | 归并语义（覆盖丢弃 / tombstone 到底才真删）、leveled 思想、读 / 写 / 空间三放大（3.5） |
| Snapshot / MVCC 简化 | 读快照、版本可见性、删除 = 新版本——点到为止的概念层（3.6） |
| Mini Raft | 单节点日志复制状态机（term/index、commit→apply、崩溃重放）；选举概念（3.7） |
| HNSW 向量检索 | 分层小世界图、贪婪下探 + 宽搜、recall / QPS / P95 / 内存四件套实测（3.8） |
| Axum / Tonic 数据服务 | HTTP 暴露 KV / range-scan：路由、状态共享、统一 JSON 错误、超时语义（3.9） |
| pyo3 加速模块 | 把字节解析 / 向量距离暴露给 Python：abi3、错误边界、热路径（3.10） |
| Agent 工具后端 | Tool 抽象、scope 权限、超时预算、审计日志、可观测计数（3.11） |
| 底层原理 | LSM 三放大直觉、WAL fsync 与组提交、Raft 日志一致性直觉、Bloom 假阳性率推导（4） |
| 场景与练习 | 数据基础设施真实落点 + 与 C/C++/Go 生态对照；examples/exercises/project 四层配套（5~7） |

**边界声明（本阶段定位）**：这个阶段只涉及**单机、单进程内可验证的数据基础设施组件与它们的安全组合纪律**（WAL 崩溃恢复、内存有序表、不可变有序文件 + Bloom、compaction 归并语义、快照 / MVCC 的概念点到、单节点 Raft 状态机、HNSW toy、Axum 数据服务、pyo3 模块、Agent 工具边界），**不涉及**以下内容——它们要么属于后续可深入方向、要么已在更早阶段讲透：

- **分布式共识的生产级实现**：本阶段 Mini Raft 只到「单节点日志复制状态机 + 选举概念」——真多节点的 RPC（RequestVote / AppendEntries）、quorum 判定、leader 切换、PreVote、log matching 的完整工程（快照安装、流式复制）不做；Raft 生产化是**后续可深入方向**而非编号阶段；
- **向量库工业级工程**：HNSW 只做 toy——量化训练（PQ/SQ）、启发式邻居选择、并发写入、持久化格式、多副本不在本阶段；工业向量库工程是后续方向；
- **Agent 框架层**：本阶段只做**工具后端的边界**（Tool trait、权限、超时、审计、可观测），不做 Agent 编排、规划、记忆、LLM 调用那一层；
- **ph19 已讲透的字节解析细节**：record 的魔数 / 长度前缀 / CRC 的逐字节写法、`get` 区间检查与 `try_into`、零拷贝借用，本阶段直接「使用」并只从「解析纪律如何服务引擎层」的视角引用，不重讲；
- **ph24 已讲透的供应链流水线细节**：cargo audit / deny 的配置语法、SBOM、可复现构建的验证方法——本阶段**直接复用 ph24 沉淀的 deny.toml 与 release-check.sh 形态**（project/ 已复制并注明来源），只从「把门禁接进组件工程」的角度说明。

roadmap 第 25 节的「阶段验收」是一份可执行的对账表，本阶段的四层交付物逐条给出落点：

| roadmap 阶段验收 | 交付物落点 |
|-----------------|-----------|
| 能通过 WAL 恢复 put / delete 操作 | ex01（三场景）+ sol-01（engine open 重放）+ project smoke「重启恢复」段 |
| 能按 key 查询 SSTable | ex02 / sol-02（get + Bloom 拦截断言） |
| 能完成基础 range scan | ex02 scan + project `/kv?start=&end=` 实测 count:2 |
| 能解释 LSM 的读放大、写放大和空间放大 | 3.5 / 4.1（ex03 实测 13767 B vs 3809 B） |
| 能解释 Raft 的 leader election 和 log replication | 3.7（单节点实测 + 多节点概念流程） |
| 能输出向量检索 recall、QPS、P95 延迟和内存占用 | ex05（recall 0.831 / QPS / P95 / mem）+ sol-04 |
| 能设计可被 Agent 调用的稳定工具 API | 3.11 / ex08 / project 工具四件套 |
| 能构建 Python 调用 Rust 的加速模块 | ex07（pyo3 0.23.5 + verify.py 实测） |

roadmap 的「必会概念」逐条对应到正文位置（学完应能自指）：

| roadmap 必会概念 | 落点 |
|-----------------|------|
| WAL 用于崩溃恢复 | 3.1（append/fsync/replay/torn tail）+ ex01/sol-01 |
| SSTable 是不可变有序文件 | 3.3（不可变 ⇒ 共享安全）+ ex02 |
| LSM 通过顺序写提升写入吞吐，但会引入 compaction 成本 | 3.2/3.5 + 4.1 的三放大量化 |
| Raft 通过日志复制保证多副本状态一致 | 3.7（单节点状态机 + 复制概念） |
| HNSW 用图结构提升近似最近邻搜索效率 | 3.8/4.5（为什么跳得快 + 复杂度视角） |
| Rust 的所有权模型适合封装安全的存储和并发抽象 | 贯穿：3.3「不可变的类型投影」、3.5 归并的所有权交接、3.11 工具边界 |
| Agent 工具后端要关注权限、超时、审计和可观测性 | 3.11（四件套 + 调用链旅程图）+ ex08 |

**收官性质说明**：roadmap 第 25 节即本路线最后一节（其后只有「附录：阶段性项目验收标准」这一非编号章节与语言对比/项目路线/推荐路线，均不构成 ph26）——本阶段主文档第 7 章以终点声明收尾；「下一阶段」小节按仓库惯例保留，内容写「后续可深入方向不另设编号阶段」。ph01~ph25 全链收官后，Rust 在 TenetLang 仓库的能力弧线是「从写得出安全程序 → 到把数据做成跨崩溃、可检索、可服务、可信赖的组件」。

上一阶段预告在本阶段的兑现，就是本阶段的验收骨架：

| 预告来源 | 预告点 | 兑现位置 |
|---------|--------|---------|
| ph24 主文档「下一阶段」 | deny.toml / audit job / release-check.sh 被 KV/LSM 工程直接拿去用；KV 运行时安全、Agent 后端权限/审计/可观测性在那里展开 | 3.1~3.5 的引擎组件 + project/ 的 deny.toml 与 release-check.sh（注明来源）+ 3.11 工具边界 |
| ph24 project/README 扩展方向 | 「换被测对象：把 src/lib.rs 换成 ph25 的 KV/LSM 组件——模板原样可搬」 | project/mini-kv-service 直接用该模板跑通 9 步流水线 |
| ph19 主文档边界声明 | 「完整恢复机制属 ph25」 | 3.1 的 WAL replay / 残尾修复（ex01 + sol-01） |
| ph19 project/README | 「把 records 迭代出的 Put/Delete 应用到内存表做成 Mini MemTable——完整语义属 ph25」 | 3.2 MemTable + ex01 `apply_to_memtable` |
| ph21 project/README | 「ph25 的 KV/LSM crate 直接以本模板起步」 | project/ 的 fmt/clippy/test 门禁沿用 ph21 模板并过 release-check |
| ph20 testing 系列 | 「把假引擎换成 ph25 的真实 MemTable/WAL replay，套件不变」 | project/ 的 5 个测试即换过真实引擎后的落点 |

## 2. 来源与演变

数据基础设施的主线是「**把随机写变成顺序写、把不可变文件变成可归并的层**」，这条线在 Rust 生态里 2015 年后与系统语言复兴同频。先补一段生态史：**sled**（2016 起，Spacejam 早期项目）是 Rust 社区第一个有影响力的嵌入式 KV——它尝试锁免费的结构（当年叫「lock-free」的 B+Tree 变体，后转向 LSM 风格），把「用 Rust 写存储引擎」变成大众话题；**redb**（2020 起）用 B+Tree 路线证明纯 Rust 嵌入式库可以小而稳；**RocksDB 的 Rust 绑定**（rust-rocksdb）与 **tikv**（2016 起，PingCAP 的分布式事务 KV，Rust 写）把「LSM + Raft」的完整组合带进 Rust——TiKV 至今仍是 Rust 数据基础设施最大的生产样本：**它用一个纯 Rust 的 Raft 实现（etcd-rs / raft-rs）指挥 RocksDB 的列族**，这个分工正好是本章 3.5 与 3.7 的「compaction 归并 + 日志复制状态机」在工业界的缩影。检索侧：**arrow / datafusion**（2018 起，Apache 基金会的 Rust 列式内存与查询引擎）与 **vector**（2019 起，Datadog 用 Rust 写的可观测数据管道）证明 Rust 在「数据在内存里如何排布、如何在管道里搬运」上也站得住。**设计哲学一句话加粗：存储组件的每个结构都在「读成本」与「写成本」之间选边——WAL 与 LSM 把随机写摊成顺序写，SSTable 与 Bloom 把磁盘读摊成可过滤的块读，Raft 把「状态机一致性」摊成一条可重放的日志，HNSW 把「最近邻」摊成一张可导航的图；Rust 的所有权与类型系统让这些摊法第一次可以在编译期证明安全。**

机制史本身可以呼应 C++ 版 ph22 的 LSM 纪事（WAL 回溯到 1970 年代 System R 以来的崩溃恢复研究、1992 年 ARIES 把 redo/undo 系统化、Bloom Filter 是 Burton Bloom 1970 年的论文、LSM 是 O'Neil 等 1996 年、Bigtable 2006 年把 MemTable/SSTable 带进工程词汇、LevelDB 2011 / RocksDB 2013 成为参考实现），本表不重复那段，只列 **Rust 生态侧**的里程碑：

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| sled | 2016~ | 早期 Rust 嵌入式 KV：把「无锁 / 可持久化」写进 Rust 社区议程，虽然后期 API 波动大、被质疑过度设计，仍是最早的布道者 |
| rust-rocksdb 绑定成熟 | 2016~ | 让 Rust 工程直接骑在 RocksDB 上，获得成熟 LSM + 列族 + 合并算子 |
| TiKV / raft-rs | 2016~ | 纯 Rust 分布式事务 KV：Raft 层（raft-rs）指挥 LSM 引擎，分布式共识 + 存储引擎的 Rust 合体样板 |
| arrow / datafusion | 2018~ | Apache 生态的 Rust 列式内存格式与查询引擎；数据在内存里以列式排布、SIMD 友好的范式 |
| vector | 2019~ | 可观测数据管道（采集→转换→路由），把「异步 + 类型化 pipeline」的 Rust 工程推向生产 |
| redb | 2020~ | 纯 Rust B+Tree 嵌入式 KV，走「小而稳、零 unsafe 依赖」路线，是 sled 之后的口碑标杆之一 |
| 本文的工程基线 | 2025~2026 | rustc 1.92 稳定支持 edition 2021/2024；axum 0.8 / tokio 1.53 / pyo3 0.23（abi3）成为本阶段实测依赖 |

本文示例以 **rustc/cargo 1.92.0（stable-aarch64-apple-darwin，rustc ded5c06cf 2025-12-08 / cargo 344c4567c 2025-10-21）** 为基线（与 ph17/ph21/ph23/ph24 及本仓库全部 rs/ 代码层一致），**Python 3.13.12**（`/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3`）为 pyo3 验证解释器。**验证工具链与本环境实测口径**：ex01~ex05（纯 std 零第三方依赖）已逐个本机 `cargo test --release` 验证（8/6/6/5/5 全绿，`clippy -D warnings` 零警告）；ex06/ex08（网络依赖）实测依赖版本为 axum **0.8.9**、tokio **1.53.1**、serde **1.0.229**、serde_json **1.0.151**、async-trait **0.1.92**（ex08），HTTP 冒烟与单测均实测通过；ex07 pyo3 **0.23.5**（abi3-py311）构建成功并由 Python 3.13 实际 `import ph25_accel` 调用通过；project 的 release-check.sh 复用 ph24 的 cargo-audit **0.22.2** / cargo-deny **0.20.2** 实测 9 步通过（advisories 在 db fetch 网络不稳时按脚本降级为警告，硬性门禁由 cargo audit 承担）。**未在本环境验证**的项如实标注：真实多节点 Raft、真实 Agent 框架层、真实 crates.io 发布（无账号/token）、`cargo test` 对 pyo3 extension crate（需嵌入解释器符号，本环境为可重定位 Python，测试改走 Python 侧 verify.py）。**这个阶段语法点极少，难的是把「所有权 / 错误 / 安全」落到每个组件的组合纪律上**——每节都会问同一句：这个设计里，Rust 的所有权与类型系统替我保证了什么？

**给想往生产走一步的读者**：本章的每个 toy 都能在开源工程里找到「大一号」的对应物——WAL/MemTable/SSTable/Bloom/compaction 直接对 LevelDB/RocksDB 源码（C++）与 sled/redb（Rust）；Raft 单节点对 raft-rs 的 `Raft` 状态机骨架；HNSW toy 对 hnswlib（C++）与 Rust 侧 `instant-distance`/`qdrant` 的图实现。读源码的路径建议：先找你 toy 里「被简化掉的那一步」（比如 compaction 的选文件、HNSW 的邻居启发式），再看大工程怎么补——这比从头读大库快得多，也正好是「组件心智 → 工业实现」的桥。

## 3. 语法与参数

本章按 roadmap 第 25 节学习内容展开。它不是语法章，而是**组件接口与布局参数章**：每个组件回答「为什么这样设计」+「Rust 的所有权 / 错误 / 安全在此处的具体体现」。全部命令与完整工程见 [`examples/`](./examples/)，练习见 [`exercises/`](./exercises/)，综合项目见 [`project/`](./project/)。

先给一张**组件栈全景图**，学完本章后再回来看它，每个方块都该能说出「它防什么、它贵在哪、所有权在哪体现」：

```text
                 ┌──────────────────────────────────────────────┐
  服务面          │ Axum（HTTP：/kv、range-scan、工具调用、metrics）│  3.9/3.11
                 └──────────────┬───────────────────────────────┘
                                │ 调用
                 ┌──────────────▼───────────────┐   ┌────────────────────┐
  工具面          │ Agent 工具后端（权限/超时/审计）│   │ pyo3 Python 加速   │  3.10/3.11
                 └──────────────┬───────────────┘   │（解析/距离热路径）    │
                                │                    └─────────┬──────────┘
                 ┌──────────────▼───────────────┐              │
  引擎面          │ MemTable（有序内存表）+ WAL     │─────────────┘ 数据如何被读到
                 └──────────────┬───────────────┘
                                │ flush / 重放
                 ┌──────────────▼───────────────┐   ┌────────────────────┐
  存储面          │ SSTable（不可变有序文件）       │──▶│ Bloom Filter 点查闸门│  3.3/3.4
                 └──────────────┬───────────────┘   └────────────────────┘
                                │ 后台归并
                 ┌──────────────▼───────────────┐
                 │ Compaction（归并/删 tombstone） │  3.5
                 └──────────────────────────────┘
 一致性面：WAL（单机崩溃）与 Raft 日志（多副本）共用「日志即事实、状态是投影」——3.1/3.7
 检索面：HNSW 图索引 + 四件套评测（recall/QPS/P95/内存）——3.8
```

### 3.1 WAL：append / replay 与崩溃恢复（ph19 字节纪律落地）

WAL（Write-Ahead Log）的第一性原理：**任何状态变更，先把「我打算做什么」追加到日志并落盘，再改内存结构**——崩溃后重放日志即可重建内存态。本阶段引擎层的 WAL 是 ph19 解析纪律的「使用方」：ph19 目录内的 parser crate 证明了「魔数先行 → 长度闸门 → CRC → 损坏即停」的字节写法可行；本阶段把它升级成「写路径 append + fsync → 读路径 replay + torn tail 修复」的完整循环。

| record 字段 | 作用 | 没有它会怎样 |
|------|------|-------------|
| magic u32 | 识别「这是我们的记录」（本仓库与 C/ph16、cpp/ph22 对齐：`0x57414C31` = "WAL1"，大端） | 垃圾 / 错位数据被当成合法记录解析 |
| type u8 | 区分 PUT / DEL（删除 = tombstone 记录，不是擦除） | 删除无法表达，日志只能增不能删 |
| klen / vlen u32 | 长度前缀 → replay 能逐条跳读 | 解析器必须理解 payload 才能找下一条 |
| key / value | payload | — |
| crc32 u32（覆盖 type..value） | 校验完整性（残写、位衰减在此现形） | 半条记录被当完整记录，数据悄悄错乱 |

```rust
// examples/ex01-wal-replay/src/main.rs —— WAL append + replay 骨架（节选，已验证）
// record 布局：encode 端与 replay 端必须用同一个长度公式与同一个校验范围
impl WalAppender {
    pub fn append(&mut self, op: Op, key: &[u8], value: &[u8]) -> Result<u64, WalError> {
        let rec = Record { seq: self.next_seq, op, key: key.to_vec(), value: value.to_vec() };
        let mut buf = Vec::with_capacity(HEADER_LEN + key.len() + value.len() + 4);
        rec.encode(&mut buf);            // 见 encode：大端字段 + CRC 覆盖 type..value
        self.file.write_all(&buf)?;      // 追加（文件以 append 打开）
        self.next_seq += 1;
        Ok(rec.seq)
    }
    pub fn sync(&mut self) -> Result<(), WalError> {   // fsync：append 返回 ≠ 持久化
        self.file.sync_all()?;
        Ok(())
    }
}
```

**重放的校验顺序是四道防线，顺序有讲究**：① 剩余长度够一个头部 → ② magic 吻合 → ③ klen/vlen 联合长度上限（各自 ≤ 上限且合计不越界）→ ④ CRC 吻合；任一失败就停在「残尾」（torn tail），报告偏移，修复手段是把文件 `ftruncate` 到干净位置——这是「最多丢最后一条」承诺的来源。**Rust 在此处的体现**：解析层不 panic——每步 `get` 区间检查、定长用 `try_into`、错误收进 `WalError` 枚举（`?` 传播，绝不在字节路径上 `unwrap`）；所有权上，`replay` 把每条 `Record` **拥有化**后交给回调 `apply`，由引擎决定是插内存表还是丢——「解析器返回借用、引擎层拥有」的交接点在函数签名里就是可见的（与 ph19 的零拷贝解析无缝衔接）。ex01 实测三条路径（完整输出见 examples/README）：干净追加 3 条重放 `Clean{applied:3}`；尾部塞 6 字节垃圾 → `TornTail{offset:39}` 截断后还能继续写；翻转第二条 payload 一字节 → `Corrupt{offset:32, error: ChecksumMismatch{expected:578089092, actual:342720993}}`。**为什么这样设计**：日志只增不改、append 是顺序写，fsync 的代价用「攒批一次落盘」（组提交，见 4.2）摊薄——先写日志的本质是「把随机写的崩溃窗口收窄到一条记录」。

**写路径与恢复路径的完整形态**（把它放进引擎看更清楚，project/ 即按此实现）：

```text
写路径：put/del ──▶ WAL append ──▶ fsync（提交粒度由调用方定）──▶ MemTable 变更
                              崩溃？──是──▶ 丢最后一条残记录（可截断修复），其余 op 安然无恙
恢复路径：open ──▶ WAL replay（四道校验，遇残尾 set_len 截断）──▶ 重建 MemTable
```

**四个容易踩的坑**（ex01/sol-01 的注释里都有实录）：① 编码端与 replay 端必须用同一个长度公式与同一个 CRC 范围——开发时曾因 replay 漏算长度字段导致全部记录判损坏；② `ftruncate` 后写游标可能停在 EOF 之外，直接写会造出「零字节空洞」——必须在截断后重新 `seek(End(0))`（sol-01 因此修过一版）；③ 残尾的判定要用「文件尾 > 已解析位置」，而不是「读到的字节数 < 头部」——恰好 8 字节的残尾会被误判成干净 EOF；④ `enum Op as u8` 的第一变体是 0，而记录格式里约定 PUT=1——把枚举直接 cast 会写出 op=0 的坏记录（sol-01 真实踩坑，后改显式映射 1/2）。这些坑的共同教训：**字节格式的每一处「约定」都要有一份显式代码 + 一条测试**，让编码端与解码端互相印证。

### 3.2 MemTable：内存有序表做写缓冲

MemTable 是 LSM 的内存层：**所有写入先进它，保持 key 有序，写满后整体 flush 成 SSTable**。工程上选 Skip List 还是 BTreeMap 取决于「写路径要不要并发化」：LevelDB/RocksDB 用 Skip List 是因为它对无锁并发友好（跳表的层结构可以原子地局部修改）；本阶段是单线程引擎，用标准库 `BTreeMap` 直接获得「有序 + 范围遍历 + 覆盖写」三件套，**并在注释里注明与 C++ 版 ph22（SkipList）的取舍差异**——这正是「所有权/安全抽象 × 数据基础设施」分工视角的第一个例子：C++ 版要自己管理跳表节点的生命周期，Rust 版把内存安全交给 `BTreeMap`，把精力放在语义正确上。

**删除必须写成 tombstone**：不能 `mem.remove(key)` 了事——删除是「写一条 Delete 记录进 WAL + 从内存表移除」；一旦 flush 成 SSTable，删除意图以 tombstone 形态保留在文件里，才能遮挡更旧层（3.5 compaction 讲为什么）。ex01 的 `apply_to_memtable` 把重放的 Put 插表、Delete 删表，正是 engine 的最小形态：

```rust
// examples/ex01-wal-replay/src/main.rs —— 删除 = 记录 + 移除（节选，已验证）
pub fn apply_to_memtable(mem: &mut BTreeMap<Vec<u8>, Vec<u8>>, rec: Record) {
    match rec.op {
        Op::Put => { mem.insert(rec.key, rec.value); }
        Op::Delete => { mem.remove(&rec.key); }
    }
}
```

**Rust 在此处的体现**：`BTreeMap` 的元素所有权明确——`put` 移动 `Vec<u8>` 进树、`get` 返回 `Option<&[u8]>` 借用、`scan` 返回克隆的拥有数据或借用切片由调用方决定；绝不存在「用后悬垂」或「迭代中修改」这类 C++ 常见事故。project/ 的 `engine.rs` 把「WAL 写盘 → 内存表变更 → 崩溃重放」收进 `Engine` 一个结构，`scan` 在内存表上直接做闭区间有序返回——range scan 从这里就是一等公民。

**为什么选 BTreeMap 而不是别的结构**——一张「选型对照表」把工程约束写清楚：

| 候选 | 有序 | 覆盖写 | 范围遍历 | 无锁并发友好 | 备注 |
|------|:---:|:---:|:---:|:---:|------|
| `BTreeMap`（本阶段） | ✓ | ✓ | ✓ | ✗（需 `Mutex` 包） | std 自带，内存安全编译期保证 |
| Skip List（C++/cpp/ph22） | ✓ | ✓ | ✓ | ✓（对锁免费改造友好） | LevelDB/RocksDB 的 MemTable 形态；C++ 侧自己管节点生命周期 |
| `HashMap` | ✗ | ✓ | ✗ | ✓ | 点查快但 flush/scan 前要排序，把成本推迟到写满那一刻 |

Rust 版用 `BTreeMap` 的取舍是**教学与工程共同决定的**：单线程引擎里「有序」才是刚需（flush 成 SSTable 与 range scan 都靠它），Skip List 的并发优势在这里用不上；把内存安全交给标准库、把精力留给「WAL 先落盘」这一条语义——这正是 Rust 侧与 C++ 侧分工视角的注脚。

### 3.3 SSTable：不可变有序文件 + writer / reader

SSTable 是 LSM 的磁盘层：**不可变有序文件**。不可变意味着「写一次读多次、可整体删除、对并发读天然安全」，这正是 Rust 所有权哲学的磁盘版——`&T` 随便开、`&mut T` 唯一；文件不可变 = 可以放心缓存与共享。

| 结构 | 作用 | 本阶段的落点 |
|------|------|-------------|
| block 内升序 entry | 每个 block 是一小段有序数据，读时整块取回顺序比对 | 块 = `[n u32][entry]*n`，entry = `[type u8][klen u32][key][vlen u32][value]` |
| 稀疏索引（块首 key → 偏移） | 不必全文件扫描就能二分定位块 | index = 每块一条 `[first_key][offset u64]` |
| 定长 footer / trailer | 文件尾固定位置告诉读侧「索引和 Bloom 在哪」 | trailer = `[magic][num_blocks][index_len][bloom_len]` |

ex02 把 2000 个键写成一个 88 141 B / 667 块的文件后实测：点查 `get` 只读 **1 个块**，`scan` 读全区间 8 个块——**读盘面的差异是文件结构直接决定的，不是猜的**。文件里 tombstone 以 `type=Delete`、vlen=0 的形态存在，读侧返回 `Value::Tombstone` 让上层决定遮挡语义。

**Rust 在此处的体现**：writer 与 reader 是两个独立类型（`SstWriter` 消费有序迭代、`SstReader` 持有 `Vec<u8>` + 解析好的索引与 Bloom），"不可变"直接由类型表达；读路径上所有长度字段都来自不可信字节，逐处 `get` 区间检查后返回 `Result`——一个损坏文件最多报 `BadIndex/TooShort/TooLarge`，绝不越界 panic。排序不变量交给 writer：`add` 遇到降序输入直接返回 `OutOfOrder` 错误，把「非法状态不可表示」从类型层延伸到协议层。

**读一条 key 的完整路径**（把结构串起来看为什么点查「只读 1 块」）：

```text
get(key)
 ├─ ① Bloom.may_contain(key) ── false ──▶ None（文件里肯定没有，零 I/O）
 └─ true（可能有）
     ├─ ② 稀疏索引二分：找最后一个 first_key ≤ key 的块
     ├─ ③ 只读那一块：块内升序线性比对（超过即停）
     └─ 命中返回 value；tombstone 返回删除标记，让上层遮挡旧层
```

**Rust 在此处的体现（所有权在文件格式上的投影）**：SSTable 不可变 ⇒ 读侧可以安全持有整文件字节并共享（`&[u8]` 随便开），不必考虑写者并发——这正是「不可变」从磁盘布局语言翻译成并发安全语言的过程；读路径上每个长度字段都来自不可信字节，`decode_block` 逐处 `get` 区间检查后返回 `Result`，坏文件最多报 `BadIndex/TooShort/TooLarge`，**绝不越界 panic**（ex02 的 decode 全部走 Result，没有裸下标）。writer 侧则把「排序不变量」收进 `add`：降序输入直接 `Err(OutOfOrder)`——非法状态在协议层也「不可表示」。

### 3.4 Bloom Filter：点查加速的标准件

Bloom Filter（1970 年 Burton Bloom）是**以可控假阳性换「无假阴性」**的空间换时间结构：位数组 + k 个散列位置，查询时只要有一个位是 0，key 一定不在文件里。把它挂在 SSTable 点查路径上，**大部分「点查不存在的 key」在文件系统 I/O 之前就被拦掉了**。

| 性质 | 含义 | 本阶段怎么验证 |
|------|------|---------------|
| 无假阴性 | `may_contain=false` ⇒ key 一定不在 | ex02 对全部 2000 个已写 key 断言全过（假阴性 = 0） |
| 有假阳性 | `true` 只能说明「可能」，还要真正查文件 | 2000 个不存在 key 实测 0 个被判 maybe（bits/key 被取整成 16 后 FPR 极低） |
| 参数 | m = n × bits_per_key；k = round(ln2 · m / n) | ex02 m=32768、k=11 |

**Rust 在此处的体现**：Bloom 的位操作是最容易写错越界/并发的地方——本阶段用 `Vec<u8>` + `(pos/8)` / `(pos%8)` 显式位寻址，无一个 `unsafe`；f32 不是 `Ord`，距离作排序键时用 `f32::to_bits()` 转成保序的 u32（对非负浮点保序），这类「把不可比类型转成可排序键」是类型系统逼出来的好习惯。工程上可换 `crc32fast`、xxhash 等硬件加速散列——那属于「后续可深入方向」，本阶段 FNV 双散列足矣（假阳性率推导要点见 4.4）。

**为什么用「双散列」而不是 k 个独立散列函数**：独立散列需要 k 个不同的种子与 k 次遍历，代价高；双散列法 `pos_i = (h1 + i·h2) mod m`（h2 取奇数保证步长与 m 互质、能覆盖整个位图）用两个散列值生成 k 个位置，遍历一次数据即可全部算出——工程实现几乎总是走双散列。**参数一旦错了会怎样**：k 过大会把位图快速置满（假阳性率不降反升）、m 过小同理——所以 ex02 用「bits/key」而非裸「位数组长度」作参数，让不同规模的表可比较。**Bloom 与「点查拦截计量」**：工程里值得把 `may_contain=true` 的次数单独计数——它告诉你「过滤闸门拦截了多少次真正不需要的磁盘读」，是评估 bits/key 该不该调的量化依据（ex02 对 2000 个不存在 key 实测 0 次放行，说明当前 bits/key 有余量）。

### 3.5 Compaction：归并语义与 leveled 思想

Compaction 是 LSM 的「后台整理」：把多个有序 run 归并成更少的 run，顺带做三件事——**旧值被新值覆盖（丢掉）、tombstone 真正删除 key、数据更紧凑**。归并语义的难点全在 tombstone 上：

> **非底层归并（下面还有更老的 run）必须保留删除标记**——否则更老 run 里的旧值会「复活」；只有「到底」的 full compaction 才能真删。这一条在本阶段由 examples/ex03 与 exercises/sol-03 的断言锁死：partial（final=false）归并结果必须带 `deleted`，full（final=true）归并后 key 才真正消失。

**Leveled 思想**：RocksDB 式 leveled compaction 把数据分成若干层，每层容量是上一层的固定倍数（size ratio T），compaction 触发时从上层取文件与下层有 key 区间重叠的文件归并。它换来的收益是「读放大有上界」：点查最多查 L0 的文件数 + 每层各 1 个文件（Bloom 把每个文件再压成 O(1) 判定）；代价是「写放大」——每个 entry 在向下走的每一层大约被重写 T 次。tiered（universal）思路则反过来攒批：等若干个 run 攒满再整体归并，写放大低、但两次归并之间读要跨更多 run。

ex03 在一个确定性模型上把这段拍成了可复现数字（模型参照 cpp/ph22 ex06，见文件头注明）：同一批 12 次 flush，**每次 flush 都全量归并**写出 13 767 B（平均读放大恒 1.00）；**攒 4 次归并一次**只写出 3 809 B，但平均读放大升到 2.00、在两次归并之间累积——「何时触发 compaction」本身就是 LSM 的核心运维杠杆。Rust 在归并里的体现是所有权交接：`merge_runs` 消费一组 `Run`（不可变借用逐个读），把每个 key 的最新版本用 `BTreeMap` 收集后整体搬进新 `Run`，`MergeStats` 返回「丢弃多少覆盖、多少 tombstone」——统计与数据同构，不需要额外的全局计数器。

**leveled vs tiered 的取舍表**（把「三放大」落到具体策略上）：

| 策略 | 触发方式 | 写放大 | 读放大上界 | 适用 |
|------|---------|--------|-----------|------|
| leveled | 层容量达到倍数即选文件归并 | 高（每层重写约 T 次） | 低（每层 1 文件 + Bloom） | 读多写少的稳定负载 |
| tiered / universal | 攒够 N 个 run 整体归并 | 低 | 高（N 个 run 都查） | 写多、可接受读波动 |

**tombstone「复活」的完整剧情**（为什么非底层必须保留删除标记）：假设 L1 是 2024 年写入、L2 是 2022 年写入，2025 年用户删除了 key=k——Delete 记录进了 L1。若此时把 L1 与 L2 归并（非底层，下面可能还有更老的层），却把 L1 里的 tombstone 顺手丢掉，那么 L2（以及更老层）里的 k 旧值就「复活」了——用户明明删过它。所以归并算法只在该层已确认「下面没有更老数据」（full compaction 到底）时才允许真删。ex03 的断言把这条锁死：`merge_runs(partial, final=false)` 输出必须仍带 `deleted`。

### 3.6 Snapshot 与 MVCC 简化模型（点到为止）

多版本并发控制的简化模型一句话：**删除/更新 = 写一条新版本，旧版本留在原地**——这正好是 tombstone 的精神祖先（LSM 的删除标记与 MVCC 的旧版本是亲戚）。本阶段只点到三个概念：

| 概念 | 简化直觉 | 与 LSM 的关系 |
|------|---------|--------------|
| 读快照 | 读操作绑定一个固定的版本号（seq），只看 ≤ 该版本的数据 | MemTable/日志记录天然带 seq，为「按 seq 过滤」留好位置 |
| 版本可见性 | 同 key 多条版本，只有「已提交且 ≤ 我的快照」的那条可见 | compaction 按 seq 取新压旧，就是可见性规则的落盘版 |
| 删除 = 新版本 | tombstone 就是「值为 deleted 的新版本」 | 见 3.2/3.5 |

本阶段不实现事务（begin/commit/rollback、隔离级别），也不做多版本的数据结构（版本链、undo log）——那属数据库事务理论。示例代码里唯一与 MVCC 相关的落点是 ex04 的 `seq`/`commit_index`：**日志记录带顺序号，状态机只 apply 已提交前缀**——这是「版本可见性」在单机一致性模型上的最小雏形。若需要真的读快照隔离（如 ph18 附录路线里的时序库方向），从「快照号 = 日志位点」出发即可，那是后续可深入方向。

**为什么单机 KV 也要懂 MVCC 概念**：真实系统的「读一致性」从来不是「读到最后一次写」这么简单——备份、报表、长时间事务都希望看到「某一刻的一致快照」。工程上最小的一步是给每次写分配**单调 seq**、给每次读声明「我要 ≤ 哪个 seq 的快照」，这就是 MVCC 的种子。本阶段的引擎已经带了 seq（WAL record 的顺序号 / Raft 的 index），所以从「现在只有最新值」到「保留历史版本供快照读」只差「旧版本别急着丢」这一步——那一步正是工业引擎做多版本与 compaction 交互（版本过期判定）时要精雕的地方。作为读者，你此刻只需建立两个认知：**快照 = 版本号；可见性 = 一个判定函数（我的快照号 ≥ 该版本的写入号吗）**。

### 3.7 Mini Raft：单节点日志复制状态机（选举概念）

Raft 通过日志复制让多副本的状态机一致。本阶段的边界是**单节点**：不实现节点间 RPC、quorum、leader 切换，只把「与单节点也成立」的两块核心抽象做对——① **日志条目带 (term, index)**：客户端指令先 append 进日志，再按 `commit_index` 顺序 apply 到状态机（K-V 表）；② **选举在单节点簇里的退化形态**：term 单调递增、节点给自己投票、立即当选。

```text
写路径：客户端指令 ──▶ append(term, index+1) ──▶ commit（单节点 majority=1）──▶ apply 到状态机
崩溃恢复：丢弃内存状态机 ──▶ 凭日志 + commit_index 从头重放 ──▶ 状态机恢复原样（幂等）
```

**为什么先日志后状态机**：只有日志是「可重放的事实」，状态机只是它的投影。ex04 实测：选举后 append no-op（覆盖上一任期遗留）、随后 4 条 put/delete 指令依次 commit→apply，模拟崩溃后只凭日志重放 5 条就把状态机恢复到 `{"alpha":"10"}`——与崩溃前一致。多节点的完整语义（请求投票 / AppendEntries RPC、多数派、心跳超时随机化、matchIndex/nextIndex 的日志匹配）在正文用流程文字与注释讲清，属后续可深入方向。**Raft 与 WAL 的关系一句话**：Raft 的日志就是分布式版的 WAL——单机 WAL 防「进程崩溃」，Raft 日志防「节点崩溃 + 网络分区」，两者的重放思想一致（本阶段 ex01 与 ex04 可以对照着读）。

**多节点选举与日志复制（概念，不是实现）**：本阶段单节点把「term 单调、投自己、当选、append no-op」跑通了，多节点只是把这些动作发给别人：

```text
选举：随机超时到期 ──▶ term+1，广播 RequestVote ──▶ 收到多数派投票 → 当选 leader
                              └─ 收到更高 term 的 RPC → 立刻让位（term 是全局单调钟）
复制：leader 收客户端指令 ──▶ append 到本地日志 ──▶ 广播 AppendEntries（带 prevLogIndex/prevLogTerm）
      └─ follower 发现日志不匹配 → 拒绝并回退 → leader 往前删改重发（保证日志前缀一致）
```

工程上不实现它的理由很诚实：真实 Raft 的坑在「网络分区时的脑裂防护」与「日志匹配的收敛效率」，需要故障注入与多节点测试环境才能验证——那超出单机可测的本阶段边界，是后续方向。但单节点形态已经让你亲手摸到三块地基：**term 单调性、index 连续性、commit→apply 的顺序推进**。

### 3.8 HNSW 向量检索基础：图索引 toy 与四件套评测

HNSW（分层可导航小世界图）把「最近邻」变成一张多层图：高层稀疏图负责快速跳到目标区域，底层稠密图负责精确收尾。本阶段实现它的最小核心（examples/ex05，纯 std、确定性数据）：

- 每层每节点最多 M 个邻居；新点按 `floor(-ln(u)·mL)`（mL = 1/ln M）分配层高；
- 插入：层间逐层**贪婪下探**（每层留最近 1 个），到目标层后**宽搜**（ef_construction）取最近 M 个连双向边，超限按距离剪枝；
- 查询：从图顶下探到底层，底层按 ef_search 宽搜取 top-k；
- 评测四件套：**recall@10**（对暴力 top-10 的重合率）、**QPS**（整批查询实测）、**P95 延迟**（逐查询计时排序取分位）、**内存**（按结构成员计算估计，注明口径）。

ex05 实测（N=2000、DIM=8、M=8、ef_c=64、ef_s=120，本机某次）：构建 83.0 ms、图 32 832 条边、8 层、内存 ≈ 455 KiB；查询 recall@10 = 0.831、QPS ≈ 1.6 万、P95 ≈ 0.13 ms；暴力对照 QPS ≈ 2.5 万。**诚实结论直接印在输出里**：在 2k×8 维这种小尺度上图索引的常数开销尚未被 N 增长摊薄，收益要到更大 N / 更高维才显性；recall/QPS 是调参权衡（ef 越大 recall 越高、越慢）——exercises/sol-04 用一个可复现的束宽扫描把这条权衡也锁成了断言。**Rust 在此处的体现**：图结构用 `Vec<HashMap>` 分层存邻接、`BTreeSet<(u32, usize)>` 当候选集——f32 距离不是 `Ord`，用 `to_bits()` 键化（见 3.4）；toy 里没有任何 `unsafe`，邻接访问全部走索引 + `get`，越界在结构上不可表示。工业级向量库（量化训练、启发式邻居选择、并发写入、持久化格式）是后续方向。

**为什么图索引能「跳」到目标区域**：多层结构的直觉是「高层图 = 稀疏的高速公路，底层图 = 密集的街区路」。插入时每个点按几何分布随机获得层高（约 1/M 的点有 1 层以上），高层节点天然是「地标」——从入口点出发在高层每步只能走少数几条边，但一步能跨过大量底层节点，因此到达目标区域只花 O(log N) 步；到底层后再用小步长精确定位。**参数表**（ex05 与 sol-04 的默认值）：

| 参数 | 含义 | 取大 | 取小 |
|------|------|------|------|
| M | 每层每节点最大邻居数 | 图更密、建图更贵 | 图更稀疏、可能断连 |
| ef_construction | 建图候选宽搜 | 邻居质量高、建图慢 | 邻居粗糙 |
| ef_search | 查询候选宽搜 | recall 高、查询慢 | recall 低、查询快 |
| mL | 层高分布参数（1/ln M） | 高层更密 | 高层更稀 |

ex05 的诚实输出请重点读：在 2k×8 维小尺度上 HNSW 的吞吐没跑赢暴力——**这不是失败，是这条曲线本来的形状**；sol-04 的束宽扫描（窄 6 vs 宽 60）则把「宽候选 → 更高 recall → 更慢」的权衡用两组真实数字印了出来（recall 0.956 → 1.000，QPS 3.6k → 2.0k）。

### 3.9 Axum / Tonic 数据服务：把 KV 与检索暴露成 API

Axum（0.8，tokio 系）做 HTTP 数据服务的四个动作：**路由、状态共享、统一 JSON 错误、超时语义**。Tonic（gRPC）是同一批思想在二进制协议上的版本（proto + codegen + 双向流），本阶段以 Axum 实测为主、Tonic 只作概念对照（未实现，标注「未在本环境验证」——见 examples/README 与 5 节生态对照）。

| Axum 动作 | 本阶段的落点 |
|----------|-------------|
| 路由与方法链 | `route("/kv/{key}", get(get_kv).put(put_kv).delete(delete_kv))`、`route("/kv", get(scan_kv))`（0.8 起路径参数用 `{key}`） |
| 状态共享 | `State<Arc<Mutex<Engine>>>`：每请求克隆 `State`（廉价 Arc），锁保证跨请求写互斥 |
| 统一 JSON 错误 | `ApiError`（NotFound/Internal）实现 `IntoResponse`，404/500 的 body 都是 `{"error": …}`，调用方好解析 |
| 超时语义 | 本服务内存操作无慢路径，超时由调用方/中间件承担；真正需要预算的是 Agent 工具（3.11/ex08）与远程依赖（tokio::time::timeout） |

ex06 实测 HTTP 冒烟：`PUT /kv/temperature {"value":"36.5"}` → `GET` 返回 `{"key":"temperature","value":"36.5"}`；`GET /kv?start=h&end=pressure` 返回闭区间条目；DELETE 204；删后再 GET 404 且 body 统一 JSON。project/ 把这套面直接架在持久化引擎上——HTTP CRUD 写的每一条都先落 WAL。**Rust 在此处的体现**：handler 全部 async + 返回 `Result<_, ApiError>`，锁中毒用 `map_err` 转成 500 而不是 `unwrap` panic——「异步边界不 panic、错误全部结构化」是服务层与引擎层同一条纪律。

**Tonic（gRPC）概念对照**：HTTP/JSON 适合「人类可读、语言无关、调试方便」的服务面；gRPC 适合「强类型契约、二进制高效、双向流、多语言 SDK 自动生成」的内部服务面。Tonic 在 Rust 侧的形态是「写 `.proto` → `tonic-build` 生成代码 → 实现 trait server / 用 client stub」——请求/响应不再手写 JSON 结构，错误走 gRPC status。本阶段用 Axum 实测了「路由 / 状态 / 错误 / 扫描」全套，Tonic 只在此作概念对照（本环境未实现，标注「未在本环境验证」）；若把 project/ 的 KV 服务改成 gRPC，引擎层与工具边界一行不用动——换的只是「壳」。

**路由与提取器的最小对照表**（写 handler 前先想清楚「参数从哪来」，Rust 的类型系统会把「顺序写错」变成编译错误）：

| 数据来源 | 提取器 | 示例 |
|---------|--------|------|
| 路径参数 | `Path<String>` | `GET /kv/{key}` |
| 查询字符串 | `Query<ScanQuery>` | `GET /kv?start=…&end=…`（结构体 derive Deserialize） |
| 请求体 | `Json<Value>` | `PUT` body `{"value":…}` |
| 请求头 | `axum::http::HeaderMap` | `x-client-id`（工具调用的调用方声明） |
| 共享状态 | `State<AppState>` | `Arc<Mutex<Engine>>`（每请求廉价克隆） |
| 返回错误 | 自定义 `ApiError: IntoResponse` | `(status, Json({error}))` 统一格式 |

**服务的超时语义分两层**：进程内内存操作（本服务的 `get/put/scan`）没有慢路径，超时主要由**调用方/网关**兜底（HTTP 客户端超时、负载均衡器超时）；真正需要服务侧预算的是**会等外部的东西**——Agent 工具（3.11/ex08 的 `tokio::time::timeout`）、远程依赖调用。这条分层避免了一个常见错误：给内存操作也套一堆超时参数，徒增噪声却保护不了任何东西。

### 3.10 pyo3 Python 加速模块：把解析 / 距离计算暴露给 Python

ph23 把「怎么用 pyo3 安全过 FFI」教给了我们（extern "C"、cdylib、谁分配谁释放、panic 护栏），本阶段把它用到**数据基础设施的热路径出口**上：解析（WAL 帧）与距离（向量）都是「Python 慢、Rust 快」的典型。examples/ex07 用 pyo3 0.23.5 暴露三个函数：

```rust
// examples/ex07-pyo3-accelerate/src/lib.rs —— pyo3 模块骨架（节选，已验证）
#[pyfunction]
fn parse_frames(data: &[u8]) -> PyResult<Vec<&[u8]>> { /* 长度前缀帧切分，坏帧抛 ValueError */ }

#[pymodule]
fn ph25_accel(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_frames, m)?)?;
    // …
    Ok(())
}
```

**两个工程点**：① 构建用 **abi3**（`abi3-py311`）——产物不链接 libpython，可在 3.11+ 任意解释器加载；本环境 3.13.12 的 sysconfig LIBDIR 指向不存在的 `/install/lib`（可重定位 Python 构建），abi3 恰好绕开该问题（`.cargo/config.toml` 另提供 macOS 的 `-undefined dynamic_lookup`）；② **测试走 Python 侧**——pyo3 extension-module crate 的 `cargo test` 需要把解释器符号链进测试二进制，本环境不便嵌入，社区惯例是写一个 `verify.py` 由真实 Python import 后断言。实测（Python 3.13.12 import）：帧解析正确性通过、坏流抛 `ValueError`（残尾 / 截断信息清晰）；暴力 top-k（N=20 000、dim=8）Rust 约 2.9 ms vs 纯 Python 约 15.9 ms——「Python 要快就调 Rust」的出口在此闭环。

**与 ph23 的衔接**：ph23 教的是「边界怎么安全」——`extern "C"` 的导出面、panic 不过 FFI、谁分配谁释放；本阶段把它升级成「边界有什么可给」——模块该暴露什么函数、错误如何翻译成 Python 异常、参数如何借用不拷贝。`parse_frames` 的坏帧抛 `ValueError`（而不是 panic 让解释器崩掉）就是 ph23 的 panic 护栏在 pyo3 层的体现；`Vec<f32>` 参数由 pyo3 从 Python list 转换，转换失败返回 `TypeError`——**边界上的错误是类型化的，不是字符串拼接的**。工程上若要发布给团队/CI 用，ph23 project/README 预告的「maturin 打包、pyproject.toml、多 Python 版本构建」正是本模块的上游形态。

### 3.11 Agent 工具后端：权限 / 超时 / 审计 / 可观测

roadmap 的必会概念要求「Agent 工具后端要关注权限、超时、审计和可观测性」。本阶段把它们做成一个可测的边界（examples/ex08 与 project 各实现一次，形态一致）：

| 边界 | 问题 | 落点 |
|------|------|------|
| 权限 | 谁能调用哪个工具 | 调用方声明 scope 集合（`x-client-id` → `["kv:read","kv:write"]`），工具的 `required_scope()` 与之比对，不匹配 403 |
| 超时 | 工具卡住怎么办 | 每个工具给 `budget()`，路由层用 `tokio::time::timeout` 包一层，超时 504 |
| 审计 | 调用留痕、可追责 | 每次调用写 JSON 审计行（时间 / 调用方 / 工具 / 决策 / 耗时 / note）；纪律：**只记 key 不记 value** |
| 可观测 | 服务健康与用量可见 | 按 (工具 × 决策) 的计数与累计耗时，`/metrics` 暴露 |

工具抽象与 roadmap §25 的示例骨架一致（`#[async_trait]` + trait object 注册表）：

```rust
// examples/ex08-agent-tool-backend/src/main.rs —— Tool trait 骨架（节选，已验证）
#[async_trait]
pub trait Tool: Send + Sync {
    fn name(&self) -> &'static str;
    fn required_scope(&self) -> &'static str;
    fn budget(&self) -> std::time::Duration;
    async fn call(&self, ctx: &ToolCtx, input: Value) -> Result<Value, String>;
}
```

ex08 实测：writer 调 `kv.put` 成功、reader 越权写返回 `[403] {"error":{code:"permission_denied",message:"'reader' 无权调用 kv.put（需要 scope 'kv:write'）"}}`；`debug.sleep`（预算 30 ms、实际睡 100 ms）返回 `[504] tool_timeout`；`/metrics` 累计 `{"by_decision":{"allowed":2,"denied":1,"timeout":1},"by_tool":{...},"total_calls":4}`，`/audit` 逐条可查。**Rust 在此处的体现**：工具是 `Box<dyn Tool>` trait object（`async_trait` 让 async fn 可对象化），共享状态用 `Arc<Mutex<…>>` 收口；审计与计数都包在调用器里，工具自己不必知道「我被审计了」——横切关注点被类型化的边界隔开。真 Agent 框架层（编排 / 规划 / 记忆）是后续方向，本阶段只把「工具侧」做厚。

**一次工具调用的完整旅程**（把四件套串成一条链）：

```text
POST /tools/call  body={tool, input} + header x-client-id=requester
 │
 ├─ ① 路由层取 requester ──▶ ② registry 找 tool（找不到 → not_found + 审计）
 │                              └─ ③ scope 比对：requester 的 scopes ⊇ tool.required_scope？
 │                                    （不满足 → 403 permission_denied + 审计）
 │                              └─ ④ tokio::time::timeout(tool.budget(), tool.call(...))
 │                                    （超时 → 504 tool_timeout + 审计）
 │                              └─ ⑤ 工具执行（Result<Value, String>）
 │                                    （内部错误 → 500 tool_internal_error + 审计）
 │
 └─ ⑥ 无论哪条路都写审计行 + 计数：allowed/denied/timeout/not_found 各归各桶
```

**呼应全库行业语境的一个工具示例**：本仓库 Python/Java/C++/Go 各路线反复出现的「设备遥测 / 数据平台」语境在这里直接可用——把上面三个 KV 工具换成 `device.get_latest(device_id)`、`device.put_dtc(device_id, code)`、`device.scan_by_fleet(fleet_id)`，scope 换成 `fleet:read` / `fleet:write`，审计记录的是「谁、在什么时候、读了哪个 DEVICE_ID 的哪类字段」——**同样的边界代码，接真实业务只需要换工具实现与 scope 名字**。这就是「工具后端边界」与「业务语义」分层的好处。

**安全注意**：审计记 key 不记 value 是一条默认纪律——value 可能是密钥、PII、长文本，进审计日志等于把它复制到每一台日志收集器；工具输入里若必须带敏感字段，应写「字段名 + 长度」而不是内容。权限的最小化同样默认：`reader` 只有 `kv:read`，想越权写任何 key 都被 403——**权限是「按工具需要的最小 scope」，不是「按人给的最大权限」**。

## 4. 底层原理

### 4.1 LSM 读 / 写 / 空间三种放大的量化直觉

| 放大 | 直觉 | 影响因素 | ex03 的模型化观察 |
|------|------|---------|------------------|
| 写放大 | 用户写 1 B，后台因 compaction 实际写了几 B | 归并节奏、层数、覆盖密度 | 12 次 flush：每次全量归并写 13 767 B vs 攒批归并写 3 809 B（约 3.6× 差距） |
| 读放大 | 一次点查要读几个 run / 文件 | run 数量、Bloom 命中率、L0 文件数 | 不存在 key 点查平均探测 run 数：A=1.00 vs B=2.00 |
| 空间放大 | 物理占用 / 有效数据 | 删除与覆盖的积压、层容量比 | 3 run 归并前 92 B / 归并后有效 31 B（2.97×），归并后回落到 1× |

量化的目的是让「何时 compaction、层容量比取多少」成为可讨论的工程参数而不是玄学：读放大有上界（每层一个文件 + Bloom），写放大与归并频率成正比，空间放大与删除积压成正比——三者互相拉扯，所以 RocksDB 的调参文档本质上是一张三角权衡表。

### 4.2 WAL fsync 语义与组提交（group commit）

`write()`/`append` 返回时数据只到**内核页缓存**，机器断电/内核崩溃都会丢；`fsync`（Rust 的 `sync_all`）返回才意味着「可承诺」。如果每条写都 fsync，吞吐被单次落盘延迟卡死；**组提交**把一段时间内的多条提交攒批，一次 fsync 让整批同时成为「已提交」——代价是单条确认延迟略增（等一个批次窗口）。工程形态：一批记录先顺序 append（顺序写本身很快），攒到阈值或超时后一次 `sync_all`，再把整批的 commit_index 一起推进（这正好是 Raft 单节点版 commit_index 的语义——ex04 的「append 即 commit」在组提交下变成「批末 fsync 后批内全部 commit」）。本阶段 project/ 的 engine 为正确性选择了「每条写都 fsync」的保守档，README 把「攒批 group commit」列为扩展方向。

### 4.3 Raft 日志复制的一致性直觉

Raft 保证一致性的核心机制是**日志匹配属性**：如果两个节点上同一 index 的日志 term 相同，那么该 index 之前的日志完全一致。直觉来自「leader 只在 AppendEntries 里带 `prevLogIndex/prevLogTerm`，follower 发现不匹配就拒绝并回退」——这个「从后往前对账」的过程保证日志前缀不会分叉。本阶段单节点只用到它的投影：**index 连续、term 单调、commit 只能前进**。ex04/sol-03 的断言把这三条投影锁住（`index` 从 1 连续、`last_applied == commit_index`、恢复幂等）——多节点时真正要补的是「怎么让另一个节点也长出同样的前缀」，那需要 RPC 与多数派，属后续方向。

### 4.4 Bloom 假阳性率推导要点

设位数组 m 位、n 个元素、k 个散列。单个元素插入后某一位仍为 0 的概率 ≈ `(1 - 1/m)^(kn)`；查询一个不在集合里的 key，其 k 个位置都被置位的概率（假阳性率）≈ `(1 - (1 - 1/m)^(kn))^k ≈ (1 - e^(-kn/m))^k`。对给定 m/n，最优 `k = ln2 · (m/n)`（本阶段全部实现按此取 k）。工程含义：bits/key = 10 时理论 FPR ≈ 0.8%，bits/key = 16 时 ≈ 0.02%——ex02 把 bits/key 取整到 16 后 2000 个不存在 key 实测 0 个假阳性，与理论量级一致。Bloom 的「无假阴性」不随参数变化（那是结构保证），所以它可以安全地做**过滤闸门**：被它放行的才需要真查文件。

### 4.5 HNSW 为什么能近似但暴力不能：复杂度视角

暴力的复杂度是 O(N·D)（N 个点 × 每次 D 维距离），数据规模上去后无法回避；HNSW 把查询摊成「高层 O(log N) 步跳转 + 底层 O(ef·M) 步精搜」——每步只看当前节点的 M 个邻居，**复杂度与 N 解耦**（只与 ef、M 和对数层数有关）。代价有两笔：① 建图 O(N log N) 级且要存边（内存随 N 线性长，ex05 的 memory_bytes 把它估出来）；② 这是**近似**算法——跳转与宽搜都可能漏掉真最近邻，所以必须用 recall 对暴力真值来校准。这也解释了 ex05 为什么在 2k×8 维小尺度上「没跑赢暴力」：此时 N·D 太小，图索引的常数开销（邻接数组、BTreeSet 维护）反而占上风——**选型不是「图索引一定快」，而是「N 大到暴力不可接受时图索引才划算」**。

## 5. 使用场景

**数据基础设施组件的真实落点**，按「谁在用它」分三档：

| 角色 | 典型形态 | 本阶段哪些组件直接命中 |
|------|---------|----------------------|
| 嵌入式 / 单机服务 | 设备端状态、边缘缓存、单机时序 | WAL + MemTable + range scan（本阶段 project 的持久化服务就是最小样板） |
| 分布式系统 | 多副本强一致 KV | Mini Raft 的心智 + WAL（raft 日志 = 分布式 WAL），生产化交给 raft-rs/TiKV 一类 |
| AI / RAG 侧 | 向量检索、Python 加速 | HNSW toy 的评测方法 + pyo3 加速模块（解析/距离热路径出口） |
| Agent 基建 | 工具网关 | 工具后端的权限/超时/审计/可观测四件套 |

**什么时候不选它**：单机小数据量（几千条）上 HNSW 图索引跑不过暴力（ex05 已诚实输出这个结论）——检索索引的收益有数据规模门槛；不需要跨进程时 WAL/文件层是负担，直接内存 `BTreeMap` 即可；单写者场景用 `Arc<Mutex>` 就够，多写者再考虑 shard 或 channel（ph12 的判断在此复用）。

**与其他语言 / 生态的对照**（为 analysis/ 与 Tenet 合成积累素材）：

- **与 C++ 版 ph22 的分工视角**：cpp/ph22-storage-engine-db-kernel 与本章同主题（同款 WAL/SSTable/Bloom/compaction 磁盘格式语义），但 C++ 版聚焦「磁盘组件的实现细节」（RAII、容器、手写 SkipList、页管理），本阶段聚焦「所有权/安全抽象 × 数据基础设施的组合纪律」（BTreeMap 管内存、Result 管坏文件、trait 管工具边界）并把重点延伸到「服务面 + 工具面 + Python 出口」——examples/ex03 的 compaction 模型在文件头注明参照 cpp/ph22 ex06，可逐字节对照；
- **与 C 版 ph16 存储引擎**：C 路线以「字节纪律 + 全手工内存」收尾；Rust 把同样的字节纪律做成编译期检查——记录格式两路对齐（大端 + CRC 覆盖整段），跨语言可对照；
- **与 Go 生态**：Go 的 KV 组件同样常见（badger、etcd 的 boltdb/bbolt），但内存与并发模型不同——Rust 用所有权表达「谁拥有数据」，Go 用 GC + 值语义，工程后果是「Rust 库可以把内存布局做成公共 API（零拷贝），Go 更依赖接口边界」；
- **与 Python 生态**：Python 侧数据基础设施以「胶水 + 生态」取胜（pandas、sqlalchemy），Rust 组件是它的加速器——pyo3 出口让「热路径 Rust、分析路径 Python」成为 RAG/数据平台的标准分工（呼应全库 py/ph18 的收官分工）。

**什么时候不用这套组件**（把「选它」说清楚之后，边界更清楚）：单机内存就够、无需跨崩溃存活时，WAL/文件层是纯负担——直接用内存 `BTreeMap`；数据量到不了「暴力不可接受」，别为图索引付建图与内存的代价（4.5 的复杂度门槛）；只有单写者、无跨进程消费者时，`Arc<Mutex>` + HTTP 已经越界——先想清楚有没有第二个进程需要这份数据，再决定要不要起服务。

**给分析 / Tenet 合成留一句**：跨语言读下来，数据基础设施的「语言分工」几乎是生态决定的——Rust/C++ 站内核与热路径、Go 站高并发服务的默认态、Python 站分析与胶水；而「WAL→LSM→Bloom→compaction→raft→ANN」这套骨架五十年不变，语言只决定「内存与并发安全谁替你看着」与「库生态长在哪一层」。本阶段所有磁盘格式（大端 + CRC 覆盖整段 + tombstone 语义）与 C/ph16、cpp/ph22 对齐，未来 Tenet 若做数据基础设施方向，可以直接引用这三门语言的同一份字节规范做设计解剖。

## 6. 代码示例

本节展示关键形态，完整工程与运行命令在 [`examples/`](./examples/)。验证环境与依赖版本已在第 2 章基线说明给出。八例的验证状态与实测数字摘要如下（完整运行命令、逐例看点、输出日志见 examples/README）：

| 示例 | 对应主文档 | 一句话说明 | 验证状态（实测摘要） |
|------|-----------|-----------|---------|
| `ex01-wal-replay` | 3.1 | WAL append/sync/replay + torn tail 截断修复 + 位翻转拦截 | 已验证（8 测试；场景 2 残尾 offset=39、场景 3 位翻转 CRC 拦截） |
| `ex02-sstable-bloom` | 3.3/3.4 | SSTable writer/reader（稀疏索引）+ Bloom 假阳性实测 + range scan | 已验证（6 测试；2000 键 / 667 块 / 点查读 1 块 / scan 读 8 块） |
| `ex03-compaction-sim` | 3.5/4.1 | 归并语义 + 读写放大与归并节奏取舍（模型注明参照 cpp/ph22 ex06） | 已验证（6 测试；攒批写 3 809 B vs 全量 13 767 B） |
| `ex04-mini-raft-state-machine` | 3.7 | 单节点 Raft：term/index 日志、commit→apply、崩溃重放；选举概念 | 已验证（5 测试；重放 5 条恢复到 `{"alpha":"10"}`） |
| `ex05-hnsw-toy` | 3.8 | HNSW toy：recall/QPS/P95/内存四件套 + 暴力对照 | 已验证（5 测试；recall@10=0.831、QPS≈1.6 万） |
| `ex06-axum-kv-service` | 3.9 | Axum KV/range-scan HTTP：State、统一错误、curl 冒烟 | 已验证（3 测试 + HTTP 冒烟） |
| `ex07-pyo3-accelerate` | 3.10 | pyo3 0.23.5：帧解析 + L2/top-k（abi3 免链 libpython） | 已验证（Python 3.13 import + verify.py；`cargo test` 不适配 extension crate，如实标注） |
| `ex08-agent-tool-backend` | 3.11 | Agent 工具后端：Tool trait / scope 权限 / 超时 / 审计 / 指标 | 已验证（4 测试 + HTTP 冒烟：403/504 实测） |

```rust
// examples/ex06-axum-kv-service/src/main.rs —— 统一 JSON 错误的最小形态（节选，已验证）
impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, msg) = match self {
            ApiError::NotFound(m) => (StatusCode::NOT_FOUND, m),
            ApiError::Internal(m) => (StatusCode::INTERNAL_SERVER_ERROR, m),
        };
        (status, Json(json!({ "error": msg }))).into_response()
    }
}
```

```bash
# examples/ex05-hnsw-toy —— 四件套实测（本机某次，数字见运行输出）
CARGO_TARGET_DIR=/tmp/ph25-ex05-target cargo run --release
# 查询：recall@10 = 0.831，QPS = 16166（整批 0.025s 除 400 查询），P95 延迟 = 0.133 ms
# 暴力对照：QPS = 25163
```

**示例与练习怎么跑**（每个目录的命令在 examples/README 与 exercises/README 逐例给出；此处给统一骨架）：

```bash
# 纯 std 示例（ex01~ex05）：一个目录内 fmt/clippy/test 一次过
export PATH="$HOME/.cargo/bin:$PATH"; export CARGO_TARGET_DIR=/tmp/ph25-exNN-target  # NN=01~05，每例独立目录
cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test --release && cargo run --release
# 练习（sol-01~sol-04，std 单文件）：用 rustc 直接编译 + 跑内嵌测试
rustc --edition 2021 -D warnings --test sol-0X-*.rs -o /tmp/ph25-sol0X-t && /tmp/ph25-sol0X-t
# 网络依赖示例（ex06/ex08）与收官工程（project/）：cargo 工程，跑法与上同；ex07 走 Python 侧验证
```

**给收官工程的一句话验收**：`project/mini-kv-service/scripts/smoke.sh` 一条命令跑完「HTTP CRUD → range scan → 工具权限与审计 → **重启后 WAL 恢复**」四关——它就是 roadmap 附录「阶段性项目验收标准」里「异步数据基础设施网关 / Agent 工具网关」两条推荐项目的合体缩小版（引擎换成真实持久化组件）。

## 7. 总结

### 关键要点

- **WAL 的第一性原理是「先日志后内存」**：append 返回 ≠ 持久化，fsync 返回才可承诺；重放四道校验（长度→magic→长度闸门→CRC）让崩溃恢复退化成「截断残尾重来」（3.1/ex01）
- **MemTable 用内存有序表把写路径变成「有序的临时状态」**：BTreeMap 管内存安全，tombstone 表达删除——删除是写一条记录，不是 erase（3.2）
- **SSTable 的不可变性是性能与安全的地基**：稀疏索引二分定位块 + 块内升序，点查只读 1 块、scan 读区间（3.3/ex02）
- **Bloom 是「无假阴性」的过滤闸门**：假阳性率 ≈ (1 − e^(−kn/m))^k、k = ln2·m/n；放行的才查文件（3.4/4.4）
- **compaction 的难点全在 tombstone**：非底层归并必须保留删除标记，否则旧值复活；leveled 换「读放大有上界」，代价是写放大（3.5/ex03）
- **Snapshot/MVCC 点到即可**：删除/更新 = 新版本，tombstone 是它的落盘亲戚；本阶段只做「seq + commit 前缀」的最小可见性雏形（3.6）
- **Raft 单节点 = 日志即事实、状态机是投影**：term/index 连续、commit→apply、崩溃重放幂等；多节点靠 RPC + 多数派，是后续方向（3.7/ex04）
- **HNSW toy 必须跑出真实四件套**：recall 对暴力真值、QPS/P95 用 Instant、内存注明口径；toy 尺度诚实承认没跑赢暴力（3.8/ex05）
- **服务面与工具面共享同一条 Rust 纪律**：async + Result 不 panic、锁中毒转 500、工具按 scope 授权 + 预算超时 + 审计记 key 不记 value + 指标可观测（3.9/3.11/ex06/ex08）
- **pyo3 出口让「Python 要快就调 Rust」闭环**：abi3 免链 libpython、测试走 Python 侧 verify.py（3.10/ex07）
- **本阶段直接「使用」ph24 的产物**：deny.toml 与 release-check.sh 复制进 project/ 并注明来源，9 步流水线实跑通过——「安全地写出来」与「可信地发出去」在此汇合（2 章/project）

### 阶段验收清单

- [ ] 能用 WAL 恢复 put / delete 操作（roadmap 验收「能通过 WAL 恢复 put / delete 操作」）：写一批操作后「崩溃」重启，状态与崩溃前一致；手工塞残尾能被截断修复（3.1/ex01/sol-01）
- [ ] 能按 key 查询 SSTable 并能完成基础 range scan（3.3/ex02/project 的 `/kv?start=&end=`）
- [ ] 能解释 LSM 的读放大、写放大和空间放大，并说出归并节奏如何取舍（3.5/4.1/ex03）
- [ ] 能解释 Raft 的 leader election 和 log replication 概念，并跑通单节点「选举→写→提交→崩溃恢复」链（3.7/ex04/sol-03）
- [ ] 能输出向量检索 recall、QPS、P95 延迟和内存占用（真实测量，3.8/ex05/sol-04）
- [ ] 能设计可被 Agent 调用的稳定工具 API：权限 scope、超时预算、审计日志、指标计数（3.11/ex08）
- [ ] 能构建 Python 调用 Rust 的加速模块并说明测试形态（3.10/ex07）
- [ ] 能用一份含持久化、HTTP、工具调用的服务通过「WAL 恢复 / range scan / HTTP CRUD / 工具调用冒烟」四关（project/）

### 跨语言对比

- Rust 数据基础设施的差异化卖点是「**内存布局 + 并发安全可以被类型系统约束**」：C++ 用 RAII 与容器约定、Go 用 GC、Python 靠胶水，Rust 把「谁拥有这块内存、能不能共享、坏文件只能报错不能 panic」压进编译期；而「字节格式、WAL 纪律、归并语义」这类五十年不变的存储内核与 C/ph16、cpp/ph22 完全同源——跨语言可逐字节对照（为 analysis/ 与 Tenet 合成积累素材，详见 5 节）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。四题与 roadmap 第 25 节练习一一对应：练习 1 =「实现 WAL append/replay 与 MemTable」（sol-01），练习 2 =「实现 Mini SSTable writer/reader 并增加 Bloom Filter」（sol-02），练习 3 =「实现基础 compaction 与 Mini Raft 单节点状态机」（sol-03），练习 4 =「实现 HNSW toy version 并输出 recall/QPS 指标」（sol-04）；roadmap 第 5 条（Axum + pyo3）已由 examples/ex06+ex07 完整落地。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**mini-kv-service——Mini LSM-KV 持久化引擎 + Axum HTTP + Agent 工具 API 的三合一收官服务**。验收四关：WAL 恢复（同一 KV_DATA 重启后数据还在）、range scan（`/kv?start=&end=`）、HTTP CRUD（PUT/GET/DELETE 状态码与 JSON 错误）、工具调用冒烟（writer 可 put、reader 越权 403、`/audit`/`/metrics` 有记录）。实测：`cargo test --release` 5 测试全绿、`./scripts/smoke.sh` 四关全过、`./release-check.sh` 9 步通过（复用 ph24 的 deny.toml 与流水线形态）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部 4 题并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其四关验收（`cargo test` 全绿 + smoke.sh 四关 + release-check.sh 9 步）

### 下一阶段

**本阶段是 Rust 学习路线的终点（roadmap 第 25 节即最后一节，无 ph26）**——ph01~ph25 走完「语法 → 所有权 → 数据结构 → Option/Result → 模式匹配 → Cargo/模块 → trait/泛型 → 生命周期 → 迭代器 → 智能指针 → 错误处理 → 并发/async → 系统编程 → unsafe → 宏 → Edition/工具链 → Crate 生态 → Borrow Checker 调试 → 内存布局/零拷贝 → 测试体系 → 代码质量/CI → 性能剖析 → FFI → 供应链/发布 → 数据基础设施」的完整闭环，收官在「安全可信的数据基础设施组件」上：WAL 让状态跨崩溃活下来、SSTable/Bloom 让数据被有序高效找到、Raft 心智让单机一致性模型清晰、HNSW toy 让近似检索可测、Axum/pyo3/工具 API 让组件可服务、可信——「安全地写出来」与「可信地发出去」在这里汇合。终点之后不再另设编号阶段，但有几个可继续深入的**方向**（各自通向别处，而非 Rust 路线的新阶段）：

- **分布式共识生产化**：把 Mini Raft 单节点状态机接上真实 RPC 与多数派——raft-rs / TiKV 是最直接的阅读与参与对象；
- **列式 / 时序存储**：在有序 KV 之上做列式块、压缩与谓词下推——arrow / datafusion / influxdb 的 Rust 侧都是样本；
- **向量库工程化**：给 HNSW toy 补量化训练、启发式邻居选择、并发写入与持久化格式，向 Faiss / Milvus 的工程能力靠拢；
- **Agent 框架层**：把本阶段的工具后端接上编排 / 规划 / 记忆 / 多工具协同，工具边界直接复用。

把最后一句话带出 Rust 路线：**存储组件的每一条日志、每一层文件、每一次归并，都是「把不确定性关进可控结构」的练习——而这正是所有权系统教你的同一件事。** 至此 Rust 25 个阶段全部完成：恭喜，去写下一个真实系统的安全内核吧。
