# Rust 测试体系进阶阶段

> 面向「让代码可证明正确」的方向：本阶段把测试从「会写 #[test]」升级为「一套体系」——单元与集成测试的目录工程、固定样例与临时文件两类 fixtures、fake 与 mock 的测试替身、proptest 的属性轰炸、criterion 的基准量化，并用 ph19 写下的 WAL record 解析器当练兵场，回答 ph19 主文档末尾留给本阶段的预告。

## 1. 概述

本阶段对应 roadmap 第 20 节，目标是**建立覆盖单元、集成、属性和基准的测试体系**。它在学习路线里的位置很特别：ph11（错误处理与工程质量）已把 `#[cfg(test)]`、`#[should_panic]`、Result 返回测试、`rustc --test` 单文件测试讲过一遍；ph06 讲过 `cargo test`；ph19 的解析器带了一批样例测试。本阶段**不重复入门**，而是回答三个进阶问题：**测试放哪里**（目录工程与共享模块）、**测试数据从哪来**（fixtures 与构造辅助）、**除了手写用例还能怎么测**（属性测试补盲区、基准测试给结论）。被测对象全程固定为 ph19 的 **WAL record 解析器**——字节解析类代码的边界路径（长度不足、坏魔数、CRC 失败、长度越限、粘连/截断）是测试体系的天然练兵场，这与 ph19 主文档「### 下一阶段」段落对 ph20 的预告完全一致：**把 ex07/project 的样例测试升级成异常样例矩阵（test fixtures）、用 proptest 生成随机字节流找解析器崩溃点、用 criterion 基准验证「零拷贝真的比逐次复制快」**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 单元测试 | `#[cfg(test)]` 模块组织、断言宏家族、`#[should_panic]`、Result 返回测试、`#[ignore]`、doctest（3.1） |
| 集成测试目录 | `tests/` 每文件独立 crate、`tests/common/mod.rs` 共享模块、`cargo test` 目标过滤、pub API 面 = 可测面（3.2） |
| test fixtures | 数据夹具（固定样例文件，.hex 文本约定）与设备夹具（临时文件/目录，Drop 自清理）、构造辅助、异常样例矩阵（3.3） |
| mock 与 fake | 两者定义与选用判据、trait 假实现（fake）测行为、手写 mock 测调用协议与失败注入、mockall 概念（3.4） |
| proptest | QuickCheck 血脉、策略组合（any/vec/组合子/自定义）、`proptest!` 宏、收缩 shrinking 与最小反例、回归文件（3.5/4.2） |
| criterion | 内置 bench 与 criterion 的取舍、group/参数扫描/吞吐、噪声控制、`--save-baseline`/`--baseline` 回归对比与 p 值（3.6/4.3） |
| 可测试设计 | 测试金字塔在 Rust 的落地、依赖注入、接口边界、纯函数核心、确定性（3.7） |
| 底层原理 | test harness 如何收集 `#[test]`、proptest 收缩算法直觉、criterion 统计（重采样置信区间/显著性）、fixtures 与 CI 缓存（4） |
| 场景与练习 | 测试金字塔落地 + Go testing / Java JUnit / Python pytest 跨语言对比；examples/exercises/project 四层配套（5~7） |

这个阶段只涉及 **Rust 进程内测试体系的工程化组织与工具链使用**，**不涉及代码质量工具链的系统集成**（cargo fmt / cargo clippy / lint 等级管理 / GitHub Actions 的矩阵构建与缓存策略——本阶段只在 4.4 点到「fixtures 与 CI 缓存」的直觉，CI 编排本身属 [ph21 Clippy、rustfmt、CI 与代码质量阶段](../ph21-code-quality-ci/21-code-quality-ci.md)）、**系统化性能剖析方法论**（本阶段 criterion 只做「同一代码优化前后的相对对比」测量工具，讲清噪声控制与基线概念；perf/flamegraph、profile 配置调优、内存分配剖析、缓存局部性测量属 [ph22 性能优化与 Profiling 阶段](../ph22-perf-profiling/22-perf-profiling.md)）、**跨语言与安全边界的测试**（FFI 导出函数的 ABI/错误码测试、跨进程 mock，属 [ph23 Rust FFI 与跨语言接口设计阶段](../ph23-ffi-interop/23-ffi-interop.md)；依赖审计、供应链与发布质量的 CI 环节属 [ph24 安全、供应链与发布阶段](../ph24-supply-chain-release/24-supply-chain-release.md)）。同时与两条相邻知识点划清边界：**入门级测试语法**（`#[test]`/`#[should_panic]`/Result 测试/`rustc --test`）在 ph11 错误处理与工程质量阶段已讲，本阶段直接用不重复；**被测对象本身**（WAL record 的布局与解析安全纪律）属于 ph19 内存布局、零拷贝与协议解析阶段——本阶段只把它当「代码库」，不解释它的字节格式来历。

## 2. 来源与演变

Rust 的测试设施不是一次设计出来的，而是三条路线的汇合：**单元/集成测试**源自 xUnit 家族的「代码内测试」传统，Rust 把它做成「测试代码与被测代码同 crate、靠 `#[cfg(test)]` 裁剪」的形态；**属性测试**源自 Haskell QuickCheck 的「用随机生成 + 收缩替代手写用例」思想（2000 年 Claessen 与 Hughes 提出）；**基准**则从「nightly 内置 bench」长成了第三方 criterion 的「统计化测量」。**设计哲学一句话加粗：测试是代码库的一部分，不是附属品——所以它跟被测代码共享所有权规则、走同样的模块与 crate 边界，而不是靠魔法字符串或外部测试框架（如 JUnit 的注解 + 独立 runner）来连接。**

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| xUnit 测试传统（SUnit → JUnit） | 1994~1997 前后 | setUp/tearDown fixtures、断言、测试收集等概念定型；「测试是代码」的工程实践从 Smalltalk/Java 扩散 |
| QuickCheck | 2000 | Haskell 属性测试：随机生成输入 + 失败自动**收缩**到最小反例；Claessen 与 Hughes 论文《QuickCheck: A Lightweight Tool for Random Testing of Haskell Programs》 |
| Rust 1.0 | 2015 | `#[test]`、libtest、`cargo test` 稳定：同一 harness 跑单元/集成/文档测试，测试与 crate 边界对齐 |
| proptest 出现 | 2017 前后 | Jason Orendorff 发起；把 QuickCheck 思想带给 Rust，特色是可组合的 Strategy 与「值树」收缩 |
| cargo-nextest | 2021 前后 | nextest-rs 社区的快速测试 runner：按进程隔离、跳过 doc-tests 选项、更好的失败报告；仍基于 cargo 的测试目标模型，是 libtest 的**替代 runner** 而非新框架 |
| criterion 稳定路线 | 2016 起（0.5/0.8） | Jorge Aparicio 起步、bheisler 长期维护：稳定版可用的统计化基准，HTML/JSON 报告、基线对比；0.8 起弃用 `criterion::black_box`（改用 `std::hint::black_box`，本机实测） |
| 本环境工具链 | 2025-12 | rustc/cargo 1.92.0（macOS arm64，rustup 管理）；proptest 1.11.0、criterion 0.8.2（Cargo.lock 锁定） |

