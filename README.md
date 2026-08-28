# 🏛 TenetLang

> **万语归宗，探语言之本源**
>
> *All languages converge. We seek the tenet beneath them.*

一个编程语言学习与实践仓库，三条主线：**学习** 6 门语言 → **分析** 它们的语言设计 → **合成** 一门属于自己的语言 **Tenet**。

## 📚 Part 1 · 学习笔记库

6 种主流语言的系统化学习路线：**C、C++、Go、Java、Python、Rust**。

| 层级 | 位置 | 内容 |
|------|------|------|
| Roadmap 总览 | `lang-<语言>/<语言>.md` | 分阶段学习路线：目标 / 学习内容 / 必会概念 / 示例 / 练习 / 阶段验收 / 推荐项目 |
| 阶段详解 | `lang-<语言>/Ph01..Ph05/` | 每个基础阶段的完整展开：来源与演变 / 语法与参数 / 底层原理 / 代码示例 / 总结验收 |

## 🔬 Part 2 · 语言设计分析

不是"学完就完"，而是**解剖每门语言的设计**：核心设计命题、机制拆解、代价取舍。
每篇笔记配一个可运行的 demo，末尾标注「对 Tenet 的启示」。

| 分析台 | 分析对象 | 主题（notes/） |
|--------|---------|----------------|
| [`tenet-rs/`](tenet-rs/) | Rust：内存安全如何成为编译期保证 | 所有权与借用 / 生命周期 / trait 与泛型 / Option·Result / Send·Sync |
| [`tenet-cpp/`](tenet-cpp/) | C++：零成本抽象与多范式并存 | RAII / 移动语义 / 多范式 / STL 设计 / constexpr |
| [`tenet-py/`](tenet-py/) | Python：开发者体验优先的取舍 | 动态类型 / 数据模型 / 装饰器 / 生成器 / 上下文管理器 |

## ⚙️ Part 3 · Tenet 语言（设计阶段）

分析完三/六门语言，**继承优点、拒绝包袱**，合成 Tenet——当前聚焦**设计**，
实现暂缓（曾用 Rust / Python / C++ 三端完整实现验证过设计可行，代码已移出仓库）：

```text
Tenet 源码
   │
   ├─▶ 词法分析 Lexer ──▶ Token 流
   │
   ├─▶ 语法分析 Parser ──▶ AST
   │                          │
   │                          └─▶ 类型检查 + 解释执行 ──▶ 直接编译运行
   │
   └─▶ REPL（交互式执行）

自包含：tenet run file.tenet 一条命令完成，零外部工具链依赖
```

- [`tenet/design-notes.md`](tenet/design-notes.md) — **设计溯源**：三语言吸收矩阵、每个特性从哪来、拒绝了什么
- [`tenet/grammar.md`](tenet/grammar.md) — **语言规范**：正式文法（EBNF）、类型系统、求值语义（唯一事实来源）
- [`tenet/tenet.md`](tenet/tenet.md) — 语言设计文档：从词法、语法到解释执行的完整路线

「万语归宗」的实践闭环：学习 → 分析 → 合成 →（实现验证待设计成熟后恢复）。

## Why "TenetLang"?

A tenet is a core principle. Every language — C, Rust, Python — is a
different expression of the same underlying ideas. This project digs
beneath the syntax, back to the source — and then builds one from scratch.
