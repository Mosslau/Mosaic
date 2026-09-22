# tenet/compiler-rs —— Tenet 编译器（Rust 实现，clang 驱动）

> Tenet 语言的 Rust 编译器前端。管线：`.tenet → 词法 → 语法 → 类型 → LLVM IR 文本 → clang 驱动 → 原生二进制`。
> 这是 Tenet 三套实现中的第一套，后端采用 **clang 驱动**方式（生成 `.ll` 文本交给 clang）。

## 定位

| | |
|---|---|
| 语言 | Rust（纯标准库，零依赖） |
| 后端方式 | **clang 驱动**：生成 LLVM IR 文本（.ll）→ clang 子进程汇编 + 链接 |
| 产出 | 原生可执行二进制（Mach-O / ELF） |
| 特点 | `.ll` 文本可读可调试（`tenet ir` 即文档）；编译秒级；无 LLVM 开发库依赖 |
| 测试 | 41 个单元测试 |

## 管线

```text
hello.tenet
   │  前端（自己写，Rust）
   ├─▶ lexer.rs      词法分析：字符 → Token 流
   ├─▶ parser.rs     语法分析：Token → AST（递归下降 + 优先级爬升）
   ├─▶ codegen.rs    类型推断 + LLVM IR 文本生成
   │  后端（复用 clang——它是"打包好的 LLVM 后端"）
   ├─▶ clang out.ll runtime.c -o hello
   └─▶ hello         原生二进制，直接运行
```

与 rustc 架构同构：前端自写、产物是 LLVM IR、后端复用 LLVM——区别只是
"把 LLVM 当外部供应商（clang 驱动）"而不是"请进门当员工（链接库）"。

## 目录结构

```
compiler-rs/
├── Cargo.toml
├── src/
│   ├── error.rs     # 统一错误（[行:列] 定位）
│   ├── token.rs     # 词法单元
│   ├── lexer.rs     # 词法分析（最长匹配 / i64 范围 / 转义）
│   ├── ast.rs       # 抽象语法树
│   ├── parser.rs    # 语法分析（递归下降 + Pratt 优先级）
│   ├── codegen.rs   # 类型推断 + LLVM IR 文本生成（含测试）
│   ├── lib.rs       # 库入口（compile_to_ir）
│   └── main.rs      # CLI + clang 驱动 + 内嵌 runtime.c
├── examples/        # hello / fib / fizzbuzz
└── (target/ 构建产物，已 gitignore)
```

## 构建与使用

```bash
cd tenet/compiler-rs

cargo test                                   # 41 个单元测试
cargo run -- build examples/hello.tenet -o hello && ./hello   # 编译为二进制并运行
cargo run -- run examples/fib.tenet          # 编译 + 运行一步到位
cargo run -- ir examples/hello.tenet         # 只看 LLVM IR（调试）
```

## 支持的语言特性（核心子集）

| 类别 | 内容 |
|---|---|
| 类型 | `int` / `float` / `bool` / `string` |
| 变量 | `let`（类型标注可选，静态推断）、赋值（值语义） |
| 函数 | `fn f(a: int) -> int`、递归 |
| 控制流 | `if/else if/else`、`while`（唯一循环）、`break`、`return` |
| 运算符 | 算术（向零截断整除/取模）、比较、`&&`/`\|\|` 短路、一元 `-`/`!` |
| 字符串 | 拼接、比较（经 runtime.c：tenet_concat / tenet_strcmp） |
| 内建 | `print(...)`（任意类型，编译期拼 printf 格式串） |
| 注释 | `//` 与 `/* */` |

## 设计要点

1. **IR 文本化**：codegen 输出可读的 `.ll` 文本——`tenet ir` 直接看产物，教学即文档
2. **内存模型**：变量 = `alloca` + `load`/`store` 栈槽，汇合点不需要 phi 节点
3. **基本块控制流**：`if`/`while`/`break`/短路全部翻译为 `br` 跳转；
   `terminated` 标志保证每个块恰好一个终止指令（ret/br）
4. **print**：编译期按参数静态类型拼接 `printf` 格式串（`%lld`/`%g`/`%s`，bool 用 select）
5. **运行时**：字符串拼接/比较走内嵌 `runtime.c`（链接时与产物一起编译）
6. **兼容性**：本机 LLVM 21 的 IR 解析器对 `getelementptr inbounds (聚合类型)` 有兼容问题，
   取址使用不带 `inbounds`/括号的形式（语义等价）

## 测试

```bash
cargo test
```

词法（字面量/运算符/转义/位置/错误）、语法（let/优先级/函数/else-if 链/错误）、
代码生成（IR 模式断言：alloca、递归调用、短路、混合提升、错误路径）。

## 已知限制与演进

- 只支持核心子集（标量 + 函数 + 控制流）；`struct`/`array`/`Option`/`Result`/`match` 设计已定待实现
- 除法/取模零除是 UB（与 C 一致）
- 未开启 `-O2` 优化（可透传 clang）

## 与另外两套实现的关系

| | compiler-rs | compiler-cpp | compiler-arm64 |
|---|---|---|---|
| 语言 | Rust | C++17 | C++17 |
| 后端 | clang 驱动（.ll 文本） | LLVM 库进程内（rustc 方式） | 手写 AArch64 后端（零 LLVM） |
| 链接 | clang | 系统 `cc` | 系统 `as` + `ld` |
| 测试 | 41 | 74 | 68 |
| 产物 | 原生二进制，输出逐字节一致 | 同左 | 同左 |

三套实现共享同一套语言设计，行为一致——「万语归宗」的验证：同一门语言，三种自主度级别的编译器。
