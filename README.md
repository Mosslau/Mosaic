# 🏛 TenetLang

> **万语归宗，探语言之本源**
>
> *All languages converge. We seek the tenet beneath them.*

一个编程语言学习与实践仓库：先系统化学习主流语言，再从零实现一门属于自己的语言。

## 📚 Part 1 · 学习笔记库

6 种主流语言的系统化学习路线：**C、C++、Go、Java、Python、Rust**。

每种语言采用两级结构：

| 层级 | 位置 | 内容 |
|------|------|------|
| Roadmap 总览 | `lang/<语言>/<语言>.md` | 分阶段学习路线：目标 / 学习内容 / 必会概念 / 示例 / 练习 / 阶段验收 / 推荐项目 |
| 阶段详解 | `lang/<语言>/Ph01..Ph05/` | 每个基础阶段的完整展开：来源与演变 / 语法与参数 / 底层原理 / 代码示例 / 总结验收 |

配套资源：

- [`books/books.md`](books/books.md) — 计算机方向书单推荐
- [`library/library.md`](library/library.md) — 全库资料索引

## ⚙️ Part 2 · 语言设计与实现

用 Rust 从零实现一门小型语言 **Tenet**，验证「万语归宗」——把 Part 1 里学到的语言原理亲手搭一遍：

```text
Tenet 源码
   │
   ├─▶ 词法分析 Lexer ──▶ Token 流
   │
   ├─▶ 语法分析 Parser ──▶ AST
   │                          │
   │                          ├─▶ 树遍历解释器 Interpreter ──▶ 直接执行
   │                          │
   │                          └─▶ 代码生成 Codegen ──▶ Go 源码
   │
   └─▶ REPL（交互式执行）
```

- [`tenet-rs/`](tenet-rs/) — Rust 实现：`lexer` / `parser` / `interpreter` / `codegen` / `repl`
- [`tenet-py/`](tenet-py/) — Python 实现：与 Rust 版语义一致、Go 输出逐字节相同
- [`lang/tenet/`](lang/tenet/tenet.md) — Tenet 语言设计文档：从词法、语法到代码生成的完整路线

## Why "TenetLang"?

A tenet is a core principle. Every language — C, Rust, Python — is a
different expression of the same underlying ideas. This project digs
beneath the syntax, back to the source — and then builds one from scratch.
