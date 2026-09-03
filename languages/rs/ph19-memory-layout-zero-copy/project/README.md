# ph19 阶段项目：WAL record 解析器（wal-record-parser）

对应 roadmap 第 19 节推荐项目「WAL record 解析器：解析 record header、sequence、key、value 和 checksum 字段」。落地为一个**纯 std、零第三方依赖**的 Cargo 工程（库 + CLI），把主文档 3.7/3.8 的安全纪律（魔数定位 → CRC 校验 → 长度闸门 → 借用切片）与零拷贝解析做成可测试的成品。

## 需求

解析 WAL（Write-Ahead Log）的 record 字节格式，提供安全的逐条读取 API 与一个可直接解析文件的 CLI。记录格式（与主文档 3.8 表格、`examples/ex05-wal-record-parse.rs` 完全一致，字段一律小端）：

```text
[magic: u32] = b"WAL1"  防错位/异格式
[crc: u32]            对 key||value 求 CRC32（IEEE，查表实现，含标准向量自检）
[seq: u64]            单调序列号
[op: u8]              1=Put 2=Delete
[klen: u32][key]      长度前缀 + 变长 key
[vlen: u32][value]    长度前缀 + 变长 value（Delete 记录 vlen==0）
```

## 功能清单

- [x] 库 API：`parse_record(buf) -> Result<(Record, usize), WalError>` 解析单条，`Record.key/value` 是**借用输入**的切片（零拷贝，测试断言了指针偏移）
- [x] 库 API：`records(buf)` 惰性迭代整段日志，逐条返回；损坏处**显式报错并终止**（对应 WAL 重放语义，为 ph25 的崩溃恢复打底）
- [x] 库 API：`WalWriter` 追加式编码器（与解析器字段镜像，供测试与演示组包）
- [x] 完整错误模型：BadMagic / Truncated / ChecksumMismatch / UnknownOp / TooLarge（长度上限 DoS 闸门），`Display` + `std::error::Error`
- [x] CLI：无参数跑内存演示日志；传文件路径则整读文件后逐条打印，损坏时报错并以非 0 退出
- [x] 测试：8 条单元测试（CRC 标准向量、roundtrip、零拷贝断言、篡改拦截、坏魔数、未知 op、逐字节截断、损坏处终止）+ 2 条集成测试（真实文件写读全链路、损坏文件报错不 panic）
- [x] 质量闸门：`cargo fmt --check` 干净、`cargo clippy --all-targets -- -D warnings` 零告警

## 验收标准

- `cargo test` 全部通过（8 单元 + 2 集成，已验证：cargo 1.92.0 / aarch64-apple-darwin 本机实测）
- 演示 CLI 输出可复现：无参数运行打印 3 条 record（Put/Put/Delete）；对一个非 WAL 文件运行打印明确错误并以退出码 1 结束（均已实测）
- 篡改任意 key/value 字节后解析必报 `ChecksumMismatch`；把文件逐字节截短解析必报 `Truncated`，全程无 panic
- 解析不 panic、生产路径无裸 `unwrap`（仅演示 `main` 与测试使用 expect 断言）；错误一律走 `Result`/`WalError`
- 零拷贝有测试背书：`Record.key/value` 的指针偏移指向输入缓冲内部（借用的切片，不是副本）
- 仓库零二进制残留：构建统一 `CARGO_TARGET_DIR=/tmp/ph19-target`

```bash
# 一键验收（项目目录内执行）
export PATH="$HOME/.cargo/bin:$PATH"
cd project/wal-record-parser
CARGO_TARGET_DIR=/tmp/ph19-target cargo test
CARGO_TARGET_DIR=/tmp/ph19-target cargo run            # 内存演示日志
CARGO_TARGET_DIR=/tmp/ph19-target cargo run -- /path/to/xxx.wal   # 解析真实文件
CARGO_TARGET_DIR=/tmp/ph19-target cargo fmt --check
CARGO_TARGET_DIR=/tmp/ph19-target cargo clippy --all-targets -- -D warnings
```

## 扩展方向（可选）

- **重放状态机**：把 `records` 迭代出的 Put/Delete 应用到内存表，做成 Mini MemTable —— 完整 WAL append/replay、crash recovery 语义属 ph25 Rust 数据基础设施专项阶段（roadmap 第 25 节，目录待建），本库的「损坏即终止」语义正是为它准备的
- **流式解码**：改为边读文件边喂缓冲（替代整读），用 3.7 的「半帧等待」处理尾部残缺——那是崩溃断电在文件尾留下的常态，属工程解析而非错误
- **换成 bytes crate**：把 CLI 的整读改为 `Bytes` 持有，`split_to` 剥头不 memmove（3.5），观察大量 record 时分配次数下降——对比测量属 ph22 性能优化与 Profiling 阶段（roadmap 第 22 节，目录待建）
- **属性测试**：用 proptest 随机生成 Put/Delete 序列做 roundtrip —— 那是 ph20 测试体系进阶阶段（roadmap 第 20 节，目录待建）的推荐练习
- **工程化**：接入 rustfmt/clippy/CI 门禁 —— 属 ph21 Clippy、rustfmt、CI 与代码质量阶段（roadmap 第 21 节，目录待建）；`cargo audit` 依赖审计属 ph24（本工程零依赖，天然轻）
