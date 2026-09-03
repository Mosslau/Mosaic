# ph20 阶段项目：record 解析测试套件（record-test-suite）

对应 roadmap 第 20 节推荐项目「record 解析测试套件：包含真实样例、错误样例、基准测试」。被测对象是 ph19 的迷你 WAL record 解析器（本仓库 `record-test-suite/src/record.rs`，与 ph19 阶段项目 wal-record-parser 同构），本阶段不新增解析逻辑，而是把 ph20 学到的**整套测试体系**压在它身上：真实样例 + 错误样例矩阵 + proptest 属性轰炸 + criterion 基准对比，一次 `cargo test` + 一次 `cargo bench` 让「能跑」变成「可证明能跑」。

## 需求

把 roadmap 第 20 节的三种练习（异常样例测试、proptest 边界、criterion 前后对比）与「单元/集成测试目录、test fixtures」的工程组织合体成一个可复用的测试套件模板：换被测对象（例如将来 ph25 的 SSTable reader）时，只换 `src/record.rs` 与 fixtures，套件骨架原样复用。

## 功能清单

- [x] **被测对象**：`src/record.rs`——WAL record 解析器（魔数/CRC/长度闸门/零拷贝），自带 8 条单元测试（CRC 标准向量、roundtrip、零拷贝指针断言、篡改拦截、坏魔数/未知 op、逐字节截断、损坏处终止）+ lib.rs 顶部 doctest
- [x] **真实样例**：`tests/fixtures/sample_put_delete_put.hex` 等固定输入，`tests/real_samples.rs` 做字段级与「应用进假引擎」的链路断言，并验证零拷贝指针指向夹具缓冲内部
- [x] **错误样例矩阵**：`tests/fixtures/err_*.hex`（坏魔数/未知 op/CRC 翻转/klen 越限/尾部截断/空文件），`tests/anomaly_matrix.rs` 用 case 表逐类断言 + **逐截断点全扫** + **逐字节翻转不 panic**
- [x] **属性测试**：`tests/property.rs`（proptest 1.11.0）——任意字节不 panic、roundtrip、Delete 空 value、两段日志拼接 = 并集
- [x] **基准测试**：`benches/parse_bench.rs`（criterion 0.8.2）——零拷贝 vs 快照复制 × 3 组尺寸扫描，`Throughput` 吞吐，噪声控制配置与基线对比命令齐备
- [x] **演示 CLI**：`src/main.rs`——`cargo run` 跑内存演示日志并抽查错误样例矩阵（真正的断言在测试侧），支持解析任意 `.wal` 文件
- [x] **质量闸门**：`cargo fmt --check` 干净、`cargo clippy --all-targets -- -D warnings` 零告警

## 目录布局

```text
record-test-suite/
├── Cargo.toml / Cargo.lock
├── src/
│   ├── lib.rs          # crate 文档 + record 模块再导出 + doctest
│   ├── record.rs       # 被测对象：WAL record 解析器（含单元测试）
│   └── main.rs         # 演示 CLI（cargo run [<file.wal> | --matrix]）
├── tests/
│   ├── common/mod.rs   # fixtures 解码、日志构造、TempFile 设备夹具、假引擎
│   ├── fixtures/       # *.hex 数据夹具（真实/错误/边界样例，文本可 diff）
│   ├── real_samples.rs
│   ├── anomaly_matrix.rs
│   └── property.rs
└── benches/
    └── parse_bench.rs
```

## 验收标准

- `cargo test` 全部通过：单元 8 + doctest 1 + 集成 real_samples 5 + anomaly_matrix 3 + property 5（已验证：cargo 1.92.0 / aarch64-apple-darwin 本机实测）
- 五个错误类别（BadMagic/UnknownOp/ChecksumMismatch/Truncated/TooLarge）各有固定夹具与断言；真实样例字段级断言逐项对齐
- 篡改（单字节翻转、逐截断点）下解析不 panic，错误类别不越出 `WalError`
- `cargo bench` 可跑通并给出 3 组尺寸 × 2 路径的 `time`/`thrpt`（本机实测零拷贝路径显著快于快照复制，例如 1000 条 ×16B 约 1.59 GiB/s vs 0.58 GiB/s）
- 生产路径（`src/`）无裸 `unwrap`（测试与 `tests/` 内的断言性 expect 除外，均已注明）；仓库零二进制残留（构建统一 `CARGO_TARGET_DIR=/tmp/ph20-target`）

```bash
# 一键验收（项目目录内执行）
export PATH="$HOME/.cargo/bin:$PATH"
cd project/record-test-suite
CARGO_TARGET_DIR=/tmp/ph20-target cargo test
CARGO_TARGET_DIR=/tmp/ph20-target cargo run                 # 内存演示日志 + 矩阵抽查
CARGO_TARGET_DIR=/tmp/ph20-target cargo run -- --matrix      # 只看错误样例矩阵
CARGO_TARGET_DIR=/tmp/ph20-target cargo bench --bench parse_bench
CARGO_TARGET_DIR=/tmp/ph20-target cargo fmt --check
CARGO_TARGET_DIR=/tmp/ph20-target cargo clippy --all-targets -- -D warnings
```

## 扩展方向（可选）

- **换被测对象**：把 `src/record.rs` 换成 ph25 的 SSTable block reader / length-prefix frame 解析器，fixtures 与矩阵骨架直接复用——本套件的价值正是「模板可移植」
- **CI 门禁化**：把质量闸门接进 GitHub Actions（fmt/clippy/test/bench 基线）——属 ph21 Clippy、rustfmt、CI 与代码质量阶段（roadmap 第 21 节，目录待建）
- **回归阈值自动化**：用 `--save-baseline` + 解析 `change` 输出做「性能回归 CI 判红」，criterion 深层统计与阈值配套属 ph22 性能优化与 Profiling 阶段（roadmap 第 22 节，目录待建）
- **真引擎对接**：把测试里的假引擎换成 ph25 的真实 MemTable/WAL replay，套件不变——那是 ph25 Rust 数据基础设施专项阶段（roadmap 第 25 节，目录待建）的落点