**属性测试思想在主流语言都开了花**：Rust 的 proptest、Python 的 Hypothesis（2013 起，David MacIver 发起，是 proptest 官方致谢的灵感来源）、Go 标准库 `testing/quick`、Java 的 jqwik——同一套「生成器 + 收缩」在不同语言里收敛出惊人一致的形态，本阶段 5 节会逐个对照。**Rust 在测试上最独特的一点**是：由于 `cfg(test)` 与模块/可见性系统，**测试能贴到任意一层实现上**——既能 `use super::*` 看私有函数（单元测试），又能只走 pub API 当黑盒（集成测试），还能两者并存于同一 crate 而无任何运行时框架。这解释了为什么 Rust 社区至今没有一个「官方测试框架」：内置 harness 已足够，第三方价值主要在 runner（nextest）与生成/统计工具（proptest/criterion）上。

历史教训值得一提：**「能跑」不等于「可证明能跑」**。早期 Rust 工程常见的「只有 happy-path 测试」在解析器这类代码上尤其危险——ph19 安全纪律里每一条红线（坏魔数、CRC 失败、长度越限、半截帧）都对应一类手写用例容易漏、proptest 随机字节却必然撞上的边界。Rust 测试设施给的是「你不写就没人写」的自由：没有参数化测试语法（用 case 表自己拼）、没有官方 fixtures（自己约定目录）、没有 mock 框架（trait 边界自己划）——本阶段教的正是这些「没有」之下的惯用法。

本文示例以 **rustc 1.92.0 / edition 2021** 为基线（edition 2021 与仓库全代码层一致），验证工具链 **rustc/cargo 1.92.0（macOS arm64，rustup 管理）**，第三方依赖 **proptest 1.11.0 / criterion 0.8.2**（版本已在各 crate Cargo.lock 锁定）。这个阶段的语法是 Rust 里最稳定的部分：`#[test]`/`assert_eq!` 自 1.0 起语义未变；会漂的是工具链周边（nextest 的 CLI、criterion 的弃用项、proptest 的配置项），一律以锁定版本与 docs.rs 为准。**代码验证状态**：examples 的 ex01~ex05、exercises 的 record-parser 与 sol-01~sol-04、project 的 record-test-suite 全部在 cargo 1.92.0 本机实测（`cargo test` / `cargo bench` 全绿，`cargo fmt --check` 干净，`cargo clippy --all-targets -- -D warnings` 零告警），标注「已验证」。

## 3. 语法与参数

本章按「测试放哪 → 数据从哪来 → 怎么替身 → 怎么补盲区 → 怎么给结论 → 怎么设计才好测」推进：3.1~3.2 解决目录与模块组织，3.3 解决 fixtures，3.4 解决测试替身，3.5 引入 proptest 属性轰炸，3.6 引入 criterion 基准，3.7 回看可测试设计。所有代码的被测对象都是 ph19 的 WAL record 解析器（本仓库各处复刻为 `record-parser` / `ex0X` 的 `record` 模块），完整可运行版见 [`examples/`](./examples/)，练习见 [`exercises/`](./exercises/)，综合套件见 [`project/`](./project/)。

### 3.1 单元测试：cfg(test) 模块、断言宏与 panic 契约

单元测试**贴着实现放**：与被测代码同文件、同模块（`use super::*`），或作为被测模块的兄弟子模块（用 `crate::` 路径访问 pub API）。`#[cfg(test)]` 保证这些代码只参与 `cargo test` 编译，release 构建零残留——这就是 Rust「测试是代码库一部分」的最小机制。roadmap 第 20 节示例代码就是最朴素的形态：

```rust
// examples/ex01-unit-integration-tree/src/lib.rs 的 assert_styles 模块 —— 断言宏全家（已验证：cargo 1.92.0）
#[cfg(test)]
mod assert_styles {
    use crate::{parse_record, Op, WalError, WalWriter};

    #[test]
    fn assert_eq_ne_sanity() {
        assert_eq!(1 + 1, 2);    // 相等断言：失败时打印左右表达式与值
        assert_ne!(2 + 2, 5);    // 不等断言
    }

    #[test]
    fn matches_macro_matches_err_variant() {
        let r = parse_record(&[0u8; 32]); // 长度足但魔数全 0 → BadMagic
        assert!(matches!(r, Err(WalError::BadMagic(_)))); // 只关心变体、不关心内部值
    }

    #[test]
    fn result_returning_test_propagates() -> Result<(), WalError> {
        // Result 返回测试：Err 经 `?` 传播 → 测试失败并打印 Display 错误（ph11 已讲）
        let mut w = WalWriter::new();
        w.append(5, Op::Put, b"k", b"v");
        let (rec, used) = parse_record(w.as_bytes())?;
        assert_eq!(rec.sequence, 5);
        assert_eq!(used, w.as_bytes().len());
        Ok(())
    }

    #[test]
    #[should_panic(expected = "range start index 99 out of range")]
    #[allow(clippy::out_of_bounds_indexing)] // 故意越界：演示裸下标的 panic 契约
    fn naked_index_panics_on_short_buf() {
        // 复习 ph19 3.7：裸下标越界直接 panic——这正是解析器一律用 get() 的原因；
        // #[should_panic] 把「这个失败模式确实存在」固化成可回归的契约测试
        let buf = b"short";
        let _ = &buf[99..];
    }
}
```

| 设施 | 作用 | 本阶段要点 |
|------|------|-----------|
| `#[cfg(test)] mod` | 只在测试构建编译 | 可放同模块（看私有项）也可放兄弟模块（走 pub API）；release 无残留 |
| `#[test]` | 标记测试函数 | 一个函数一个用例；失败 = panic 或返回 `Err` |
| `assert_eq!`/`assert_ne!` | 值相等/不等断言 | 类型需实现 `PartialEq` + `Debug`；失败打印两侧值——**错误枚举实现 `PartialEq` 让断言能对比「是哪类错」**（ph11 已强调） |
| `assert!`/`matches!` | 布尔/模式断言 | `matches!` 只断言变体形状，读起来像意图声明 |
| `#[should_panic(expected=...)]` | 断言函数按契约 panic | 只用于「调用方违约」的契约（如越界切片）；**正常业务失败应返回 `Result` 而非 panic**（rust-patterns） |
| 返回 `Result<(), E>` 的测试 | 让 `?` 传播错误 | 错误信息比 panic 更可读；断言与 `?` 混用 |
| `#[ignore]` | 默认跳过、显式跑 | 慢用例/需外部资源用例：`cargo test -- --ignored` 或过滤名跑（ex01 演示） |
| doctest | `///`/`//!` 里 ```rust 块 | `cargo test` 默认编译执行文档示例——**文档不撒谎**的机制；lib.rs 顶部示例即 doctest |

单元测试放哪里，一个判断就够：**要看私有实现细节（内部函数、不变量）就放同模块；只断言 pub API 行为，放哪都行**。ph19 解析器的单元测试（`record` 模块内 `mod tests`）两类都有：CRC 标准向量、roundtrip、零拷贝指针偏移断言、篡改拦截、坏魔数/未知 op、逐字节截断、损坏处终止（见 [`exercises/record-parser/src/lib.rs`](./exercises/record-parser/src/lib.rs) 等处的同款用例，已验证）。

> 本阶段继续沿用 ph11 的约定：**生产代码（`src/`）无裸 `unwrap`**——错误走 `Result`/`?`；测试与 `tests/` 内的断言性 `expect` 属测试断言语境，可接受（代码里均已注明）。两条线分开看，混在一起会让「生产 panic」藏进测试风格里。

### 3.2 集成测试目录：tests/、共享辅助模块与可见性边界

集成测试放 `tests/` 目录：**每个 `.rs` 文件是一个独立 crate**，只通过被测 crate 的 **pub API** 工作（看不到私有项）。`cargo test` 会为 lib 单元测试、每个 `tests/*.rs`、doctest 分别编译运行，输出里能看到各自独立的 `running N tests`。配套约定：**共享辅助不叫 `tests/common.rs`，而放 `tests/common/mod.rs`**——`tests/` 下任何 `.rs` 都会被当成测试目标，`tests/common.rs` 会被编译成「没有 `#[test]` 的测试 crate」而报错；放 `tests/common/mod.rs` 则只有显式 `mod common;` 引用它的测试文件才编译它。

```rust
// examples/ex01-unit-integration-tree/tests/common/mod.rs —— 集成测试共享辅助（已验证：cargo 1.92.0）
// 每个 tests/*.rs 都写 `mod common;`，拿到的就是同一份构造辅助与设备夹具。
// 注意 #![allow(dead_code)]：每个测试 crate 各自内联本文件，未必用到全部辅助。
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use ex01_unit_integration_tree::{Op, WalWriter};

/// 数据夹具：三段固定合法日志（字节确定，任何测试可对比）
pub fn sample_log_bytes() -> Vec<u8> {
    let mut w = WalWriter::new();
    w.append(1, Op::Put, b"temperature", b"36.5");
    w.append(2, Op::Delete, b"humidity", b"");
    w.append(3, Op::Put, b"city", b"tokyo");
    w.as_bytes().to_vec()
}

/// 设备夹具：写临时文件，Drop 自清理（细节见 3.3）
pub struct TempFile { /* ... */ }
```

```rust
// examples/ex01-unit-integration-tree/tests/independent_crate.rs（节选，已验证）
mod common; // 每个集成测试文件各自声明，共享 tests/common/mod.rs
use ex01_unit_integration_tree::{records, WalError};

