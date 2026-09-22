# exercises —— Rust 数据基础设施专项阶段练习

四题与 roadmap 第 25 节练习一一对应：练习 1 =「实现 WAL append / replay 与 MemTable」（sol-01），练习 2 =「实现 Mini SSTable writer / reader 并增加 Bloom Filter」（sol-02），练习 3 =「实现基础 compaction 与 Mini Raft 的单节点状态机」（sol-03），练习 4 =「实现 HNSW toy version 并输出 recall / QPS 指标」（sol-04）。roadmap 第 5 条练习「用 Axum 暴露 KV / 检索 API，并用 pyo3 暴露一个解析函数给 Python」已由 [`examples/ex06-axum-kv-service`](../examples/) 与 [`examples/ex07-pyo3-accelerate`](../examples/) 完整落地，练习不再重复出题。参考实现在 `sol-*.rs`，**先自己做，做完再看**。每题标注难度（★~★★★）。

**本阶段铁律**：存储/检索练习里所有「性能类数字」（QPS、P95、构建耗时）必须来自本机实跑；正确性断言（恢复后状态一致、recall 上界、写入字节对比）不许拍脑袋——把断言写进代码，跑不过就是不过。

验证环境：rustc/cargo **1.92.0**（macOS arm64）。sol-01~sol-04 均为 **std 单文件**，离线可复现；统一验证命令（以 sol-01 为例）：

```bash
# 编译并运行自检演示（内部有 assert，输出符合预期即通过）
rustc --edition 2021 -D warnings sol-01-wal-memtable-engine.rs -o /tmp/ph25-sol01 && /tmp/ph25-sol01
# 编译并跑内嵌单元测试
rustc --edition 2021 -D warnings --test sol-01-wal-memtable-engine.rs -o /tmp/ph25-sol01-t && /tmp/ph25-sol01-t
```

## 练习 1：WAL append / replay 与 MemTable（★★）

**目标**：把「先写日志再改内存」落成一台能重启恢复的迷你引擎（roadmap 练习「实现 WAL append / replay 与 MemTable」；对应主文档 3.1）。

**要求**：用 `std::fs` + `std::collections::BTreeMap` 实现单文件引擎：
1. `MiniEngine::open(dir) -> Result<MiniEngine>`：若目录已有 WAL 则重放到内存表（重建 put/delete 后的状态），并处理**残尾**（最后一条写了一半：截断到最后一个完整 record，不 panic）；
2. `put(key, value)` / `delete(key)`：先把 record **append 进 WAL 文件**，再改内存表（删除 = 写一条 Delete record + 从内存表移除——日志只增不改）；
3. `get(key)`、`flush()`（fsync 语义要说清楚：append 返回 ≠ 持久化）；
4. record 格式自己定（建议沿用主文档 3.1 与 C/ph16、cpp/ph22 对齐的大端布局：magic/type/klen/vlen/payload/crc，CRC 覆盖 type..payload），字段上限与 CRC 缺一不可。

**验收**：演示代码里至少覆盖——① 20 次交错 put/delete 后 `flush` + 关闭，`open` 重开状态完全一致；② 向日志尾部手工追加 5 字节垃圾后 `open` 自动截断修复且能继续写；③ 翻转某条 payload 一字节后 `open` 停在损坏点之前且不崩溃。写清「append 与 fsync 的差别」一句话。

参考实现：`sol-01-wal-memtable-engine.rs`。

## 练习 2：Mini SSTable writer / reader + Bloom（★★）

**目标**：把有序键集合变成「不可变有序文件 + Bloom 点查拦截」并可读回（roadmap 练习「实现 Mini SSTable writer / reader 并增加 Bloom Filter」；对应主文档 3.2/3.3）。

