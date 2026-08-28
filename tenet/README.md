# Tenet 语言与编译器

> 万语归宗——分析 C++ / Rust / Python 的设计，继承优点、拒绝包袱，
> 合成一门属于自己的语言，并实现一个 **clang / rustc 式原生编译器**：
> `tenet build hello.tenet` 产出可直接运行的二进制。

## 文档导航

| 文档 | 内容 | 回答的问题 |
|------|------|-----------|
| [设计溯源](./设计溯源.md) | **设计文档 · 溯源**：三语言吸收矩阵、特性来源表、拒绝清单、演进路线 | 为什么这么设计 |
| [语言规范](./语言规范.md) | **设计文档 · 规范**：正式文法（EBNF）、类型系统、求值语义（唯一事实来源） | 语言是什么 |
| [架构](./架构.md) | **架构文档**：前端/后端划分、模块职责、LLVM 设计决策 | 编译器怎么组织 |
| [实现](./实现.md) | **实现文档**：逐模块实现要点、测试策略、如何扩展 | 代码怎么写 |
| [`compiler/`](./compiler/) | **实现代码**：Rust 前端（词法/语法/类型/LLVM IR）+ clang 链接 | 代码在哪 |

## 语言速览

Tenet 是吸收了 C++ / Rust / Python 设计的**静态类型语言**：语法骨骼像 C 家族，
安全与抽象学 Rust，开发体验学 Python，资源哲学学 C++ 的 RAII。

```tenet
// 标量与类型推断
let name: string = "Tenet";
let year = 2026;                 // 推断为 int

// 函数与递归
fn fib(n: int) -> int {
    if (n < 2) { return n; }
    return fib(n - 1) + fib(n - 2);
}

// 循环与控制流（唯一循环 while）
let i: int = 0;
while (i < 10) {
    if (i % 2 == 0) { print(i); }
    i = i + 1;
}
```

| 维度 | 设计 |
|------|------|
| 类型系统 | 标量 `int`/`float`/`bool`/`string`（完整设计含 `array<T>`/`struct`/`Option`/`Result`，见语言规范） |
| 变量 | `let` 声明，类型标注可选（局部静态推断）；赋值 `=`（值语义） |
| 函数 | `fn f(a: int) -> int`，显式返回类型，递归 |
| 控制流 | `if/else`、`while`（唯一循环）、`break`、`return` |
| 注释 | `//` 行注释、`/* */` 块注释 |
| 内建 | `print(...)`（任意类型、任意数量）、`len(x)` |
| 执行 | **编译为原生二进制**：`tenet build` → 可执行文件，直接运行 |

## 实现状态

| 模块 | 位置 | 状态 |
|------|------|------|
| 词法 / 语法 / 类型 / LLVM IR 代码生成 | [`compiler/`](./compiler/) | ✅ 已实现（核心子集） |
| 命令行 | `tenet build` / `tenet run` / `tenet ir` | ✅ 已实现 |
| 示例 | `compiler/examples/`（hello / fib / fizzbuzz） | ✅ 编译为原生二进制运行正确 |
| 复合类型 / Option / Result / match | 设计已定（语言规范），代码生成待扩展 | 演进 |

## 快速开始

```bash
cd compiler
cargo run -- build examples/hello.tenet -o hello && ./hello   # 编译为二进制并运行
cargo run -- run examples/fib.tenet                            # 编译+运行一步到位
cargo test                                                     # 22 个单元测试
```

## 后续演进方向

- **复合类型**：`struct` / `array<T>` 的 LLVM 代码生成（struct → LLVM struct 类型 + gep）
- **Option / Result / match / `?`**：标签联合 + 分支
- **优化**：`-O2` 透传 LLVM 优化（`clang -O2`）
- **类型检查器独立阶段**：把推断与静态检查（match 穷尽性等）独立成 pass
- **模块 / 多文件**：分离编译 + 链接
- **自举**：用 Tenet 写 Tenet 编译器（吸收 clang/rustc 的参考实现模式）

## 与仓库里 6 种语言的关系

| 参考对象 | Tenet 学到了什么 |
|---------|-----------------|
| C | 语法风格（`{}`、`;`、运算符优先级）、静态类型思想 |
| C++ | 值语义、RAII 资源管理思想、性能意识（分析见 tenet-cpp/） |
| Go | `:=` 式类型推断、`for` 即唯一循环、克制的设计哲学 |
| Rust | 组合优先（trait 思想）、`Option`/`Result`、错误带位置、**LLVM 后端的架构**（分析见 tenet-rs/） |
| Python | 类型推断、REPL、`print` 内建、可读性与上手体验（分析见 tenet-py/） |
| Java | 词法作用域、函数调用栈等语义的对照 |
