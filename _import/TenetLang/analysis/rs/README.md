# 🔬 Rust 语言设计分析（analysis/rs）

> 一步步分析 Rust 的语言设计，每篇主题配一个可运行的 demo。
> 分析结论汇总到 [`Tenet`](../../tenet/Tenet架构设计.md)，作为 Tenet 语言设计的输入。

> 🧭 **定位**：本目录是「设计解剖」——讲*为什么*这么设计。
> 对应的「学习笔记」（讲*怎么学*）在 [`languages/rs/`](../../languages/rs/)，建议先学后析。

Rust 的核心设计命题：**在没有 GC 的前提下，把内存安全和并发安全变成编译期保证**。
整个语言围绕这一个命题展开——所有权、借用、生命周期、trait、Result、Send/Sync 都是它的推论。

## 分析路线

| # | 主题 | 核心问题 | Demo |
|---|------|---------|------|
| 01 | [所有权与借用](notes/01-ownership.md) | 不用 GC 怎么保证内存安全？ | `cargo run --bin 01_ownership` |
| 02 | [生命周期](notes/02-lifetimes.md) | 引用能活多久，编译器怎么知道？ | `cargo run --bin 02_lifetimes` |
| 03 | [trait 与泛型](notes/03-trait-generics.md) | 不用继承怎么做多态？还零开销？ | `cargo run --bin 03_trait_generics` |
| 04 | [Option/Result 错误处理](notes/04-option-result.md) | 不用异常怎么显式处理错误？ | `cargo run --bin 04_option_result` |
| 05 | [Send/Sync 并发安全](notes/05-send-sync.md) | 数据竞争怎么变成编译错误？ | `cargo run --bin 05_send_sync` |

## 快速开始

```bash
cd analysis/rs/demos
cargo run --bin 01_ownership    # 依次试 01~05
```

## 分析方法

每篇笔记的结构：

1. **设计动机**——这门语言为什么要做这个设计（解决什么问题）
2. **机制拆解**——语法/语义/编译期规则怎么实现这个设计
3. **代码验证**——用最小 demo 亲眼看到机制在工作
4. **代价与取舍**——这个设计牺牲了什么
5. **对 Tenet 的启示**——哪些值得吸收，哪些应该拒绝（输入 Tenet架构设计.md（完整文档 §1 设计溯源））