#[test]
fn truncated_prefix_always_reports_truncated() {
    let full = common::sample_log_bytes();
    for cut in 0..full.len() {           // 逐字节截断扫描（确定性穷举）
        match records(&full[..cut]).next() {
            None => {}
            Some(Ok(_)) => {}
            Some(Err(e)) => assert_eq!(e, WalError::Truncated, "从 {cut} 字节处截断应报 Truncated"),
        }
    }
}
```

单元 vs 集成的分工（回答「测试放哪」）：

| 维度 | 单元测试（src 内） | 集成测试（tests/） |
|------|-------------------|-------------------|
| 可见性 | 能看到私有项（`use super::*`） | 只走 pub API（黑盒） |
| 依赖 | 无 crate 外依赖 | 无 crate 外依赖（都只依赖被测 crate 与其 dev-dependencies） |
| 数量/速度 | 多而快，毫秒级 | 少而慢一点（编译成独立 crate、可做真实 I/O） |
| 守护对象 | 实现细节与不变量 | 契约：pub API 组合起来的行为、错误类别、跨模块协作 |
| 典型失败模式 | 重构改坏内部逻辑 | 改 pub 签名/语义、破坏调用方约定 |

**pub API 面 = 可测面**是这节的深层含义：集成测试够不到的东西，要么不该 pub，要么该重构——「为了能测而暴露」是坏味道，「为了好测而收敛 API」是好设计（ph06/rust-patterns 的 minimal pub surface 在测试视角下的镜像）。ex01 的 `tests/file_roundtrip.rs` 演示了文件级全链路（写盘 → 读回 → 零拷贝解析 → 指针偏移断言），`tests/independent_crate.rs` 演示了「两个集成文件互不共享符号、可单独 `--test`」以及私有项不可见这一边界本身。

### 3.3 test fixtures：数据夹具、设备夹具与构造辅助

**fixture（测试夹具）是「把测试环境摆好」的所有手段**，Rust 生态没有 JUnit `@BeforeEach` 那样的框架设施，惯用法是三类自己动手：

| 类型 | 是什么 | 本阶段形态 | 用途 |
|------|--------|-----------|------|
| 数据夹具（data fixture） | 固定的输入样例 | `tests/fixtures/*.hex`：`#` 注释 + 十六进制字节的**文本**文件 | 合法/坏/边界样例入库，可 diff、可回归 |
| 设备夹具（device fixture） | 临时文件/目录/资源 | 自定义 `TempFile`（构造时写盘、`Drop` 时清理） | 需要真实 I/O 的用例；panic 也不留垃圾 |
| 构造辅助（builder） | 在内存里按参数生成 | `build_log(&[(seq, op, key, value)])` 之类 | 大量/变长输入、roundtrip 基准的确定性来源 |

`.hex` 文本夹具是教学仓库的刻意选择：**字节是二进制的，但样例文件应该让人类可读可 diff**。注释行写「这段期望什么」，hex 行给字节；测试端 `decode_hex_fixture` 剥注释解码后喂解析器。坏样例的制造诀窍：**用被测对象自己的 `WalWriter` 生成合法字节，再改目标字段**——你需要的正是「改了别处、CRC 没跟着改」的损坏输入（ex02/练习 1 的 fixtures 全部由此生成并提交）。格式与偏移表来自 ph19 主文档 3.8：magic@0、crc@4、seq@8、op@16、klen@17..21、vlen@21..25，key 从 25 起。

```rust
// examples/ex02-test-fixtures/tests/fixture_matrix.rs（节选，已验证）—— 异常样例矩阵的骨架
enum Expect { Ok(usize), Empty, Err(fn(&WalError) -> bool), OkThenErr(usize, fn(&WalError) -> bool) }
struct Case { fixture: &'static str, expect: Expect }

const CASES: &[Case] = &[
    Case { fixture: "sample_put_delete_put.hex", expect: Expect::Ok(3) },
    Case { fixture: "err_bad_magic.hex", expect: Expect::Err(is_bad_magic) },
    Case { fixture: "err_bad_op.hex",   expect: Expect::Err(is_unknown_op) },
    Case { fixture: "err_bad_crc.hex",  expect: Expect::Err(is_checksum) },
    Case { fixture: "err_truncated_tail.hex", expect: Expect::OkThenErr(2, is_truncated) },
    Case { fixture: "empty.hex",        expect: Expect::Empty },
];
// Rust 没有内建参数化测试：case 表 + 一个驱动函数就是参数化的惯用法
//（新增样例 = 加一个 .hex + 表里加一行）
```

三个纪律值得一提。**① 设备夹具用 Drop 保证清理**：`TempFile` 把 `remove_file` 放进 `Drop`，断言失败/panic 也不会污染临时目录（ex02 的 `temp_file_survives_real_read_and_cleans_itself` 专门断言 Drop 后文件不存在）。**② 夹具是不可变资产**：一旦提交，除非格式变更不许手改——矩阵测试与「fixture 长度/字节 = 生成器输出」的稳定性测试（ex02 `fixture_files_all_exist_and_decode_to_expected_length`）会抓「夹具被误改」。**③ 不要重复造轮子**：能由构造辅助确定性生成的场景（roundtrip）不必固化成文件；文件夹具的价值在「**保持坏**」——损坏样例一旦写对，永远是该坏的，不会像内存里现造的坏样例那样随代码重构悄悄变好。

### 3.4 mock 与 fake：接口边界上的测试替身

解析器是纯函数（输入字节 → 输出 record），**测纯函数不需要 mock**——这正是可测试设计的方向。mock/fake 登场的地方是**边界副作用**：把 record「应用」进一个存储、从真实文件读、依赖时钟。先分清两个词（术语来源：Test Double 家族，Mackinnon 等人 1999 年的 mock 论文与 xUnit 实践）：

| | fake | mock |
|---|------|------|
| 本质 | **可跑的真实现**（轻量版） | 记录调用、可脚本化的**假对象** |
| 测什么 | 行为正确性：结果对不对 | 交互协议：调了几次、参数对不对、失败怎么传播 |
| 典型 Rust 形态 | 为 trait 写一个内存版实现 | 手写结构体记 `calls` + 预设返回；或 `mockall` 自动生成 |
| 典型用途 | 内存 KV、假存储、假时钟 | 断言「恰好调用 N 次」、注入「第 2 次磁盘满」、验证失败即停 |
| 何时不该用 | —— | 能注入 fake 就别 mock：fake 顺带测了语义，mock 只测了「你喊了」 |

ex03 用一个 `Store` trait 演示两者怎么立在同一个被测对象上：

```rust
// examples/ex03-fake-mock/src/store.rs（节选，已验证：cargo 1.92.0）—— 接口边界 + fake
/// replay 时逐条应用 record 的抽象：被测对象只依赖它，不依赖任何具体存储
pub trait Store {
    fn apply(&mut self, op: Op, seq: u64, key: &[u8], value: &[u8]) -> Result<(), StoreError>;
}

/// fake：内存表完整实现 Store（生产可当冒烟引擎、测试可当「速跑真实现」）
#[derive(Debug, Default)]
pub struct MemoryStore { entries: Vec<Entry> }
impl Store for MemoryStore {
    fn apply(&mut self, op: Op, seq: u64, key: &[u8], value: &[u8]) -> Result<(), StoreError> {
        self.entries.push(Entry { op, seq, key: key.to_vec(), value: value.to_vec() });
        Ok(())
    }
}

/// 被测对象：把整段日志逐条解析并应用到任意 Store（依赖注入的最小区块）
pub fn replay_to<S: Store>(store: &mut S, log: &[u8]) -> Result<usize, ReplayError> { /* ... */ }
```

mock 的手写形态（ex03 `tests/interactions.rs`，已验证）：结构体存 `calls: Vec<Call>` + `fail_on: Option<usize>`；`apply` 先记录调用，命中 `fail_on` 次数就返回 `StoreError("磁盘已满")`。用它断言「恰好调用 3 次、参数逐一对」、注入第 2 次失败验证 `replay_to` 停在 seq=2 且不再尝试第三条。**mockall 概念**：这段样板机械且易错，`mockall` 的 `#[automock]` 能为 trait 自动生成同款 mock 结构（`.expect_apply().times(3)` 之类的 API）；本阶段**只讲概念不引入依赖**——先手写一遍看清本质，生产项目需要大量 mock 时再上 mockall。**mock 的红线**是别让它变成「对着自己的实现抄答案」：mock 只该出现在被测代码的**直接依赖**上（这里 `replay_to` 调 `Store`），不该 mock 被测对象自身或第三方库的内部。

