# ph22 阶段项目：Mini LSM KV（WAL + MemTable + SSTable + Bloom 串成一台 mini KV）

> 对应 roadmap §22「推荐项目」之一，**落地选择「Mini LSM KV」**：roadmap §22 推荐了六个项目——Mini WAL（由 examples/ex01 + exercises/sol-01 覆盖）、Mini SSTable（examples/ex02 + sol-02）、Buffer Pool toy（examples/ex04 + sol-04）、简化 B+Tree（exercises/sol-02 之外属主文档 3.6 的概念对照，不做项目落地）、LevelDB 源码分析（主文档 3.10 给出阅读引导）、**Mini LSM KV（本 project）**。它把 WAL + MemTable + SSTable + Bloom + Iterator 读面串成一条完整写/读/恢复路径，兑现 ph21 project 写在「扩展方向」里的全部预告（接 WAL、flush 成 SSTable、为点查加 Bloom）。

## 需求

实现一个嵌入式 mini KV 库，数据目录里跑一台可重启恢复的 LSM 骨架：

- **写路径**：`put/del` → 先追加 WAL 并 fsync（崩溃恢复保险）→ 写 MemTable → MemTable 估算字节超阈值自动 flush 成新 SSTable 并作废旧 WAL
- **读路径**：`get` → MemTable（最新，含 tombstone 判定）→ SSTable 从新到旧逐层回退，每层先过 Bloom Filter（"不在"零数据区 IO），遇 tombstone 即判不存在、不等更旧层
- **range scan**：把全部层按"旧 → 新"归并到有序视图（tombstone = erase、新 put = 覆盖），返回跨 MemTable + 全部 SSTable 一致的活数据
- **恢复路径**：open 时 replay WAL 重建 MemTable（残尾自动 ftruncate 修复）、按编号升序载入全部既有 SSTable
- **组件**：`wal.h`（record 格式 + replay 校验，见 examples/ex01 同款纪律）、`skip_list.h`（**复制自 ph21 project，ph21 阶段作品，未改动**——MemTable 底层的概率平衡有序结构）、`bloom.h`（素数位数组 + 双哈希）、`sstable.h`（数据区 + 稀疏索引 + bloom 区 + 定长 footer）、`lsm.h`（引擎层）

## 功能清单

- [x] `wal.h`：append-only WAL（magic/type/长度前缀/CRC32，大端）；replay 容忍缺失文件与残尾；`truncate_to` 修复；`reset` 作废重建
- [x] `bloom.h`：Bloom Filter（每 key ~10 位素数位数组、k=7 双哈希）；序列化落盘（k 与 m 精确持久化）
- [x] `sstable.h`：writer（block 内升序 entry、稀疏索引、bloom 区、28 字节 footer）与 reader（footer → bloom → 索引二分 → 块内顺扫；三态返回 none/deleted/value；整表顺序读接口供归并）
- [x] `lsm.h`：引擎层——put/del（先 WAL 后 MemTable）、自动/手动 flush、get（MemTable → SSTable 新到旧 + tombstone 遮挡）、range_scan（旧→新归并）、open 恢复（WAL replay + 残尾修复 + 载入 SSTable）
- [x] `mini_lsm.cpp`：4 组自测（基础语义 / WAL replay 与残尾 / 手动 flush 多层 + tombstone 跨层 / 自动 flush + bloom 拦截 + 全量重启恢复）
- [x] Makefile：`make` / `make test` / `make cross` / `make sanitize` / `make clean`

## 验收标准

