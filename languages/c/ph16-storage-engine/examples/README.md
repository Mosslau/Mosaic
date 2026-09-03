# examples —— C 语言数据库存储引擎基础阶段完整示例

本目录是主文档第 6 章示例 1~6 的完整可运行版。**六个示例覆盖 roadmap ph16「学习内容」9 项中的六项**：WAL record 设计（ex01）、append-only log 与 replay（ex02）、MemTable（ex03）、SSTable 文件格式（ex04）、Bloom Filter（ex05）、Buffer Pool / LRU（ex06）；其余三项不在本目录——B+Tree 基础与 LSM Tree 基础分别由 exercises/sol-05 与 project/ 落地，range scan 与 iterator 不设独立示例，在 ex03 的区 4（下标区间即迭代器）与 ex04 的块内顺扫中演示。

验证环境（本机实测）：**Apple clang 21.0.0**（`cc`，macOS arm64，ProductVersion 26.6.2）。全部 C 代码 `cc -Wall -Wextra -std=c11` 零警告；产物一律写 `/tmp/ph16c-ex/`，演示数据写 `/tmp/ph16c-ex-data/` 且示例退出时自行删除，仓库零残留。

## 一键构建与运行

```bash
make all      # 1. 构建并运行全部示例（输出即验证结果）
make ex01     # 2. 只跑某个（ex01 ~ ex06）
make clean    # 3. 清理 /tmp/ph16c-ex 与 /tmp/ph16c-ex-data
```

## 示例清单

| 组 | 文件 | 覆盖主题 | 验证状态 |
|----|------|---------|----------|
| ex01 | `ex01-wal-record.c` | WAL record 设计：magic/type/klen/vlen/payload/crc32 布局、大端编码、编解码往返、CRC 与 magic 拦截 | 已验证：零警告，退出码 0；往返 rc=0、翻转 1 字节 rc=-5、破坏 magic rc=-2 实测 |
| ex02 | `ex02-append-replay.c` | append-only log 与 replay：O_APPEND、write_full、fsync 边界、四道校验、残尾识别与 ftruncate 修复、吞吐实测 | 已验证：零警告；回放 PUT=2/DEL=1、残尾偏移 76、修复后干净 EOF 实测；吞吐实测批量 fsync 约 48 万~80 万条/s vs 每条 fsync 约 4.0 万~5.3 万条/s（差约 11~18 倍，数值随机器波动） |
| ex03 | `ex03-memtable.c` | MemTable：有序动态数组 + 二分定位、覆盖、tombstone 删除、range scan（下标区间即迭代器） | 已验证：零警告；乱序写入保序、覆盖生效、tombstone 后 get 未命中、区间 [apple,cherry] 扫描输出实测 |
| ex04 | `ex04-sstable.c` | SSTable 文件格式：数据区 + 稀疏索引 + 定长 footer、索引二分 + 块内顺扫、tombstone | 已验证：零警告；10 条写入 209 字节文件、get(fox) 索引二分 2 步命中、tombstone/范围外 key 返回"不存在"实测 |
| ex05 | `ex05-bloom-filter.c` | Bloom Filter：位数组、双哈希法（h1+i*h2）、误判率实测 vs 理论、无假阴性 | 已验证：零警告；1 万 key 回查漏报 0；10 万探测实测误判 0.46%（理论 0.82%，键序列确定故结果可复现；偏差来自双哈希与 FNV-1a 的非理想独立性） |
| ex06 | `ex06-lru-buffer-pool.c` | Buffer Pool / LRU：哈希表 + 双向链表 O(1)、LRU 淘汰、脏页写回、命中率统计 | 已验证：零警告；12 次访问命中 2 次、淘汰页 1/3/0/4/5 顺序实测、脏页 2 写回 1 次且重载后数据未丢 |

## 逐文件命令（可复现）

```bash
mkdir -p /tmp/ph16c-ex    # 0. 先建产物目录（make all / make exXX 会自动建）

# ex01 WAL record 设计（编码/解码/CRC 拦截）
cc -Wall -Wextra -std=c11 ex01-wal-record.c -o /tmp/ph16c-ex/ex01 && /tmp/ph16c-ex/ex01

# ex02 append-only WAL（追加/replay/残尾/吞吐实测）
cc -Wall -Wextra -std=c11 ex02-append-replay.c -o /tmp/ph16c-ex/ex02 && /tmp/ph16c-ex/ex02

# ex03 MemTable（有序内存表 + tombstone + range scan）
cc -Wall -Wextra -std=c11 ex03-memtable.c -o /tmp/ph16c-ex/ex03 && /tmp/ph16c-ex/ex03

# ex04 SSTable（writer/reader + 稀疏索引 + footer）
cc -Wall -Wextra -std=c11 ex04-sstable.c -o /tmp/ph16c-ex/ex04 && /tmp/ph16c-ex/ex04

# ex05 Bloom Filter（误判率实测 vs 理论; 需 -lm）
cc -Wall -Wextra -std=c11 ex05-bloom-filter.c -o /tmp/ph16c-ex/ex05 -lm && /tmp/ph16c-ex/ex05

# ex06 Buffer Pool / LRU（淘汰与脏页写回）
cc -Wall -Wextra -std=c11 ex06-lru-buffer-pool.c -o /tmp/ph16c-ex/ex06 && /tmp/ph16c-ex/ex06
```

## 说明

- 主文档第 6 章内嵌片段摘录自本目录文件的关键部分（节选可能省略无关行、调整缩进，完整文件以本目录为准），两者内容一致。
- ex02 的吞吐数字与 ex05 的误判率是实测值：ex02 每次运行随机器负载波动（比例结论稳定），ex05 因键序列确定、每次运行结果完全相同。macOS 的 `fsync` 只到设备缓存，真落盘需 `fcntl(F_FULLFSYNC)`（ph13 examples/ex03 已展开），故 ex02 的"每条 fsync"差距在 Linux 上会更大。
- 与前置阶段的衔接：ex01/ex02 的记录格式是 ph13 project/ kvlog（`magic+len+crc`）与 ph14 project/ kvdb 的升级——增加 `type` 字段区分 PUT/DEL；字节序纪律（显式大端）来自 ph12；write_full/fsync 纪律来自 ph13。
- B+Tree 没有对应 ex 文件：内存版简化 B+Tree 是 exercises 练习 5（sol-05-btree.c，含分裂/查找/范围扫描自测），避免与练习重复；LSM 串联见 project/。
