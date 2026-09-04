# ph22 C++ 存储引擎与数据库内核专项阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。题目与参考实现分离：本 README 只出题，答案在 `sol-*` 文件里，做完再看。

完成顺序建议：按 1~5 顺序完成，与 roadmap §22「练习」小节一一对应（append-only WAL 写入与 replay / SSTable block header + Mini writer-reader / 为 SSTable 增加 Bloom Filter / LRU Cache / Iterator 抽象 range scan）。练习里卡住先看 examples/ 的手法：WAL 与残尾修复看 `ex01`、SSTable 布局看 `ex02`、Bloom 本体与素数位数组看 `ex03`、页帧淘汰/pin/脏页看 `ex04`、归并迭代器看 `ex05`。**每题参考实现均已实测**（验证命令与状态见文末汇总）。

> ⚠️ 通用验收基线：`clang++ -std=c++20 -Wall -Wextra` 编译零警告、运行断言全绿、退出码 0；手写结构必须带复杂度/语义注释；文件 IO 一律写 /tmp 且退出自删（仓库不落二进制）。

## 练习 1：append-only WAL 写入与 replay（★★）

- **目标**：实现 WAL 的最小闭环——写入是 append-only、崩溃后靠 replay 把日志恢复成内存态
- **要求**：
    - 自定 record 格式（必须含：类型、key、value、校验与"能跳读的下一条定位"；可加 seq/magic）
    - `append` 与 fsync 分离：攒批一次 `fsync`（体会 group commit 的雏形），同步点由调用方决定
    - replay 四道校验后能报告"残尾偏移"并停止；`repair(offset)` 截断后日志回到干净状态且可继续追加
    - 用 replay 把 put/del 恢复进 `std::map`，证明删除（tombstone 记录）也被正确重放
    - 边界：日志尾部不足一条记录（半条残尾）、中间一字节损坏（CRC 拦截）都要被识别，不许静默吞错
- **验收**：4 条 op（2 put + 1 覆盖 + 1 del）replay 后 map 只剩覆盖后的新值；塞 8 字节残尾后 replay 报告偏移、`repair` 后再追加能继续；翻转第二条 payload 一字节后 replay 停在第二条起始偏移（参考实现 `sol-01-wal-replay.cpp`）
- **提示**：校验范围必须与编码范围完全一致（跳 magic 或含头，二选一并写进注释）；"残尾"判定用"文件尾 > 已解析位置"而不是"本次读到的字节数"（参考实现曾在此踩坑，注释有标注）

## 练习 2：设计 SSTable block header + Mini SSTable writer/reader（★★★）

- **目标**：从零定一个 block 粒度的不可变有序文件格式，写出 writer/reader 并通过点查验证
- **要求**：
    - 文件布局含三区：数据区（block 内 entry 升序）、稀疏索引（每块首 key → 块偏移）、定长 footer；多字节字段用固定字节序
    - **为 block 设计 header**（至少含条数，强烈建议加校验和）并解释每个字段的用途；校验失败时应"抛异常拒绝服务"而不是返回可能错误的数据
    - 点查路径：读 footer → 载入索引二分 → 读目标 block（校验）→ 块内线性找 key
    - 边界：跨 block 命中、末 block 不满、小于全文件最小 key 的查询零数据区扫描、篡改数据区一字节后点查报错
- **验收**：9 条记录按 4 条/块写出 3 个 block，四类点查断言全绿；篡改后抛 `std::runtime_error`；能口头说清"索引为什么稀疏""block header 的校验和为什么是必要的"（参考实现 `sol-02-mini-sstable.cpp`）
- **提示**：索引项记录"块首条落盘前"的偏移（块起点），不是封块时的位置；校验和必须覆盖整块（含 header 与全部 entry），搜索过程中不要提前跳出导致只校了一半

## 练习 3：为 SSTable 增加 Bloom Filter（★★）

- **目标**：把 Bloom Filter 挂到点查路径最前端，把"省了多少数据区 IO"变成可计数的指标
- **要求**：
    - 建表时把全部 key（**含 tombstone 的 key**——否则删除会被 bloom 误拦导致旧值复活）编进位数组并随表落盘（meta 里带 k 与位数组参数）
    - reader 点查顺序：bloom 说"不在" → 零数据区解码直接返回；"可能在" → 才走数据区
    - 统计：bloom 拦截次数、放行次数、假阳性（放行却查无此 key）次数、数据区实际解码条数
    - 位数组大小选素数或等价的 2 的幂方案，并在注释解释为什么（可对比 ex03 注释里偶数 m 的翻车实测）
