# ph13 阶段项目：kvlog —— 可靠 append-only log

> 对应 roadmap ph13「推荐项目」第一个「append-only log」（第二个「mmap 只读索引文件」由 examples/ex05 与练习 3 覆盖）。一个带 magic + 长度 + CRC32 的 append-only 日志库与命令行工具，把本阶段「write 成功 ≠ 持久化（fsync 才是刷盘边界）、崩溃最多留下最后一条残记录、残记录被长度/CRC 识别后截掉即恢复」三条核心纪律落地成可运行代码——即 WAL（Write-Ahead Log）的原型，ph16 数据库存储引擎基础阶段的 WAL replay 直接复用它。

## 需求

实现一个可靠的 append-only 日志（kvl = KV Log），供 KV 存储当写入日志用：

- **记录格式（12 + len 字节，大端）**：`magic`（u32 = "KVL1"，识别"这是不是我们的文件"）+ `len`（u32，payload 长度，上限 1 MiB）+ `crc32`（u32，覆盖 payload）
- **追加**：fd 以 `O_APPEND` 打开，每次 write 原子落到文件末尾（多进程追加互不覆盖）；`kvl_append` 返回只代表数据进了内核 Page Cache
- **刷盘**：`kvl_sync`（fsync）返回后才算到达存储设备（macOS 真落盘见下方「验证」的 F_FULLFSYNC 说明）
- **回放**：`kvl_replay` 顺序解析，干净 EOF / 残尾（截断、损坏、magic 不符）/ 系统错误给出可区分的返回码（`KVL_END_CLEAN` / `KVL_END_TORN` / `KVL_END_IOERR`），并输出完整记录数与残尾偏移
- **修复**：`kvl_repair`（ftruncate）砍掉残尾后，文件恢复可继续安全追加
- **命令行**：`write`（写 n 条 + fsync）/ `read`（回放）/ `bench`（三种刷盘策略压测）/ `crash`（fork 子进程真实 SIGKILL 后回放）/ `torn`（半写入演示）/ `corrupt`（翻转 1 字节验证 CRC 拦截）/ `test`（自测套件，退出码即结果）

解析路径的顺序即 roadmap 必会概念：**先校验长度 → magic → 长度上限 → CRC → 才计入一条完整记录**；任何一步失败都停在残尾处，绝不越界访问。

## 功能清单

- [x] `kvl_append`：按显式大端字节序组装 `magic + len + crc32 + payload`，O_APPEND 原子追加
- [x] `kvl_sync`：fsync 刷盘边界（write 成功 ≠ 持久化）
- [x] `kvl_replay`：顺序回放，干净/残尾/IO 错误三态区分，输出 count 与 torn_at 偏移
- [x] `kvl_repair`：ftruncate 砍掉残尾，恢复可追加状态
- [x] `kvlog crash`：fork + 真实 SIGKILL 模拟"写日志写到一半崩溃"，验证进程崩溃不丢 Page Cache 数据
- [x] `kvlog torn` / `kvlog corrupt`：半写入与位翻转演示（长度/CRC 拦截）
- [x] `kvlog bench`：只结尾 / 每 200 条 / 每条 fsync 三种策略吞吐对比（复现 examples/ex03 的结论）
- [x] `kvlog test`：自测套件（往返 / 残尾 / 损坏 / magic，退出码即结果，可进 CI）
- [x] Makefile：`make`（构建）/ `make test`（一键自测）/ `make demo`（演示链）/ `make san`（Sanitizer 复跑）/ `make clean`

## 验收标准

- [x] `make` 零警告（`-Wall -Wextra -std=c11`，Apple clang 21.0.0 实测）
- [x] `make test` 全部断言通过、退出码 0（实测 16 个 [PASS]，含往返 100 条、残尾停在准确偏移、损坏→CRC 拦截在第 50 条、全零垃圾→magic 拦截在偏移 0）
- [x] `make demo` 演示链全部退出码 0：写 8 条 → 回放 8 条；crash 恢复 2000/2000 条、残尾停在准确偏移、ftruncate 修复后回放干净；corrupt 翻转 1 字节被 CRC 拦截（`kvlog read` 对残尾返回退出码 2，`corrupt` 自身返回 0 表示拦截成功；Makefile 中 `-` 前缀为历史兼容保留）
- [x] `make san`：ASan/UBSan 复跑 `test` 与 `crash` 零报告（衔接 ph11 工具链）
- [x] `make clean` 零残留（仓库内无 .o / 可执行文件 / .dSYM；演示文件写 /tmp）

## 验证

```bash
make            # 1. 构建（-Wall -Wextra -std=c11, 零警告）
make test       # 2. 自测（16 个断言全过退出码 0）
make demo       # 3. 演示链（写/读/crash/torn/corrupt）
make san        # 4. Sanitizer 复跑（行为正确 + 内存无错, 衔接 ph11 工具链）
make clean      # 5. 清理
```

验证环境：Apple clang 21.0.0（`cc`，macOS Darwin arm64），C11。实测：写 2000 条（每 200 条 fsync）总约 15 ms；崩溃演示恢复 2000/2000 条、残尾停在偏移 86693；macOS 上 fsync 只到设备缓存，`fcntl(F_FULLFSYNC)` 才到介质（Linux 的 fsync 即真落盘语义，见 examples/ex03）。

## 扩展方向

- 加 `msync`/mmap 只读索引（把 key → 文件内 offset 的索引 mmap 进来随机读）——衔接练习 3 与 examples/ex05；mmap 只读索引是 roadmap 推荐的第二个项目
- 加 record 序号（seqno）支持回放去重与"读到损坏记录后按最新完好状态恢复"的完整 WAL 恢复流程——ph16 数据库存储引擎基础阶段的 WAL replay 预演（见 [ph16-storage-engine/16-storage-engine.md](../../ph16-storage-engine/16-storage-engine.md)）
- 把 payload 的"key=value"文本改成真正的 key/value 双字段 + varint 长度编码（varint 见 ph12 examples/ex06）
- 加 group commit：多条记录攒批后一次 fsync（examples/ex03 已展示"每条都 fsync"比"每 200 条"慢约 17 倍——量化收益后再决定批次大小）