- [ ] `make clean && make test` 退出码 0，输出 4 组场景行 + `ph22-project-minilsm OK`（已验证：323 项断言全绿）
- [ ] **重启后 WAL replay 恢复**：不 flush 直接销毁引擎（模拟崩溃）+ 手工塞残尾字节 → 重开引擎全部 put 恢复、日志继续可追加（自测 [2]）
- [ ] **range scan 跨 MemTable + SSTable 一致**：两个手动 flush 的 SSTable + 留在内存的 MemTable，重启后全表 scan 与 ground truth 完全一致，tombstone 跨层遮挡生效（自测 [3]）
- [ ] 自动 flush 出多个 SSTable、重启后 40/40 恢复（自测 [4]）；Bloom 拦截计数在大量不存在点查后显著增长（0/1 → 600）
- [ ] Apple clang 21.0.0 与 Homebrew clang 21.1.8 双编译器 `-std=c++20 -Wall -Wextra` 零警告、断言全绿（`make cross`，已验证）；`make sanitize` ASan/UBSan 零报告（已验证）
- [ ] `make clean` 零残留（产物在 /tmp，数据目录 /tmp/ph22-proj-d1~d4 一并清掉）
- [ ] 能口头说清：为什么删除要写成 tombstone 而不是从 MemTable erase 节点（否则删除无法跨 flush 持久化）；为什么 flush 后旧 WAL 可以直接作废（op 已全部固化进 SSTable）；为什么 Bloom 里必须包含已删 key（否则删除会被 bloom 误拦、旧值复活）

## 验证

```bash
make            # 1. 构建（-std=c++20 -Wall -Wextra, 零警告）
make test       # 2. 自测（323 项断言，退出码 0）
make cross      # 3. Homebrew clang 21.1.8 交叉编译运行（可选）
make sanitize   # 4. ASan/UBSan 复跑（先 make clean）
make clean      # 5. 清理 /tmp 产物与数据目录
```

验证环境：macOS arm64，Apple clang 21.0.0（`/usr/bin/clang++`）+ Homebrew clang 21.1.8（`/opt/homebrew/opt/llvm/bin/clang++`），libc++，make 3.81+。实测输出摘要：

```text
[1] 基础语义: scan = beta=22
[2] WAL replay 恢复: 5/5 命中, k6=v6
[3] 重启后全表 scan: k01=va k02=vb k03=vb k04=va k06=va k07=va k08=va k09=va k10=vc
[4] 自动 flush: sstable=2, bloom 拦截计数 1 -> 600
[4] 重启后恢复 40/40, scan 条数 40
checks: 323, failed: 0
ph22-project-minilsm OK
```

## 教学简化与取舍（均已在源码注释注明）

- 单线程；SSTable 只增不并——**compaction 未实现**（归并语义/放大计量见 examples/ex06 与主文档 3.5/4.1，属后续工程动作）
- MemTable 值形态用 `deleted` 位表达删除；key/value 为文本；单条 ≤ 64 KiB
- flush 后 WAL 直接作废（生产会保留到旧 WAL 对应的 SSTable 安全落盘后，见主文档 3.2）
- `range_scan` 对每个 SSTable 做整表顺序读（教学尺度可接受；生产是各层迭代器 + 堆归并，见主文档 3.9/ex05）
- 引擎接口不带锁；并发/无锁 skip-list 改造超出本阶段

## 扩展方向（与后续阶段的关系）

- **compaction 策略**（leveled/tiered 调参与放大优化）：把多代 SSTable 合并、清掉 tombstone——主文档 3.5/4.1 + examples/ex06 已备好计量心智
- **group commit**：多条 WAL 攒批一次 fsync（主文档 4.3 的组提交；ex01/ex02 有逐条 vs 批量实测数量级差距）
- **Buffer Pool 接文件页**：本 project 的 SSTable 直接整文件读内存；换成 examples/ex04 的帧缓存 + LRU/Clock 淘汰即接近真实引擎
- **MVCC/Snapshot**：在 MemTable/记录上挂版本号（主文档 3.8）→ 引擎从"最新值"变"每个快照一致的值"
- **键分区 + 范围挑文件**：compaction 与查询按 key 区间只碰相关文件（本 project 按全量处理，见主文档 3.5 leveled 的挑文件优化）
- **向量索引持久化**：SSTable/Buffer Pool 的磁盘管理思路会被 ph23 向量检索与 AI 推理引擎方向 C++（roadmap 第 23 节，目录待建）的向量索引持久化复用；阶段预告与验收清单见 ph22 主文档 [22-storage-engine-db-kernel.md](../22-storage-engine-db-kernel.md) 第 7 章