> mock 场景的深层判据：**能注入 fake 就别 mock**——fake 验证了「应用后语义正确」，mock 只验证「调用发生过」。mock 真正的不可替代处是**失败注入**（fake 不会自己坏）与**交互次数/顺序断言**。什么时候两者都不需要？当你的核心是纯函数时——ph19 解析器从头到尾没出现过 mock，这不是遗漏，是纯函数核心 + 边界替身的设计红利（3.7 展开）。

### 3.5 proptest：属性测试与策略组合

手写用例只能覆盖「想得到的输入」；proptest 让测试**声明性质**而不是**枚举用例**：给一个生成器（Strategy），随机取样跑几百上千次，任一用例失败即失败并**收缩**（shrinking）到最小反例。血脉：QuickCheck（Haskell，2000）→ Hypothesis（Python）→ proptest（Rust，1.x 长期稳定，锁定 1.11.0）。属性测试在解析器上最经典的三个性质，全部落在 ex04 与练习 3 里：

| 性质 | 生成什么 | 断言什么 |
|------|---------|---------|
| 永不 panic | 任意字节 `vec(any::<u8>(), 0..512)` | 解析任何输入都不崩溃（panic 即失败） |
| roundtrip | 结构化合法日志（见下） | 编码 → 解析逐字段相等 |
| 字段边界 | 单条 record + 任意后缀 | 解析器只消费自己那一段、剩余字节原样留下 |

```rust
// examples/ex04-proptest-boundary/tests/property_roundtrip.rs（节选，已验证：proptest 1.11.0）
use proptest::prelude::*;

proptest! {
    #![proptest_config(ProptestConfig::with_cases(256))] // 默认 256 用例/性质；PROPTEST_CASES 环境变量可覆盖

    /// 任意合法日志编码后必然逐条解析回来（这是「写入器与解析器互为镜像」的可证明形态）
    #[test]
    fn write_then_parse_roundtrips(entries in common::log()) {
        let bytes = common::encode(&entries);
        let mut it = ex04_proptest_boundary::records(&bytes);
        for (seq, op, key, value) in &entries {
            match it.next() {
                Some(Ok(rec)) => {
                    prop_assert_eq!(rec.sequence, *seq);
                    prop_assert_eq!(rec.op, *op);
                    prop_assert_eq!(rec.key, key.as_slice());
                    prop_assert_eq!(rec.value, value.as_slice());
                }
                other => panic!("构造的合法日志在第 {seq} 条解析异常：{other:?}"),
            }
        }
        prop_assert!(it.next().is_none(), "日志解析完后迭代器必须干净结束");
    }
}
```

策略（Strategy）是 proptest 的语法核心：**值发生器 + 收缩器**。组合规则：

| 组合子 | 含义 | 解析器场景 |
|--------|------|-----------|
| `any::<T>()` | 任意值 | `any::<u8>()` 任意字节 |
| `prop::collection::vec(elem, n)` / `vec(elem, a..=b)` | 定长/区间长 vec | 任意字节串、变长 key/value |
| 元组 `(a, b, c)` | 联合生成 | 把 (seq, op, key, value) 一次抽出 |
| `.prop_map(f)` | 变换值（保持收缩） | 把 bool 映射成 `Op::Put/Delete` |
| `.prop_flat_map(f)` | 先抽参数再按参数生成 | 「先抽 value 长度、再按长度生成内容」 |
| `prop_oneof![a, b, c]` | 按权重混合多条策略 | 常规 record 与「长度钉在 0/1/64/65」的边界 record 混合（sol-03 用 `4 => boundary, 9 => random`） |

自定义策略放 `tests/common/mod.rs` 由多个属性文件共享（ex04/sol-03 都这么做）。**为什么 roundtrip 必须生成「结构合法」的输入**：`prop_assert_eq!` 断言的是解析结果与写入一致，喂任意字节只会得到「解析失败」，测不出编码器与解析器是否互为镜像——所以 roundtrip 性质用自定义的合法 record 策略，而「永不 panic」性质故意用任意字节。两者生成域不同，职责不同，**别混用**。

**收缩（shrinking）**：性质失败时，proptest 沿「值树」反复简化输入直到无法再简化，报告 `minimal failing input`，并把一行可复现的 `cc <hash>` 写进 `tests/*.proptest-regressions` 文件（这些回归文件应提交，防同款 bug 复发）。本机实测收缩输出（故意写错的性质 `断言字节和 < 10`，proptest 1.11.0）：

