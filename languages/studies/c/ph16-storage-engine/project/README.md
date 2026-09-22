# ph16 阶段项目：lsmkv —— 简化 LSM KV 文件层

> 对应 roadmap ph16「推荐项目」第三个「简化 LSM KV 文件层」（另三个推荐项目「Mini WAL」「Mini SSTable」「Buffer Pool toy」分别由 examples/ex02、ex04、ex06 与 exercises 练习 1/2/4 覆盖）。一个把 **WAL + MemTable + SSTable + Bloom Filter** 串成完整 mini KV 的存储引擎：写入先落 WAL 再写 MemTable，写满 flush 成不可变 SSTable，查询从内存到磁盘逐层回退、每层先过 Bloom Filter——ph13 project/ 的 kvlog（append-only log）在这里正式升级为带 type 的完整 WAL，ph15 的方法论（稳定错误码、分层模块边界、自测断言）贯穿全部代码。

## 需求

实现一个嵌入式 KV 库与命令行工具 `lsmkv`：

- **写入路径**：`put/del` → 先追加 WAL 并 fsync（崩溃恢复保险）→ 写 MemTable（有序动态数组 + 二分定位）→ MemTable 超 4 KiB 自动 flush 成新 SSTable 并清空 WAL
- **查询路径**：`get` → MemTable（最新）→ SSTable 从新到旧；每层先查 Bloom Filter，"肯定不在"则零数据区 IO；tombstone（DEL 记录）遮挡所有更旧的层
- **恢复路径**：open 时 replay WAL 重建 MemTable（残尾识别 + ftruncate 修复），并载入目录下全部既有 SSTable（编号升序 = 从旧到新）
- **WAL 记录格式**（大端，承接 ph13 kvlog / ph14 kvdb 并加 type）：`[magic "WAL1" u32][type u8][klen u32][vlen u32][key][value][crc32 u32]`
- **SSTable 文件格式**（大端）：数据区（升序 entry）+ 稀疏索引（每 4 条 1 项）+ Bloom 位数组 + 32 字节定长 footer
- **命令行**：`put / get / del / flush / stats` / `test`（自测套件，退出码即结果）
- **教学版简化**：单线程、无 compaction（SSTable 只增不并）、key/value 为不含 NUL 的文本、单条 key+value ≤ 4 KiB、SSTable 上限 64 个

## 功能清单

- [x] `wal.c/h`：带 type 的 WAL——append（O_APPEND + write_full）/ sync（fsync）/ replay（四道校验 + 残尾报告）/ repair（ftruncate）
- [x] `memtable.c/h`：有序 MemTable——二分定位 put/覆盖、tombstone 删除、三态查询 `mt_probe`（命中/不存在/tombstone）
- [x] `bloom.c/h`：Bloom Filter——位数组 + FNV-1a 双哈希（k=7，每 key 10 位）
- [x] `sstable.c/h`：SSTable writer（数据区 + 稀疏索引 + bloom + footer）与 reader（open 载入索引/bloom，get 先 bloom 后二分再块内顺扫，tombstone 三态返回）
- [x] `lsm.c/h`：引擎层——写入/查询/恢复三条路径、自动 flush、SSTable 从新到旧、目录自动创建
- [x] `main.c`：CLI 五个子命令 + 28 项断言自测套件
- [x] Makefile：`make`（构建）/ `make test`（自测）/ `make demo`（命令行演示链）/ `make clean`

## 验收标准

- [x] `make` 零警告（`-Wall -Wextra -std=c11`，Apple clang 21.0.0 实测）
- [x] `make test` 全部断言通过、退出码 0（实测 28 项 PASS）：往返/覆盖/删除、WAL replay 恢复（含 tombstone 重放）、写满 4 KiB 自动 flush、SSTable 路径读、新层赢旧层（MemTable 赢 SSTable、新 SSTable 赢旧 SSTable）、tombstone 跨层遮挡、Bloom 拦截计数增长、flush 后纯 SSTable 恢复
- [x] ASan/UBSan 复跑 `test` 零报告（`-fsanitize=address,undefined`，衔接 ph11 工具链）
- [x] `make demo` 演示链符合预期：put → get 命中 → del → get 报 `(not found)` → flush → stats 显示 1 个 SSTable（`-` 前缀忽略 not found 的非零退出码）
- [x] `make clean` 零残留（产物全部在 /tmp/ph16c-proj，数据在 /tmp/ph16c-proj-data，仓库内无 .o / 可执行文件 / .dSYM / 数据文件）

## 验证

```bash
make            # 1. 构建（-Wall -Wextra -std=c11, 零警告）
make test       # 2. 自测（28 项断言全过退出码 0）
make demo       # 3. 命令行演示链（put/get/del/flush/stats）
make clean      # 4. 清理 /tmp/ph16c-proj 与 /tmp/ph16c-proj-data
```

Sanitizer 复跑（衔接 ph11；CFLAGS 覆盖后必须先 make clean 再重编，且用完后同样先 clean 再恢复常规构建）：

```bash
# 5. ASan/UBSan 版重编（-fsanitize=address,undefined; CFLAGS 需带全量参数）
make clean && make CFLAGS='-Wall -Wextra -std=c11 -O1 -g -fsanitize=address,undefined'
# 6. 复跑自测（detect_leaks=0: Linux 上跳过 LeakSanitizer, macOS 上为无害空操作）
ASAN_OPTIONS=detect_leaks=0 make test
# 7. 清理并恢复常规构建
make clean && make
```

验证环境：Apple clang 21.0.0（`cc`，macOS Darwin arm64，ProductVersion 26.6.2），C11。`make test` 实测输出摘要：

```text
=== ph16 project: lsmkv 自测套件 ===
PASS: open 成功 … PASS: 重开后 bulk01 仍不存在
lsmkv: 28 PASS, 0 FAIL, 退出码 0
```

Sanitizer 复跑同上第 5~7 步，实测同样 28 PASS、零报告。注意 `stats` 的 `flush N 次` 只统计当前进程生命周期内的 flush（计数器在内存），`sstable N 个` 才是磁盘真实状态。

## 扩展方向

- **compaction**：把多个 SSTable 归并成一个（顺带真正清掉 tombstone 与被覆盖的旧值）——读放大/空间放大的对症手段，主文档第 4 章有分析
- **range scan**：给引擎加迭代器——MemTable 与多个 SSTable 的 k-way 归并（主文档 3.9 讲了单表迭代器，多路归并是下一步）
- **group commit**：多条 WAL 记录攒批一次 fsync（examples/ex02 实测每条 fsync 慢约 11~18 倍；macOS 真落盘的 `F_FULLFSYNC` 见 ph13）
- **MemTable 换跳表**：插入从 O(n) 搬移降到 O(log n)（ph05 数据结构方向）
- **SSTable 块压缩与 Buffer Pool**：数据区分块 + LRU 缓存块（ex06 的 Buffer Pool 即雏形，snappy/lz4 压缩算法本身超出本阶段）
