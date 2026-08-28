# 📚 TenetLang 资料库

全库导航：学习路线、阶段详解、书单与实现参考。

## 语言学习路线

| 语言 | Roadmap 总览 | 阶段详解（Ph01–Ph05） |
|------|-------------|----------------------|
| C | [c.md](../lang-c/c.md) | 基础语法 / 函数与模块 / 数组·字符串·指针 / 内存管理 / 结构体·数据结构 |
| C++ | [cpp.md](../lang-cpp/cpp.md) | 基础语法 / 面向对象 / 内存模型 / STL / 模板 |
| Go | [go.md](../lang-go/go.md) | 基础语法 / 函数与错误 / Slice·Map·Struct / 方法·接口 / 包与工程结构 |
| Java | [java.md](../lang-java/java.md) | 基础语法 / 面向对象 / 常用类 / 集合 / 泛型 |
| Python | [python.md](../lang-python/python.md) | 基础语法 / 数据结构 / 函数与模块 / 面向对象 / 文件与异常 |
| Rust | [rust.md](../lang-rust/rust.md) | 基础语法 / 所有权 / 数据结构 / Option·Result / 模式匹配 |

> 🧭 **两条线的关系**：`lang-*`（语言学习路线）= 讲*怎么学*这门语言；
> `analyze-*`（设计分析）= 讲*为什么*这门语言这么设计（设计解剖）。
> 建议先学后析；分析结论汇总到 [Tenet设计溯源](../tenet/Tenet设计溯源.md)。

## 语言设计分析

| 分析台 | 分析对象 | 主题（notes/） |
|--------|---------|----------------|
| [analyze-rs/](../analyze-rs/) | Rust：内存安全如何成为编译期保证 | 所有权与借用 / 生命周期 / trait 与泛型 / Option·Result / Send·Sync |
| [analyze-cpp/](../analyze-cpp/) | C++：零成本抽象与多范式并存 | RAII / 移动语义 / 多范式 / STL 设计 / constexpr |
| [analyze-py/](../analyze-py/) | Python：开发者体验优先的取舍 | 动态类型 / 数据模型 / 装饰器 / 生成器 / 上下文管理器 |

## Tenet 语言与编译器

| 资料 | 说明 |
|------|------|
| [tenet/设计溯源](../tenet/Tenet设计溯源.md) | **设计 · 溯源**：三语言吸收矩阵、每个特性从哪门语言来、拒绝了什么、演进路线 |
| [tenet/语言规范](../tenet/Tenet语言规范.md) | **设计 · 规范**：正式文法（EBNF）、类型系统与推断、求值语义（唯一事实来源） |
| [tenet/架构](../tenet/Tenet架构.md) | **架构文档**：前端/后端划分、模块职责、LLVM 设计决策 |
| [tenet/LLVM后端](../tenet/LLVM后端.md) | **后端文档**：IR 生成全貌、clang 驱动、指令映射、调试工具 |
| [tenet/实现](../tenet/Tenet实现.md) | **实现文档**：逐模块实现要点、测试策略、如何扩展 |
| [tenet/README](../tenet/README.md) | Tenet 语言与编译器入口：速览、文档导航、演进 |
| [tenet/compiler-rs/](../tenet/compiler-rs/) | **实现 · Rust**：clang 驱动 LLVM（.ll 文本 + clang 链接） |
| [tenet/compiler-cpp/](../tenet/compiler-cpp/) | **实现 · C++17**：进程内调用 LLVM 后端库（rustc 方式，IRBuilder + TargetMachine） |

> 使用：`cd tenet/compiler && cargo run -- build examples/hello.tenet -o hello && ./hello`

## 书单

- [books/books.md](../books/books.md) — 计算机基础、各语言入门与进阶、Linux、数据库、软件工程