**要求**：不用第三方 crate，单文件实现：
1. `write_sstable(entries: &[(Vec<u8>, Vec<u8>)], bits_per_key) -> Vec<u8>`：输入已按 key 升序，输出字节镜像（entry 长度前缀 + 排序偏移索引 + Bloom 位图 + 定长 footer，布局自定但要能自述）；把镜像 `std::fs::write` 落盘后读回；
2. `Table::open(bytes) -> Table`：解析 footer → 偏移索引 → Bloom；`get(key)` 先过 Bloom（false 即无），再二分定位；`scan(start, end)` 有序返回；
3. Bloom 用双散列（确定性实现），把 `m`、`k` 打印出来；对 2000 个不存在的 key 量一次假阳性率。

**验收**：演示与断言——① 500 个 key round-trip 后全部 `get` 命中、值正确；② 不存在的 key 返回 `None`；③ 反序输入要被拒绝（报 OutOfOrder 类错误）；④ 打印假阳性率（≤5% 才算 Bloom 参数没配错）。写清「为什么删除在 SSTable 里是 tombstone 而不是物理删行」一句话。

参考实现：`sol-02-mini-sstable-bloom.rs`。

## 练习 3：基础 compaction + Mini Raft 单节点状态机（★★★）

**目标**：做对「归并语义」与「先日志后状态机」，两台迷你实现（roadmap 练习「实现基础 compaction 与 Mini Raft KV 的单节点状态机」；对应主文档 3.4/3.5）。

**要求**（分两部分，写进同一文件）：
- **Part A — compaction 归并**：实现 `merge_two(newer, older) -> Vec<Entry>`（Entry 含 key/value/seq/deleted）。语义：同名 key 取 seq 大者；若胜者是 tombstone 则 key 彻底消失（本练习只做「两 run 全量归并到底」）；输出必须升序。附带断言：跨 run 覆盖、跨 run 删除、同 run 后写覆盖三类样例。
- **Part B — Mini Raft 单节点**：实现 `RaftNode`：内存日志条目 `(term, index, op)`；`append` 后 `commit`、按 `commit_index` 顺序 `apply` 到 K-V 状态机；`recover()` 模拟崩溃重启——清空状态机仅凭日志重放，结果与崩溃前一致。附断言：重复 apply 幂等、index 连续、恢复一致。

**验收**：演示输出覆盖——A：3 个跨 run 语义样例的归并结果；B：election（term 单调 + 自投票）→ 写 → 提交 → 崩溃恢复一条链。用一段话说明「tombstone 在非底层 compaction 中为什么不能丢」。

参考实现：`sol-03-compaction-mini-raft.rs`。

## 练习 4：HNSW toy + recall/QPS 输出（★★）

**目标**：用一个**你自己实现的**近似最近邻图索引输出 recall / QPS / P95 / 内存四件套（roadmap 练习「实现 HNSW toy version 并输出 recall / QPS 指标」；对应主文档 3.6）。不需要复刻 examples/ex05 的完整多层 HNSW——实现到什么程度都行，**但数字必须真实**。

**要求**：
1. 确定性数据（示例给的多簇高斯生成器可自取），入库 1000 个、查询 100 个（样本外）；
2. 暴力 top-10 作真值，算 `recall@10`；
3. 用 `std::time::Instant` 实测：查询整批耗时 → QPS；逐查询计时排序取 P95 延迟；内存按结构成员计算估计并注明口径；
4. 做一次「搜索宽度」扫描：两种参数（如候选集 20 vs 80）各输出一行，断言 recall(宽) > recall(窄)——让「recall 与吞吐的权衡」成为可复现观察。

**验收**：演示输出两行参数对照 + 四件套；断言 recall(宽) > recall(窄) 通过；解释一句「为什么更宽的候选集换来更高 recall 却更慢」。

参考实现：`sol-04-hnsw-toy-metrics.rs`。

做完四题后，存储的「恢复 / 点查 / 归并 / 一致性」与检索的「近似召回与吞吐」都亲手写过一遍——去 `project/` 把它们装进一台「Mini LSM KV + Axum HTTP + Agent 工具 API」的三合一收官服务。
