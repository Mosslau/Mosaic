# ph14 阶段项目：kvdb —— C ABI KV 库（WAL 持久化）

> 对应 roadmap ph14「推荐项目」三个之一体：**「C ABI KV 插件接口」**（库本身）+ **「Python 调用 C buffer 解析库」**（py_kvdb.py 用 ctypes 读写值缓冲区）+ **「Rust 调用 C WAL 库」**（rs_kvdb.rs 用 extern "C" 调持久化 KV）。一个 C ABI 库同时被 C CLI、Python、Rust 三方真实调用——把本阶段"简单稳定类型、opaque pointer、create/destroy、错误码与错误消息、所有权规则、ABI 稳定优先"全部落地成可运行代码，并把 ph13 的 append-only log 升级为带回放的 WAL 底座。

## 需求

实现一个带 WAL 持久化的 C ABI KV 库，供其他语言（C / C++ / Python / Rust）通过动态库调用：

- **跨语言契约（kvdb.h 即契约）**：`kvdb_t` 是 opaque 句柄；`kvdb_create(path, err_out)` 打开/创建 WAL 并**回放重建内存态**；`kvdb_put` 追加 WAL 记录（拷贝语义）；`kvdb_get` 写入调用方缓冲区（调用方分配）；`kvdb_sync` 显式 fsync；`kvdb_destroy` 释放全部资源
- **WAL 记录格式（大端, 衔接 ph12/ph13）**：`[magic "KVDB" u32][plen u32][crc32 u32][klen u32][key][vlen u32][val]`；crc 覆盖 payload；崩溃最多留下最后一条残记录（半写/损坏被回放安全跳过）
- **错误码**：0 成功、负数错误（BADARG=-1 / NOMEM=-2 / IO=-3 / FULL=-4 / NOTFOUND=-5），消息经 `kvdb_strerror` 读取，不使用 errno
- **命令行**：`kvdb-cli` 自测套件（22 项断言，退出码即结果）
- **跨语言调用方**：`py_kvdb.py`（ctypes：文本/二进制值往返、NOTFOUND/BADARG 错误路径、重开后 WAL 回放验证）+ `rs_kvdb.rs`（extern "C"：同一套往返与错误路径）

## 功能清单

- [x] `kvdb_create`：新建/打开 WAL + 回放恢复（ph13 的"崩溃最多丢最后一条残记录"语义）
- [x] `kvdb_put` / `kvdb_get`：文本与二进制值（含 `\0`）往返、覆盖、容量上限 FULL
- [x] `kvdb_sync`：fsync 刷盘边界（write 成功 ≠ 持久化）
- [x] `kvdb_destroy`：释放全部资源（谁 create 谁 destroy）
- [x] `kvdb_strerror`：错误消息（静态字符串借用）
- [x] `kvdb-cli`：22 项断言自测（含 NOTFOUND/BADARG 错误路径与重开持久化验证）
- [x] `py_kvdb.py`：Python ctypes 调用方（C buffer 解析 + 错误码/消息 + WAL 回放）
- [x] `rs_kvdb.rs`：Rust extern "C" 调用方（同样验证 WAL 回放持久化）
- [x] Makefile：`make`（构建 dylib + cli）/ `make test`（三方一键验证）/ `make clean`

## 验收标准

- [x] `make` 零警告（`-Wall -Wextra -std=c11`，Apple clang 21.0.0 实测）
- [x] `make test` 全部通过、退出码 0：`kvdb-cli` 22 项断言全 PASS（含覆盖、二进制往返、NOTFOUND=-5、BADARG=-1、重开后 WAL 回放恢复）；`py_kvdb.py` 与 `rs_kvdb.rs` 各自的往返/错误路径/重开持久化断言全过
- [x] `make clean` 零残留（产物全部在 `/tmp/ph14-proj`，仓库内无 .o / .dylib / 可执行文件）
- [x] 三种语言读到的错误消息一致：`key not found` / `invalid argument`（同一份 C 字符串）

## 验证

```bash
make            # 1. 构建 libkvdb.dylib + kvdb-cli（-Wall -Wextra -std=c11 零警告）
make test       # 2. 一键验证: C CLI(22 项) → Python ctypes → Rust FFI, 全过退出码 0
make clean      # 3. 清理 /tmp/ph14-proj
```

验证环境：Apple clang 21.0.0（`cc`，macOS arm64，ProductVersion 26.6.2）+ Python 3.13.9 + rustc 1.92.0（edition 2021）。`make test` 实测输出：CLI 22 项 PASS；`py-kvdb: 全部断言通过`；`rs-kvdb: 全部断言通过`。Linux 差异：动态库编译用 `-shared -fPIC` 生成 `libkvdb.so`，其余代码与契约不变。

## 扩展方向

- 把固定容量线性表换成哈希表 / 红黑树索引（ph05 结构体与数据结构阶段），key 查找从 O(n) 到 O(1)
- 加 `kvdb_replay` 残尾修复（ftruncate）与 `kvdb_crash` 演示（fork + SIGKILL）——ph13 project/ kvlog 已有完整实现，可直接移植
- 支持迭代器（range scan）与多值类型——ph16 数据库存储引擎基础阶段的 MemTable/SSTable 方向（见 [ph16-storage-engine/16-storage-engine.md](../../ph16-storage-engine/16-storage-engine.md)）
- 把错误码扩展为"模块号 + 错误号"组合（如 `-0x0101`），并加版本化 ABI 检查（`kvdb_abi_version()`）——ph15 高级 C 与代码质量阶段（[15-code-quality.md](../../ph15-code-quality/15-code-quality.md)）的 API 设计方向
