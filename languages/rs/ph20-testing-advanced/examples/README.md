# examples —— 测试体系进阶阶段完整示例

对应主文档 `20-testing-advanced.md` 第 6 章的示例 1~5。每个示例是一个独立 cargo crate，被测对象都是**同一个 ph19 迷你 WAL record 解析器**（结构复刻自 ph19 阶段项目 wal-record-parser）——测试体系的内容不换被测对象，换「测试怎么搭」。

验证环境：rustc/cargo **1.92.0**（macOS arm64，rustup 管理）；proptest **1.11.0**、criterion **0.8.2**（版本见各 crate Cargo.lock 锁定）。**验证说明**：五个示例均已在本机实测（`cargo test` / `cargo bench` 全绿，`cargo fmt --check` 干净、`cargo clippy --all-targets -- -D warnings` 零告警），全部标注「已验证」。构建产物统一落 `/tmp`（`CARGO_TARGET_DIR`），仓库零二进制残留。

## 示例清单与运行命令

| 示例 | 对应主文档 | 一句话说明 | 验证状态 |
|------|-----------|-----------|---------|
| `ex01-unit-integration-tree` | 3.1/3.2 | 单元测试（`#[cfg(test)]` 模块 + 断言宏 + `#[should_panic]`）与集成测试（`tests/` 独立 crate + `tests/common/mod.rs` 共享辅助）的目录组织 | 已验证 |
| `ex02-test-fixtures` | 3.3 | test fixtures：数据夹具（`tests/fixtures/*.hex` 文本样例）、构造辅助、设备夹具（TempFile Drop 自清理）、异常样例矩阵 | 已验证 |
| `ex03-fake-mock` | 3.4/3.7 | 用 `Store` trait 立接口边界：fake（MemoryStore 真实现）测行为、手写 mock 测调用协议与失败注入；依赖注入演示 | 已验证 |
| `ex04-proptest-boundary` | 3.5/4.2 | proptest 属性测试：任意字节轰炸不 panic、构造日志 roundtrip、record 只消费自己的字段；自定义策略 | 已验证 |
| `ex05-criterion-bench` | 3.6/4.3 | criterion 基准：零拷贝 vs 逐条复制的解析路径对比、参数扫描、噪声控制、`--save-baseline`/`--baseline` 回归演练 | 已验证 |

```bash
# 通用运行方式（在任一示例 crate 目录内执行；以 ex04 为例）
export PATH="$HOME/.cargo/bin:$PATH"
cd examples/ex04-proptest-boundary
CARGO_TARGET_DIR=/tmp/ph20-target cargo test
# 加大 proptest 轰炸量（可选）
PROPTEST_CASES=4096 CARGO_TARGET_DIR=/tmp/ph20-target cargo test
# 跑被 #[ignore] 的慢用例（ex01 演示了 ignore 用法）
cd ../ex01-unit-integration-tree
CARGO_TARGET_DIR=/tmp/ph20-target cargo test ignored_long_running_case -- --ignored
# 基准（ex05）
cd ../ex05-criterion-bench
CARGO_TARGET_DIR=/tmp/ph20-target cargo bench
# 回归基线演练（ex05；看 change 行的区间与 p 值）
CARGO_TARGET_DIR=/tmp/ph20-target cargo bench --bench parse_compare -- --save-baseline v1
CARGO_TARGET_DIR=/tmp/ph20-target cargo bench --bench parse_compare -- --baseline v1
```

## 每个示例的看点

- **ex01**：单元测试与集成测试各自该放什么。`src/lib.rs` 里两类 `#[cfg(test)]` 模块（同模块 + 兄弟模块 `crate::` 路径访问）；断言宏（`assert_eq!`/`assert_ne!`/`matches!`/Result 返回测试/`#[should_panic]` 验证裸下标 panic 契约/`#[ignore]`）；`tests/` 两个独立集成 crate + `tests/common/mod.rs`（为什么辅助模块不能叫 `tests/common.rs`）。
- **ex02**：测试数据从哪来。`tests/fixtures/*.hex`（`#` 注释 + hex 字节的文本数据夹具，可 diff 可回归）由同目录生成逻辑产出并提交；`decode_hex_fixture` 加载；`TempFile` 设备夹具用 Drop 保证清理；异常样例矩阵用「case 表 + 一个驱动函数」实现参数化。
- **ex03**：trait 边界让测试替身可插拔。`replay_to(store: &mut impl Store, log)` 只依赖接口；`MemoryStore` 是 fake（真实现），`tests/interactions.rs` 的手写 `MockStore` 是 mock（记录调用 + 注入「磁盘满」）；对照测试证明 fake 与 mock 对同一日志给出的观测一致，并验证失败注入后重放停止。
- **ex04**：属性测试。`tests/common/mod.rs` 定义任意字节 / 合法 record / 带后缀 record 三类策略；性质 = 永不 panic、错误类别封闭、roundtrip、字段边界不读穿。proptest 失败时会**收缩到最小反例**（主文档 4.2 有实测输出）。
- **ex05**：criterion。`benchmark_group` + `BenchmarkId` 参数扫描 + `Throughput`；两路径（借用 vs 复制）实测量级差（小 value 场景约 3×）；噪声控制（warm-up/measurement/sample_size）在 `config()` 里显式给出并说明正式验收建议放宽。

> ⚠️ criterion 0.8 起 `criterion::black_box` 已弃用，请用 `std::hint::black_box`（本仓库示例按此编写并在本机实测零警告）。基准结论依赖机器与系统负载，请以本机跑出的相对差为准。

## 阅读顺序建议

按主文档教学增量推进：ex01（测试放哪、断言怎么写）→ ex02（样例数据怎么管）→ ex03（接口边界与测试替身）→ ex04（属性轰炸补盲区）→ ex05（基准量化收尾）。每看完一个示例就去 `exercises/` 做对应一题。

## 验证状态汇总

- ex01~ex05：已验证（cargo 1.92.0 本机实测；fmt/clippy `-D warnings` 全绿）
- 依赖版本：proptest 1.11.0 / criterion 0.8.2（Cargo.lock 各自锁定并提交）
- 本机无网络时：ex01~ex03 纯 std 可直接跑；ex04/ex05 需先拉取 proptest/criterion（首次 `cargo test`/`cargo bench` 会自动下载，或配置 crates.io 镜像预热缓存）