- **验收**：1000 条表（含 ~9% tombstone）下真 key 零假阴性；20000 次不存在查询拦截率 > 95%，且能报出假阳性白读的次数与代价；能解释"为什么 tombstone 也必须进 bloom"（参考实现 `sol-03-bloom-sstable.cpp`）
- **提示**：位数组的"总位数 m"要精确落盘（reader 用字节数反推 m 会因为 ceil 而错位——参考实现注释里有这个坑）；删除标记藏在空 value 里只是教学简化

## 练习 4：LRU Cache 升级为页帧缓存（★★）

- **目标**：在 ph21 练习 1 的 LRU 本体上加页帧语义——pin/unpin、脏页写回、按帧淘汰
- **要求**：
    - 容量 = 帧数；`fix(id)` 返回帧内可写数据（帧地址在 unfix 前稳定），`unfix(id)` 归还
    - 帧三态位：dirty（改完标脏）、pin 计数（>0 绝不淘汰）、LRU 顺序（只对"未钉帧"维护）
    - 淘汰时：写回脏页 → 从索引摘除 → 复用帧；backing store 用内存 map 模拟（页为定长字节块）
    - 自拟能证明"命中即提前 / pin 保护 / 脏页写回"的序列（不要抄 ex04 或本仓库其他文件的测试序列）
- **验收**：容量 3 写满 1/2/3 后再取 4 → 淘汰 1 且磁盘上是写回后的值；访问 2 后再满 → 淘汰的是 3 不是 2；钉住某页时取新页 → 被钉页存活、淘汰的是另一未钉页（参考实现 `sol-04-lru-page-cache.cpp`）
- **提示**：`fix` 命中且该帧从未钉变钉住时要把它从 LRU 候选链表里摘掉，`unfix` 到 0 再放回头部——忘记"摘/放"就是 ph21 说的"LRU 退化成 FIFO"的帧缓存版

## 练习 5：Iterator 抽象：MemTable 与 SSTable 的 range scan（★★★）

- **目标**：把内存表与磁盘表接到同一张"迭代器读面"上，实现跨源有序合并扫描
- **要求**：
    - 定义 `Iterator` 接口（valid/next/seek/key/value，seek = lower_bound 语义）；MemTable 与 SSTable 各自实现
    - MemTable 允许"删除标记"（教学简化：空 value）；归并规则：同 key 取最新源，最新一份是删除标记则整个 key 从读面消失（遮挡旧层残余值）
    - `seek(key)` 后应只输出 ≥ key 的活数据；全表 scan 输出严格有序、无重复 key
    - 至少两个磁盘源 + 一个内存源（新→旧排序），值不可与 examples/ex05 的测试数据雷同
- **验收**：内存层删除的 key 在全表 scan 与点查中都不可见（即使旧 SSTable 里有值）；同 key 内存新值赢磁盘旧值；从某个 key 起 seek 的数量正确（参考实现 `sol-05-iterator-range-scan.cpp`）
- **提示**：归并每步做三件事——取最小 key → 最新值是删除标记则让所有同 key 源前进并继续选 → 否则输出并跳过同 key 的旧源；"删除是最新状态"的判断要在"赢家"身上做

## 验证状态汇总

| 练习 | 参考实现 | 工具链 | 状态 |
|------|---------|--------|------|
| 1 WAL replay | `sol-01-wal-replay.cpp` | Apple clang 21.0.0 + Homebrew clang 21.1.8 | 已验证（双编译器零警告、断言全绿） |
| 2 Mini SSTable | `sol-02-mini-sstable.cpp` | Apple clang 21.0.0 + Homebrew clang 21.1.8 | 已验证（含篡改检测断言） |
| 3 SSTable + Bloom | `sol-03-bloom-sstable.cpp` | Apple clang 21.0.0 + Homebrew clang 21.1.8 | 已验证（拦截率/假阳性/解码计数断言） |
| 4 LRU 页帧缓存 | `sol-04-lru-page-cache.cpp` | Apple clang 21.0.0 + Homebrew clang 21.1.8 | 已验证 |
| 5 Iterator range scan | `sol-05-iterator-range-scan.cpp` | Apple clang 21.0.0 + Homebrew clang 21.1.8 | 已验证（含删除遮挡断言） |

统一命令示例（每个 sol-* 文件头注释自带其命令）：

```bash
clang++ -std=c++20 -Wall -Wextra sol-01-wal-replay.cpp -o /tmp/ph22-sol01 && /tmp/ph22-sol01
```
