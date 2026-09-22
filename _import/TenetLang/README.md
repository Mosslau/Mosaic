# 🏛 TenetLang

> **万语归宗，探语言之本源**
>
> *All languages converge. We seek the tenet beneath them.*

一个编程语言学习与实践仓库，三条主线：**学习** 6 门语言 → **分析** 它们的语言设计 → **合成** 一门属于自己的语言 **Tenet**。

**先看哪个？** 三个目录族各回答一个问题，互不重复：

| 目录 | 角色 | 回答的问题 | 适合 |
|------|------|-----------|------|
| `languages/` | **学**（学习笔记） | 这门语言有什么、怎么学 | 入门 / 系统学习某门语言 |
| `analysis/` | **析**（设计解剖） | 这门语言**为什么**这么设计、代价是什么 | 想懂设计、准备做语言 |
| `tenet/` | **合 + 实现** | 吸收了哪些优点、合成出什么、编译器怎么写 | 追 Tenet 本身 |

建议路线：先 `languages/<语言>/` 学会一门语言 → 再看对应 `analysis/<语言>/` 理解它的设计 →
最后看 `tenet/` 看这些设计如何被吸收、合成、实现。

## 📚 Part 1 · 学习笔记库

6 种主流语言的系统化学习路线：**C、C++、Go、Java、Python、Rust**。

| 层级 | 位置 | 内容 |
|------|------|------|
| Roadmap 总览 | `languages/<语言>/<语言>.md` | 分阶段学习路线：目标 / 学习内容 / 必会概念 / 示例 / 练习 / 阶段验收 / 推荐项目 |
| 阶段详解 | `languages/<语言>/ph01..phNN-<主题>/`（NN 为末阶段编号，随 roadmap 规划） | 每个阶段的完整展开：来源与演变 / 语法与参数 / 底层原理 / 代码示例 / 总结验收 |

> ✅ 6 条路线已全部建成：C 16 · Python 18 · Go 21 · Java 23 · C++ 23 · Rust 25，合计 **126 个编号阶段**，每阶段均含 examples / exercises / project 代码层。

## 🔬 Part 2 · 语言设计分析

不是"学完就完"，而是**解剖每门语言的设计**：核心设计命题、机制拆解、代价取舍。
每篇笔记配一个可运行的 demo，末尾标注「对 Tenet 的启示」。

| 分析台 | 分析对象 | 主题（notes/） |
|--------|---------|----------------|
| [`analysis/rs/`](analysis/rs/) | Rust：内存安全如何成为编译期保证 | 所有权与借用 / 生命周期 / trait 与泛型 / Option·Result / Send·Sync |
| [`analysis/cpp/`](analysis/cpp/) | C++：零成本抽象与多范式并存 | RAII / 移动语义 / 多范式 / STL 设计 / constexpr |
| [`analysis/java/`](analysis/java/) | Java：托管运行时（JVM）的工程赌注 | GC 与自动内存 / 类型系统·泛型擦除 / 单继承与接口 / 受检异常 / JMM 与并发原语 |
| [`analysis/py/`](analysis/py/) | Python：开发者体验优先的取舍 | 动态类型 / 数据模型 / 装饰器 / 生成器 / 上下文管理器 |

> 待建：`go`（并发与 channel 设计）、`c`（零抽象代价与指针）两门分析台——`analysis/` 目前覆盖 rs / cpp / java / py 四门。

## ⚙️ Part 3 · Tenet 语言与编译器

在 `languages/` 六门路线与 `analysis/` 已建分析的基础上，**继承优点、拒绝包袱**，合成 Tenet——并实现一个
**clang / rustc 式原生编译器**：`tenet build hello.tenet` 产出可直接运行的二进制。

```text
hello.tenet
   │
   ├─▶ 词法分析 → Token 流
   ├─▶ 语法分析 → AST
   ├─▶ 类型检查与推断
   ├─▶ 代码生成 → LLVM IR
   ├─▶ clang 链接 → hello（原生二进制，直接运行）
```

- [`tenet/README`](tenet/README.md) — 语言与编译器入口（速览、快速开始、导航）
- [`tenet/Tenet`](tenet/Tenet架构设计.md) — **完整文档**：设计溯源 / 语言规范 / 架构 / LLVM 后端 / 实现 / 演进
- [`tenet/compiler-rs/`](tenet/compiler-rs/) — **实现 · Rust**（clang 驱动 LLVM）：`tenet build` / `tenet run`
- [`tenet/compiler-cpp/`](tenet/compiler-cpp/) — **实现 · C++17**（进程内调用 LLVM 后端库，rustc 方式）：`make && ./tenet build`
- [`tenet/compiler-arm64/`](tenet/compiler-arm64/) — **实现 · C++17 手写后端**（AArch64 汇编，零 LLVM/clang）：`make && ./tenet build`

「万语归宗」的实践闭环：学习 → 分析 → 合成 → 固化 → 实现 → 运行。

## Why "TenetLang"?

A tenet is a core principle. Every language — C, Rust, Python — is a
different expression of the same underlying ideas. This project digs
beneath the syntax, back to the source — and then builds one from scratch.
