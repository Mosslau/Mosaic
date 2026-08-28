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
> 建议先学后析；分析结论汇总到 [Tenet](../tenet/Tenet.md)（完整文档）。

## 语言设计分析

| 分析台 | 分析对象 | 主题（notes/） |
|--------|---------|----------------|
| [analyze-rs/](../analyze-rs/) | Rust：内存安全如何成为编译期保证 | 所有权与借用 / 生命周期 / trait 与泛型 / Option·Result / Send·Sync |
| [analyze-cpp/](../analyze-cpp/) | C++：零成本抽象与多范式并存 | RAII / 移动语义 / 多范式 / STL 设计 / constexpr |
| [analyze-py/](../analyze-py/) | Python：开发者体验优先的取舍 | 动态类型 / 数据模型 / 装饰器 / 生成器 / 上下文管理器 |

## Tenet 语言与编译器

| 资料 | 说明 |
|------|------|
| [tenet/Tenet](../tenet/Tenet.md) | **完整文档**：设计溯源 / 语言规范 / 架构 / LLVM 后端 / 实现 / 演进 |
| [tenet/README](../tenet/README.md) | Tenet 语言与编译器入口：速览、快速开始、导航 |
| [tenet/compiler-rs/](../tenet/compiler-rs/) | **实现 · Rust**：clang 驱动 LLVM（.ll 文本 + clang 链接） |
| [tenet/compiler-cpp/](../tenet/compiler-cpp/) | **实现 · C++17**：进程内调用 LLVM 后端库（rustc 方式，IRBuilder + TargetMachine） |
| [tenet/compiler-arm64/](../tenet/compiler-arm64/) | **实现 · C++17 手写后端**：AArch64 汇编（零 LLVM/clang，as/ld 链接） |

> 使用：`cd tenet/compiler && cargo run -- build examples/hello.tenet -o hello && ./hello`

## 书单

- [books/books.md](../books/books.md) — 计算机基础、各语言入门与进阶、Linux、数据库、软件工程
