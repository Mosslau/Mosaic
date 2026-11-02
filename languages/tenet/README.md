# 🏛 Tenet 语言与编译器

> 万语归宗——解剖 C++ / Rust / Python / Java 等主流语言的设计，继承优点、拒绝包袱，
> 合成一门属于自己的语言，并用三种自主度实现编译器。
> **完整文档见 [`Tenet架构设计.md`](./Tenet架构设计.md)**（设计溯源 / 语言规范 / 架构 / LLVM 后端 / 实现）。

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
| 类型系统 | ✅ **已实现**：标量 `int`/`float`/`bool`/`string`；**struct（含嵌套/参数/返回值）**；**固定值数组 `array<T, N>`**；**局部动态数组 `array<T>`（push/深拷贝/drop）**；⏳ 设计已定稿未实现：`Option`/`Result`（见下方「能力边界」） |
| 变量 | `let` 声明，类型标注可选（局部静态推断）；赋值 `=`（值语义） |
| 函数 | `fn f(a: int) -> int`，显式返回类型，递归；调用参数/返回类型严格核对 |
| 控制流 | `if/else`、`while`（唯一循环）、`break`、`return`；条件必须 `bool` |
| 注释 | `//` 行注释、`/* */` 块注释 |
| 内建 | `print(...)`（标量/字符串，多参数；struct/array 需逐字段/元素打印） |
| 执行 | **编译为原生二进制**：`tenet build` → 可执行文件，直接运行 |
| 错误 | 类型错误（混合类型 / 声明·赋值·参数·返回不匹配）在前端报 `[行:列]`，三实现消息一致 |

> ⚠️ **能力边界**：三个编译器目前实现**标量 + 字符串 + 递归 + struct（嵌套/参数/返回值）+ 固定值数组 `array<T, N>`**，定位为纯计算的算法语言。
> struct 字段限 `int`/`float`/`bool` 或其他 struct；支持链式字段、嵌套字面量、参数/返回值（指针 ABI）；支持 `array<struct>` 固定/动态（字段读写、元素赋值、参数/返回值）；支持固定嵌套 `array<array<T,N>,M>` 局部/参数/返回值；不支持动态嵌套 `array<array<T>>`、struct 字段 array、直接 `print(struct)`；
> 固定值数组 `array<T, N>` 在局部/参数/返回值中都是一等公民，长度是类型的一部分，按值拷贝（指针/sret ABI）；动态 `array<T>` 支持局部变量、堆、`push`、运行时 `len`、深拷贝/drop，以及参数/返回值（descriptor/sret，支持字面量/调用表达式）；元素限 `int`/`float`/`bool`；
> `Option` / `Result` / `match` / `?` 已在设计文档定稿但**尚未实现**——
> 不要按速览表把它们当作可用特性。完整边界见 [`Tenet架构设计.md`](./Tenet架构设计.md) §2.7。

## 三个编译器（自主度阶梯）

| 实现 | 前端 | 后端方式 | 测试 |
|---|---|---|---|
| [`compiler-rs/`](./compiler-rs/) | Rust | clang 驱动（.ll 文本） | 94 |
| [`compiler-cpp/`](./compiler-cpp/) | C++17 | LLVM 库进程内（rustc 方式） | 749 |
| [`compiler-arm64/`](./compiler-arm64/) | C++17 | **手写 AArch64 后端（零 LLVM）** | 983 |

三套实现共享同一套语言设计，同一批示例的**程序输出一致**。

## 快速开始

```bash
# Rust 实现（clang 驱动 LLVM 后端）
cd compiler-rs
cargo run -- build examples/hello.tenet -o hello && ./hello

# C++17 实现（进程内调用 LLVM 后端库，rustc 方式）
cd ../compiler-cpp
make
./tenet build examples/hello.tenet -o hello && ./hello

# C++17 手写后端（AArch64 汇编，零 LLVM/clang）
cd ../compiler-arm64
make
./tenet build examples/hello.tenet -o hello && ./hello
```

## 目录结构

```
tenet/
├── README.md          # 本入口：语言速览 + 快速开始 + 导航
├── Tenet架构设计.md           # ★完整文档：设计溯源 / 语言规范 / 架构 / LLVM 后端 / 实现 / 演进
├── compiler-rs/       # 实现 · Rust（clang 驱动）
├── compiler-cpp/      # 实现 · C++17（LLVM 库进程内）
└── compiler-arm64/    # 实现 · C++17（手写 AArch64 后端，零 LLVM）
```

## 与仓库的关系

仓库的三条主线：`studies/`（学 6 门语言）→ `analysis/`（析它们的语言设计）→
`tenet/`（合 + 实现）。本目录即"合成与实现"的落点：
学习与分析的结论在 `Tenet架构设计.md` §1 汇总为设计决策，三个编译器把设计变成可运行的二进制。
