# examples —— 内存布局、零拷贝与协议解析阶段完整示例

对应主文档 `19-memory-layout-zero-copy.md` 第 6 章示例 1~7。分成两组：

- **ex01~ex05（纯 std）**：零第三方依赖，`rustc --edition 2021 -D warnings` 单文件编译，产物输出 `/tmp/`。
- **ex06~ex07（bytes / nom）**：第三方 crate，独立 cargo 工程 `crates/`（Cargo.lock 已提交锁定版本）。bytes 1.12.1、nom 8.0.0。若网络不可用需先配置 crates.io 镜像或预热缓存（见 ph13 的 rsproxy 说明）。

验证环境：rustc/cargo **1.92.0**（macOS arm64，rustup 管理）；bytes **1.12.1** / nom **8.0.0**。**验证说明**：ex01~ex05 已在 rustc 1.92.0 本机实测编译运行通过；ex06/ex07 已在 cargo 1.92.0 本机实测（含 ex07 的 4 条测试与 clippy -D warnings 零告警、cargo fmt 干净），全部标注「已验证」。

## 第一组：纯 std（rustc 单文件，零依赖）

| 文件 | 对应主文档 | 说明 | 编译 | 运行 |
|------|-----------|------|------|------|
| `ex01-repr-layout.rs` | 3.1/4.1 | repr(Rust)/repr(C)/repr(packed)/repr(transparent)/ZST 的 size/align/offset 实测；packed 字段取引用报 E0793 的纪律 | `rustc --edition 2021 -D warnings ex01-repr-layout.rs -o /tmp/ph19-ex01` | `/tmp/ph19-ex01` |
| `ex02-byteorder.rs` | 3.3 | 大小端换算、`to_be_bytes`/`from_be_bytes`、纯 std `BeReader`（长度检查 + try_into），截断返回 None/Result 不 panic | `rustc --edition 2021 -D warnings ex02-byteorder.rs -o /tmp/ph19-ex02` | `/tmp/ph19-ex02` |
| `ex03-slice-zero-copy.rs` | 3.4/4.2 | `&[u8]` 借用、函数返回借用子切片、指针算术证明零拷贝、`chunks`/`chunks_exact` 差异 | `rustc --edition 2021 -D warnings ex03-slice-zero-copy.rs -o /tmp/ph19-ex03` | `/tmp/ph19-ex03` |
| `ex04-length-prefix-frame.rs` | 3.7 | length-prefix framing：长度上限闸门、单帧解析、流式增量（半帧等待）、粘连多帧 | `rustc --edition 2021 -D warnings ex04-length-prefix-frame.rs -o /tmp/ph19-ex04` | `/tmp/ph19-ex04` |
| `ex05-wal-record-parse.rs` | 3.8 | WAL record：魔数 + CRC32（零依赖手写，含 IEEE 测试向量自检）+ 零拷贝 key/value 回放 + 篡改拦截 | `rustc --edition 2021 -D warnings ex05-wal-record-parse.rs -o /tmp/ph19-ex05` | `/tmp/ph19-ex05` |

## 第二组：bytes / nom（cargo 工程 `crates/`，已验证）

```bash
# 构建与运行 / 测试（CARGO_TARGET_DIR 指向 /tmp，仓库零二进制残留）
cd examples/crates
CARGO_TARGET_DIR=/tmp/ph19-target cargo run --bin ex06-bytes-crate
CARGO_TARGET_DIR=/tmp/ph19-target cargo run --bin ex07-nom-parser
CARGO_TARGET_DIR=/tmp/ph19-target cargo test --bin ex07-nom-parser
# 质量闸门（本阶段交付时已全绿）
CARGO_TARGET_DIR=/tmp/ph19-target cargo fmt --check
CARGO_TARGET_DIR=/tmp/ph19-target cargo clippy --all-targets -- -D warnings
```

| 文件 | 对应主文档 | 说明 | 实测输出要点 |
|------|-----------|------|-------------|
| `src/bin/ex06-bytes-crate.rs` | 3.5 | `Bytes` 引用计数廉价 clone、`slice`/`copy_to_bytes` 共享缓冲零拷贝、`BytesMut` grow + `freeze`；对照 ex04 的 `drain` compact 谈「头指针移动 vs memmove」 | `a.as_ptr() == b.as_ptr()`；length-prefix 双帧零搬运切出 |
| `src/bin/ex07-nom-parser.rs` | 3.6/4.4 | nom 8 组合子：tag/take/手写 be_u16/be_u32 逐层串出 KV record 解析器、外层长度信封、截断/坏魔数错误路径、连排 record 循环消费；4 条单元测试 | `Msg{ ty:1, seq:100001, key:b"temperature", …}`；test result: ok. 4 passed |

> ⚠️ nom 8.0 是破坏性大版本：`tag` 参数需传切片 `tag(&b".."[..])`，`tag(b"..")`（数组引用）会编译失败——示例已按 8.x API 编写并在本机实测通过。若锁旧版本 nom 7，示例 API 需小幅适配。

## 阅读顺序建议

按主文档教学增量推进：ex01（布局心智，先知道「字节 = 布局 + 填充」）→ ex02（字节序，读数的第一课）→ ex03（切片借用，零拷贝的语法基础）→ ex04（length-prefix 与安全纪律，把「检查长度再信长度」内化）→ ex05（WAL record 实战，完整走一遍安全解析纪律）→ ex06（bytes 的共享缓冲，工程解法）→ ex07（组合子声明式解析，协议解析的另一种世界观）。

## 验证状态汇总

- ex01~ex05：已验证（rustc 1.92.0 本机实测编译运行通过）
- ex06/ex07：已验证（cargo 1.92.0 本机实测；ex07 4 条测试全过，crates 工程 clippy `-D warnings` 与 `cargo fmt --check` 干净）
- 依赖版本：bytes 1.12.1 / nom 8.0.0（Cargo.lock 锁定，仓库已提交）