```text
Test failed: sum = 10 at tests/shrink.rs:8.
minimal failing input: xs = [
    10,
]
```

即从几百字节随机输入一路缩到「单个元素 10」。`PROPTEST_CASES=4096 cargo test` 可加大轰炸量，CI 上想固定预算时用 `PROPTEST_CASES` 环境变量（不必改代码）。

### 3.6 criterion：统计化基准与噪声控制

内置基准需要 nightly（`#![feature(test)]` + `#[bench]`），稳定版 Rust 用 **criterion**：`cargo bench` 即可跑，统计化地报告耗时区间与置信度。接线方式：Cargo.toml 加 `[dev-dependencies] criterion` + `[[bench]] name = "..." harness = false`（harness=false 表示不用 libtest，criterion 接管 main），bench 文件用 `criterion_group!`/`criterion_main!` 注册。ex05 演示了完整形态（已验证：criterion 0.8.2）：

```rust
// examples/ex05-criterion-bench/benches/parse_compare.rs（节选，已验证）
use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};

fn bench_replay_paths(c: &mut Criterion) {
    let mut group = c.benchmark_group("replay_borrowed_vs_owned");
    // BenchmarkId + 尺寸参数：同一基准扫多个输入规模
    for &(records, vlen) in &[(1_000usize, 16usize), (10_000, 256)] {
        let log = build_log(records, vlen);
        group.throughput(Throughput::Bytes(log.len() as u64)); // 顺带报吞吐
        group.bench_with_input(BenchmarkId::new("borrowed_zero_copy", format!("{records}x{vlen}B")),
            &log, |b, log| b.iter(|| replay_borrowed(black_box(log)).expect("合法日志")));
        group.bench_with_input(BenchmarkId::new("owned_with_copy", format!("{records}x{vlen}B")),
            &log, |b, log| b.iter(|| replay_owned(black_box(log)).expect("合法日志")));
    }
    group.finish();
}
criterion_group! { name = benches; config = config(); targets = bench_replay_paths }
criterion_main!(benches);
```

核心概念按 ph20 需要的深度展开：

**① 防止死代码消除**：迭代闭包里凡是不影响输出的中间量都要 `black_box`（criterion 0.8 起用 `std::hint::black_box`，`criterion::black_box` 已弃用——本仓库按新 API 实测零警告）。

**② 噪声控制**：基准测的是「代码 + 机器 + 调度」的联合，噪声来自 CPU 频率、缓存冷热、后台进程。criterion 的内置手段：

| 手段 | 参数 | 说明 |
|------|------|------|
| 预热 | `warm_up_time` | 让 JIT/频率/缓存先稳定，默认 3s |
| 测量时长 | `measurement_time` | 越久样本越稳，默认 5s |
| 样本量 | `sample_size` | 统计样本数，默认 100 |
| 置信水平 | `confidence_level` | 报告区间的置信度，默认 0.95 |

教学演示常调小加速（ex05 用 300ms/2s/20），**正式结论请放宽回默认并连续跑两次取第二次**（第一次含编译与预热噪声）。基准输出 `time: [lower mean upper]` 即 95% 区间。

**③ 回归对比**：criterion 把每次结果存档在 `target/criterion/`（`CARGO_TARGET_DIR` 之下，仓库零残留）。优化前后各存一次基线再对比（命令见 ex05/exercises/ex4 的 Cargo.toml 注释）：

```bash
CARGO_TARGET_DIR=/tmp/ph20-target cargo bench --bench parse_compare -- --save-baseline v1   # 优化前存档
# ……改代码 / 换实现……
CARGO_TARGET_DIR=/tmp/ph20-target cargo bench --bench parse_compare -- --baseline v1        # 与 v1 对比
```

实测输出（criterion 0.8.2，本机）：

```text
replay_borrowed_vs_owned/owned_with_copy/10000x256B
                        time:   [6.6113 ms 6.9545 ms 7.2420 ms]
                 change:  time:   [−14.287% −9.9072% −5.4423%] (p = 0.00 < 0.05)
```

`change` 行给出相对基线的变化区间与显著性 p 值（统计方法见 4.3）。**阈值说明**：criterion 没有内置「change 超 ±5% 就失败退出」的开关——CI 判红通常由两件事拼成：`--save-baseline` 存档 + 解析 `change` 输出比对阈值（或配 cargo-criterion 的阈值）。本阶段把「给结论」教会，把它「自动化成门禁」交给 ph21（CI 编排）与 ph22（系统化性能方法）。

ex05 实测还顺带回答了 ph19 的预告（本机数值，量级参考）：`1000 条 × 16B` 场景，零拷贝借用 ≈ 30µs（约 1.5 GiB/s），逐条复制 ≈ 96µs（约 0.5 GiB/s）——**约 3× 差距**；到 `10000 × 256B` 大 value 场景差距收窄到 ~10%（复制变成 memcpy 带宽主导）。这就是「零拷贝收益在分配次数敏感的小记录场景最明显」的基准证据——**结论要由测量给，这正是 3.6 存在的理由**。

### 3.7 可测试设计：依赖注入、接口边界与纯函数核心

测试体系的隐形前提是**代码本身好测**。把 ph19 解析器与 ex03 的 store 放在一起看，可测试设计收敛成四条纪律：

| 纪律 | 含义 | 解析器场景的体现 |
|------|------|-----------------|
| 纯函数核心 | 把计算与副作用分开：核心吃输入吐输出 | `parse_record(buf) -> Result<(Record, usize), _>` 不碰文件不碰时钟；I/O 在调用方 |
| 接口边界 | 副作用/外部依赖用 trait 抽象 | `replay_to(store: &mut impl Store, log)` 不依赖具体存储（ex03） |
| 依赖注入 | 依赖从参数进，不全局取 | `replay_to` 的 `store` 参数让 fake/mock 随意换（比 `static mut` 全局可测一万倍） |
| 确定性 | 测试里没有「随机的时间/顺序」 | 序列号由调用方给（WAL record 带 `seq` 字段而非解析器自己取时间）；ph25 真引擎同理由外部注入时钟 |

判据一句话：**一个逻辑「难测」通常不是测试的问题，是边界没划对**。纯函数核心 + 接口边界让每层都只有一种测法——解析层喂字节断言输出、应用层喂 Store 断言行为/协议、I/O 层用设备夹具摆真文件。若发现某段代码「得先建一堆全局状态才能测」，先重构再补测试（rust-patterns 的 minimal pub surface 也是测试友好设计：pub API 面收敛 = 集成测试要守的契约面收敛）。

> 本阶段只到「把依赖注入与接口边界作为测试性前提」；**架构层面的依赖注入框架/容器、更系统的分层设计属于 Rust 工程化后续阶段**（roadmap 无专门章节，本项目靠 exercises/examples 的模式内化即可）——记住最小区块：被测函数签名里加一个 trait 参数，替身就插进去了。


## 4. 底层原理

### 4.1 test harness 如何收集 #[test]

`cargo test` 不是一个测试运行器，而是**一堆测试运行器的调度器**：它会为 lib（及其 `#[cfg(test)]` 模块）、每个 `tests/*.rs`、每个 `[[bench]]`、doctest 分别编译出一个带 test harness 的二进制，逐个执行（`Doc-tests`、`Running unittests src/lib.rs`、`Running tests/xxx.rs` 各是一个目标）。每个目标内部的机制是：`#[test]` 属性把函数注册进一张静态表，编译器生成的 `main`（libtest）遍历该表逐个调用——失败靠 panic 传播，成功靠返回；并行度默认 = 逻辑核数（`--test-threads 1` 关掉，测试间共享临时资源时常用）。`#[cfg(test)]` 是纯编译期裁剪：测试代码在 `cargo build` 里根本不存在。

```text
cargo test
├── 单元目标 lib：编译 src/**（含 #[cfg(test)] 模块）→ 跑内嵌 #[test]
├── 集成目标 tests/*.rs：每个文件一个独立 crate（只 link 被测库）→ 各跑各的
├── 基准目标 [[bench]]：harness=true 用 libtest；harness=false 由文件自己接管 main
└── doctest 目标：抽取 /// 与 //! 的 ```rust 块逐一编译执行
        ▲ 每个目标 = 一个独立进程；失败不影响其他目标
```

为什么测试目标之间进程隔离：**每个 tests/*.rs 独立链接**，测试文件里 `mod common;` 的辅助代码是各自内联的副本（不是共享库）——这正是 `#![allow(dead_code)]` 在共享模块里常见的原因。名字过滤是 libtest 提供的子串匹配：`cargo test truncated` 只跑名字含 `truncated` 的用例；`cargo test -- --nocapture` 让 `println!` 直出（criterion 等自定义 harness 则接管自己的参数，见 3.6 的 `--` 用法与 4.3 的 `harness=false` 理由）。

### 4.2 proptest 收缩算法直觉

收缩不是「二分找 bug」，而是**沿生成树走捷径**。proptest 把每个随机值记成一棵「值树」（ValueTree）：根是原始随机值，向下是若干「更简单」的候选（int 向 0/边界减半、vec 删元素/缩短、结构递归缩小到子结构）。性质失败时，proptest 尝试当前节点的简化候选；若候选仍失败就继续深入，直到任何简化都不再失败——停在**局部最小反例**。3.5 实测的 `[10]`（从几百字节随机输入缩来）展示的正是这条路径：先删元素删到 1 个，再把该元素往 0 减到 10（再减就通过，因为 9 < 10）。收缩让属性测试从「报错但不可读」变成「给你最小复现」——这是 QuickCheck 家族相对纯随机 fuzzing 的关键优势。`*.proptest-regressions` 文件就是收缩结果的**固化**：失败的最小输入以 `cc <hash>` 一行存档，下次跑直接重放，同一 bug 改完再犯立刻被抓（属性测试版的回归测试）。

### 4.3 criterion 的统计方法：它在报什么

criterion 不报告单次计时，而是报告一组统计量。机制直觉：基准函数会被调用很多轮，每轮测出一次耗时；criterion 对这些样本做**重采样**（bootstrap：有放回地反复抽样，估计「均值这类统计量在不同样本下的波动」），得到均值/中位数的置信区间，打印成 `time: [下界 均值 上界]`（默认 95% 置信）。对比基线时，报告**变化百分比区间**与 **p 值**（`change: time: [−14.287% −9.9072% −5.4423%] (p = 0.00 < 0.05)`）：区间不跨 0 且 p < 0.05 即判「统计显著」，说明这次改动对性能的影响不太可能是噪声造成的。**统计显著 ≠ 工程重要**：`p < 0.05` 只回答「有没有变化」，`−9.9%` 才回答「变化多大」——两个数都要读。这也解释了噪声控制的必要：样本越少、机器越吵，置信区间越宽，本来显著的变化会被噪声吞掉，所以正式对比要放宽 measurement_time/sample_size（3.6）。

`harness = false` 的机制也在这里：criterion 需要完全接管进程（自己的参数解析、自己的报告落盘 `target/criterion/`、保存基线），libtest 的参数协议（`--test-threads` 等）不适用——所以 `cargo bench -- --save-baseline v1` 要配 `--bench <名字>` 把参数只传给该基准目标，否则会落到 libtest 目标上报「Unrecognized option」（本机实测的坑，见 3.6 命令）。

### 4.4 fixtures 与 CI 缓存

夹具在 CI 里的两个特性值得点破。**① 数据夹具是提交的资产**：`.hex` 样例随代码入库，每次 CI 全量重跑但输入恒等——错误样例矩阵因此是确定性回归（同一输入永远该报同一类错）；夹具文件小、文本化，diff 友好。**② 设备夹具与缓存的关系**：CI 缓存策略只缓存「慢且不变」的东西（cargo 的依赖与 registry、可选 sccache 编译缓存），**不缓存测试产物**——否则 stale 的 target/criterion 基线会让基准对比失真。fixtures 本身不用缓存（轻、常变、应每次现读）。把「缓存依赖、重跑测试、基准另存基线」三件事分开，是 CI 设计里让测试可信的前提；CI 的矩阵/编排本身属 [ph21 Clippy、rustfmt、CI 与代码质量阶段](../ph21-code-quality-ci/21-code-quality-ci.md)，本阶段只需理解「夹具恒等 + 产物不缓存」这两条测试侧原则。

## 5. 使用场景

**测试金字塔在 Rust 的落地**（ph11 给过理念，本阶段给完整形态）：

```text
            端到端/手工  ← 少，交付前冒烟（本阶段不写：需要完整系统）
           ┌─────────────────────────┐
          / 集成测试（tests/）         \  ← 中量：真实样例、错误矩阵、文件链路
         / ────────────────────────────\    契约层，跑得稍慢
        /  属性测试（proptest）          \  ← 补盲区：任意字节/边界组合
       └─────────────────────────────────┘
        ┌─────────────────────────────┐
        │ 单元测试（#[cfg(test)]）     │  ← 大量：贴实现的快速用例，毫秒级
        └─────────────────────────────┘
        ┌─────────────────────────────┐
        │ 基准（criterion）            │  ← 不属于金字塔：横向的「性能回归」轨道
        └─────────────────────────────┘
```

| 场景 | 用什么 | 理由 |
|------|--------|------|
| 修了一个解析 bug | 先加异常样例夹具再修（回归测试先行） | 坏样例从此保持坏，bug 复发立刻被抓（roadmap 验收「bug 修复伴随回归测试」） |
| 协议/解析器边界 | proptest 任意字节 + 构造日志 roundtrip | 手写样例补不齐的错位/长度怪值（ex04、练习 3） |
| 依赖存储/网络/时钟 | trait 边界 + fake（行为）/ mock（协议与失败注入） | 注入替身测「应用语义」与「失败即停」（ex03） |
| 性能结论 | criterion group + 基线对比 | 「快」要有可重复数字与统计显著性（ex05、练习 4、project bench） |
| 文档与 API 示例 | doctest | 文档里的代码被测试守护，不撒谎 |
| 什么时候不写测试 | 一次性脚本、探索原型 | 先直白后加固：核心路径稳定后再按金字塔补（ph22 的「先测量后优化」同理） |

**跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）。Rust 的测试设施与主流语言的最大分水岭是：**没有「测试框架」这一层**——Go 也是标准库风格（`testing.T` + `go test` 自动收集 `TestXxx`），Python/JVM 则普遍是第三方框架（pytest、JUnit）管理发现与夹具：

| 维度 | Rust（libtest + 生态） | Go testing | Java JUnit 5 | Python pytest |
|------|----------------------|------------|--------------|---------------|
| 测试即代码 | `#[cfg(test)]` 模块与实现同 crate、可看私有项 | 同包 `_test.go` 可看私有 | 独立 test 源集，反射发现 | 独立文件，命名/类收集 |
| 断言 | 宏 `assert_eq!`/`matches!`（panic 即失败） | `t.Errorf`/`require` | AssertJ/JUnit `assertThat` | `assert` 语句 + 插件 |
| 夹具 | 无内置：文件、TempFile、构造辅助自己约定 | `TestMain`/helper | `@BeforeEach`/`@TempDir`/`@ExtendWith` | `fixture`（同名最强） |
| 参数化 | 无语法：case 表惯用法 | table-driven（`t.Run` 子测试） | `@ParameterizedTest` + `@CsvSource` | `@pytest.mark.parametrize` |
| 属性测试 | proptest（自定义 Strategy） | `testing/quick`（较弱）/ `rapid` | jqwik | hypothesis（@given + 策略） |
| mock | trait + 手写/`mockall` | interface + gomock/mockery | Mockito | monkeypatch/unittest.mock |
| 基准 | criterion（第三方，统计化） | `testing.B` 内置（`go test -bench`） | JMH（JVM 专用） | pytest-benchmark |
| 测试金字塔直觉 | 由类型系统支撑「贴实现 vs 走 API」双视角 | 包内白盒 vs 包外黑盒 | 反射让一切皆可注入 | 动态语言注入最轻 |

跨语言读出的规律：**夹具/参数化是「框架派」（JUnit/pytest）擅长而「标准库派」（Rust/Go）不内置的，Rust/Go 用 case 表与共享模块手工补齐；属性测试与基准则是 QuickCheck/Hypothesis/criterion 这类「生成/统计工具」的天下，与测试框架解耦**。Rust 的特殊点在 2 节说过：模块系统让「单元/集成」不是物理目录强制，而是可见性选择——同一份代码既能白盒又能黑盒。

**mock 使用场景再收一句**：mock 只适合「被测代码的直接依赖且有协议要守」的边界（存盘失败、重试次数、通知恰好一次）；纯计算、纯解析永远不该出现 mock——出现说明有副作用混进了纯函数，先拆（3.7）。


## 6. 代码示例

本节展示示例的关键片段，完整工程在 [`examples/`](./examples/)。验证环境：rustc/cargo 1.92.0（macOS arm64）+ proptest 1.11.0 / criterion 0.8.2。**验证说明**：ex01~ex05 均已本机实测（`cargo test`/`cargo bench` 全绿，fmt/clippy `-D warnings` 全绿），全部标注「已验证」。逐示例运行命令见 [`examples/README.md`](./examples/README.md)。

| 示例 | 对应主文档 | 一句话说明 | 验证状态 |
|------|-----------|-----------|---------|
| [`examples/ex01-unit-integration-tree/`](./examples/ex01-unit-integration-tree/) | 3.1/3.2 | 单元 vs 集成测试目录工程：断言宏/`#[should_panic]`/`#[ignore]`/doctest、`tests/` 独立 crate、`tests/common/mod.rs` 共享辅助 | 已验证 |
| [`examples/ex02-test-fixtures/`](./examples/ex02-test-fixtures/) | 3.3 | test fixtures：`tests/fixtures/*.hex` 数据夹具 + TempFile 设备夹具 + 构造辅助 + 异常样例矩阵 | 已验证 |
| [`examples/ex03-fake-mock/`](./examples/ex03-fake-mock/) | 3.4/3.7 | `Store` trait 接口边界：fake（MemoryStore）测行为、手写 mock 测协议与失败注入、`replay_to` 依赖注入 | 已验证 |
| [`examples/ex04-proptest-boundary/`](./examples/ex04-proptest-boundary/) | 3.5/4.2 | proptest：任意字节不 panic、roundtrip、字段边界不读穿；自定义策略与收缩 | 已验证 |
| [`examples/ex05-criterion-bench/`](./examples/ex05-criterion-bench/) | 3.6/4.3 | criterion：零拷贝 vs 复制的解析路径对比、参数扫描、噪声控制、基线回归 | 已验证 |

### 示例 1：单元与集成测试目录工程（`examples/ex01-unit-integration-tree`）

```text
src/lib.rs                  # 被测对象 + #[cfg(test)] 单元测试
                            #   （同文件 mod tests 看私有项；兄弟模块 assert_styles 走 pub API）
tests/common/mod.rs         # 共享辅助：sample_log_bytes() 数据夹具 / TempFile 设备夹具
                            #   （命名成 common.rs 会被当测试目标，见 3.2）
tests/file_roundtrip.rs     # 集成：真实文件写读全链路 + 零拷贝指针偏移断言
tests/independent_crate.rs  # 集成：逐字节截断语义 + 「集成测试看不到私有项」的可见性边界
```

实测（cargo 1.92.0）：`cargo test` 让 lib 单元、两个 `tests/*.rs`、doctest 各自独立成目标运行——单元 12 通过 + 1 忽略（`#[ignore]` 的慢用例需 `--ignored` 显式跑）、两个集成目标各 2 条、doctest 1 条；`matches!`/`#[should_panic]`/Result 返回测试全部覆盖（断言宏的语义见 3.1）。

### 示例 2：test fixtures 三件套（`examples/ex02-test-fixtures`）

```text
tests/fixtures/*.hex        # 数据夹具：真实/坏/边界样例（# 注释 + hex，共 7 个文件）
tests/common/mod.rs         # decode_hex_fixture / build_log 构造辅助 / TempFile 设备夹具
tests/fixture_matrix.rs     # case 表驱动：每个夹具断言「该 Ok 的 Ok、该报哪类错报哪类错」
tests/device_and_constructor.rs # 真实文件全链路、变长键 roundtrip、夹具长度稳定性守护
```

实测（cargo 1.92.0）：单元 12 通过 + 1 忽略、集成 5 条（矩阵 2 + 设备/构造 3）、doctest 1，全绿；`TempFile` 的 Drop 清理有专门用例断言「Drop 后文件不存在」。

### 示例 3：fake 与 mock 共用一个被测对象（`examples/ex03-fake-mock`）

```rust
// examples/ex03-fake-mock/src/store.rs —— trait 边界 + 依赖注入（已验证：cargo 1.92.0）
pub trait Store {
    fn apply(&mut self, op: Op, seq: u64, key: &[u8], value: &[u8]) -> Result<(), StoreError>;
}

pub fn replay_to<S: Store>(store: &mut S, log: &[u8]) -> Result<usize, ReplayError> {
    let mut applied = 0;
    for item in records(log) {
        let rec = item.map_err(ReplayError::Parse)?;
        store.apply(rec.op, rec.sequence, rec.key, rec.value)
            .map_err(|source| ReplayError::Apply { seq: rec.sequence, op: rec.op, source })?;
        applied += 1;
    }
    Ok(applied)
}
```

实测行为：fake（`MemoryStore`）与 mock（tests 里手写 `MockStore`）对同一日志给出的观测完全一致（有交叉验证测试）；mock 注入「第 2 次磁盘满」后 `replay_to` 返回 `Apply` 错误且不再尝试第三条；截断日志应用前缀后报 `Parse(Truncated)`——三类替身场景（行为/协议/失败注入）一个被测对象全演示。

### 示例 4：proptest 属性（`examples/ex04-proptest-boundary`）

```rust
// examples/ex04-proptest-boundary/tests/common/mod.rs —— 自定义策略（已验证：proptest 1.11.0）
pub fn record_with_suffix() -> impl Strategy<Value = (Vec<u8>, Vec<u8>)> {
    (record(), prop::collection::vec(any::<u8>(), 0..=128)).prop_map(
        |((seq, op, key, value), suffix)| {
            let mut w = WalWriter::new();
            w.append(seq, op, &key, &value);
            let mut bytes = w.as_bytes().to_vec();
            bytes.extend_from_slice(&suffix); // 合法 record + 任意后缀
            (bytes, suffix)
        },
    )
}
```

实测行为：4 个测试文件全绿——任意字节（512 字节上限）解析永不 panic、错误类别封闭在 `WalError` 五变体内、`HEADER_LEN` 以下输入必报 Truncated、构造日志 roundtrip 逐字段相等、「record + 任意后缀」验证 `used` 恰为字段总长且剩余字节原样留下。跑 `PROPTEST_CASES=4096 cargo test` 加大轰炸量仍全绿。

### 示例 5：criterion 基准（`examples/ex05-criterion-bench`）

```rust
// examples/ex05-criterion-bench/benches/parse_compare.rs —— 双路径对比（已验证：criterion 0.8.2）
group.bench_with_input(BenchmarkId::new("borrowed_zero_copy", format!("{records}x{vlen}B")),
    &log, |b, log| b.iter(|| replay_borrowed(black_box(log)).expect("合法日志")));
group.bench_with_input(BenchmarkId::new("owned_with_copy", format!("{records}x{vlen}B")),
    &log, |b, log| b.iter(|| replay_owned(black_box(log)).expect("合法日志")));
```

实测输出（节选）：`borrowed_zero_copy/1000x16B time: [29.029 µs 30.185 µs 31.241 µs]`（约 1.54 GiB/s）vs `owned_with_copy/1000x16B time: [91.302 µs 96.335 µs 102.34 µs]`（约 0.49 GiB/s）——零拷贝路径约快 3×。跑 `--save-baseline v1` 后再 `--baseline v1` 能看到 `change` 区间与 `p` 值（3.6）。

完整代码层还包括：[`exercises/`](./exercises/)（共享被测对象 `record-parser` + 练习 1~4 参考实现，均验证通过）与 [`project/`](./project/)（record-test-suite 综合套件，见 7 节阶段项目）。

## 7. 总结

### 关键要点

- **测试放哪由可见性决定**：看私有实现 → 同文件 `#[cfg(test)]` 单元测试；守 pub 契约 → `tests/` 独立 crate 集成测试；`tests/common/mod.rs` 是共享辅助的约定位置（放 `common.rs` 会被当成测试目标）（3.1/3.2）
- **断言宏家族是断言语义**：`assert_eq!` 比值、`matches!` 比形状、Result 返回测试让 `?` 传播错误、`#[should_panic(expected)]` 只用于「调用方违约」的契约；测试代码的 expect 属断言语境，生产代码无裸 unwrap（3.1）
- **fixtures 三类分清楚**：数据夹具（固定样例文件，文本 hex 可 diff）、设备夹具（TempFile，Drop 自清理）、构造辅助（内存生成）；异常样例矩阵 = 每类坏输入一个固定夹具 + case 表断言（3.3）
- **fake 测行为、mock 测协议**：trait 边界上，fake 是可跑的真实现（内存版），mock 记录调用可注入失败；**能注入 fake 就别 mock**，纯函数核心根本不需要 mock（3.4/3.7）
- **属性测试声明性质而非枚举用例**：proptest 的 Strategy 是「生成器 + 收缩器」，roundtrip 用合法结构策略、永不 panic 用任意字节策略——两者别混用；失败自动收缩到最小反例并写入 regression 文件（3.5/4.2）
- **criterion 是统计化测量**：`harness=false` 接管进程，group/BenchmarkId 扫参数、Throughput 报吞吐；`time: [下界 均值 上界]` 是置信区间，`change` + p 值判显著性；噪声控制 = warm-up/measurement/sample_size（3.6/4.3）
- **可测试设计先于测试**：纯函数核心 + trait 接口边界 + 依赖从参数进 + 确定性，让每层都只有一种测法；「难测」通常是边界没划对（3.7）
- **性能结论要可重复**：零拷贝 vs 复制不是信仰，是 criterion 对比出来的测量差（小 value 场景约 3×）；同一代码优化前后用 `--save-baseline`/`--baseline` 看 `change` 区间（3.6）

### 阶段验收清单

- [ ] 能说清单元测试、集成测试、属性测试、基准各自「放哪、测什么、什么时候写」（可画出本文的测试金字塔图）
- [ ] 能为一个现有解析器搭出 `tests/` + `tests/common/mod.rs` + fixtures 的目录工程，并把一条新回归 bug 固化成「夹具 + case 表一行」
- [ ] 能为解析器补异常样例测试：每类 `WalError` 一个坏夹具、逐截断点全扫不 panic、单字节翻转不 panic（练习 1 验收）
- [ ] 能用 proptest 测边界输入：自定义合法日志策略 + roundtrip 性质 + 任意字节不 panic 性质，失败时能读懂 `minimal failing input`（练习 3 验收）
- [ ] 能用 criterion 对比优化前后：扫两个以上尺寸、报 `time`/`thrpt`、显式配置噪声控制、能跑基线对比并读出 `change` 与 p 值（练习 4 验收）
- [ ] 能解释 fake 与 mock 的区别与选用判据；能指出「纯函数不需要 mock」的理由
- [ ] 核心逻辑有正反测试（roadmap 验收「能让核心逻辑有正反测试」）、bug 修复伴随回归测试（roadmap 验收）、性能结论有可重复基准（roadmap 验收）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。四题与 roadmap 第 20 节练习对应：练习 1 =「为解析器加入异常样例测试」（异常样例矩阵 + fixtures），练习 2 =「集成测试目录组织 + 共享模块 + 假引擎」，练习 3 =「用 proptest 测边界输入」，练习 4 =「用 criterion 对比优化前后」。被测对象共用 [`exercises/record-parser/`](./exercises/record-parser/)（ph19 解析器复刻，自带单元测试）。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**record 解析测试套件**——真实样例 + 错误样例 + proptest + 基准测试合体（roadmap 第 20 节推荐项目落地，`tests/` 组织 + fixtures 目录 + criterion bench + CLI 演示，全部验收标准与命令见 project/README.md）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`cargo test` 全绿 + `cargo bench` 可跑 + fmt/clippy 零告警）

### 跨语言对比

- Rust 的「单元/集成」是**可见性选择**而非目录强制（同 crate 白盒、`tests/` 黑盒），Go 靠同包 `_test.go`、JVM/Python 靠独立源集与反射/运行时注入——模块系统让 Rust 测试能贴着任何抽象层，这是它的结构性优势（为 analysis/ 与 Tenet 合成积累素材，详见 5 节对比表）

### 下一阶段

[**ph21 Clippy、rustfmt、CI 与代码质量阶段**](../ph21-code-quality-ci/21-code-quality-ci.md)——本阶段把测试体系搭起来了，下一阶段回答「如何让这套体系被强制遵守」：`cargo fmt --check` 与 `cargo clippy -- -D warnings` 作为质量门禁进 CI，lint 等级与例外管理，GitHub Actions 的矩阵构建与缓存策略——把本阶段手敲的每条质量命令变成每次 PR 自动执行的关卡；届时本阶段的 record-test-suite 正好当第一个接入 CI 的样板工程。
