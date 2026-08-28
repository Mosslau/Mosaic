# tenet/compiler-cpp —— Tenet 编译器（C++17 实现，LLVM 库进程内）

> Tenet 语言的 C++17 编译器前端。管线：`.tenet → 词法 → 语法 → 类型 → LLVM IR（内存构建）→ LLVM 后端库 → 原生二进制`。
> 这是 Tenet 三套实现中的第二套，后端采用 **rustc 方式**：进程内调用 LLVM 后端库，而不是 clang 驱动。

## 定位

| | |
|---|---|
| 语言 | C++17（纯标准库 + LLVM 开发库） |
| 后端方式 | **LLVM 后端库（进程内）**：IRBuilder 内存构建 IR → TargetMachine 产出机器码（rustc 方式） |
| 产出 | 原生可执行二进制（Mach-O / ELF） |
| 特点 | 进程内完整控制（常量折叠自动生效）；真正的"链接 LLVM 库"路线实证 |
| 测试 | 56 项检查 |

## 管线

```text
hello.tenet
   │  前端（自己写，C++17）
   ├─▶ lexer.hpp      词法分析：字符 → Token 流
   ├─▶ parser.hpp     语法分析：Token → AST（递归下降 + 优先级爬升）
   ├─▶ codegen.hpp    类型推断 + LLVM IR 构建（IRBuilder，内存对象）
   │  后端（LLVM 库，进程内——与 rustc 相同）
   ├─▶ TargetMachine 产出对象文件 .o（指令选择/寄存器分配/机器码）
   ├─▶ 系统 cc 链接 runtime.c
   └─▶ hello          原生二进制，直接运行
```

与 rustc 架构同构：前端自写、产物是 LLVM IR、后端复用 LLVM——区别是
"把 LLVM 请进门当员工"（链接库，进程内调用），而 compiler-rs 是"当外部供应商"
（clang 驱动）。

## 目录结构

```
compiler-cpp/
├── Makefile          # clang++ + llvm-config 自动取头文件/库
├── src/
│   ├── error.hpp     # 统一错误（[行:列] 定位）
│   ├── token.hpp     # 词法单元
│   ├── lexer.hpp     # 词法分析
│   ├── ast.hpp       # 抽象语法树（标签结构体）
│   ├── parser.hpp    # 语法分析
│   ├── codegen.hpp   # 类型推断 + LLVM C++ API 代码生成（含 56 项测试的断言对象）
│   └── main.cpp      # CLI + 进程内后端（TargetMachine）+ 内嵌 runtime.c
├── examples/         # hello / fib / fizzbuzz
└── tests/            # test_main.cpp
```

## 构建与使用

要求：LLVM 开发库（Homebrew：`brew install llvm`，本机 21.1.8）。

```bash
cd tenet/compiler-cpp

make                    # 构建 tenet 与 test_tenet 并跑测试
make test               # 56 项检查
./tenet build examples/hello.tenet -o hello && ./hello   # 编译为二进制并运行
./tenet run examples/fib.tenet          # 编译 + 运行一步到位
./tenet ir examples/hello.tenet         # 打印 LLVM IR（Module::print）
```

`llvm-config` 路径可用 `LLVM_CONFIG` 覆盖（Makefile 默认
`/opt/homebrew/opt/llvm/bin/llvm-config`）。

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

1. **进程内 IR**：`IRBuilder` 在内存里构建 IR（非文本）——`CreateAlloca`/`CreateLoad`/
   `CreateStore`/`CreateCall` 直接生成指令对象
2. **LLVMContext 生命周期**（本实现的头号坑）：`Module` 持有 `LLVMContext&`，
   二者必须与 `CompiledModule{ctx, mod}` 一起转移所有权，否则 context 析构后模块悬空 → 段错误
3. **基本块 + phi**：`if`/`while`/短路用基本块；短路结果用 `CreatePHI`（进程内 API 下最简洁）
4. **常量折叠**：LLVM 自动做编译期求值（`7 / 2.0` 在 IR 阶段就算成 3.5）——进程内库的天然优化
5. **后端**：`InitializeAllTargets` → `TargetMachine` → `legacy::PassManager`
   `addPassesToEmitFile` 产出对象文件 → 系统 `cc` 链接
6. **LLVM 21 API 适配**：`Triple.h`/`Host.h` 移至 `TargetParser/`、`verifyModule` 签名、
   `setTargetTriple` 收 `Triple`、`getOpcode()` 返回 `unsigned`

## 测试

```bash
make test
```

词法/语法用文本断言；代码生成用 **LLVM Module 结构断言**（main 含 alloca/store、
add 含 Add 指令、fib 递归自调用、短路含 phi、混合提升含 sitofp）。

## 已知限制与演进

- 只支持核心子集；`struct`/`array`/`Option`/`Result`/`match` 设计已定待实现
- 未开启 `-O2`（可 `TargetMachine` 配置或 `opt` pass）
- 链接用系统 `cc`（LLVM 完成 IR→机器码，链接与 rustc 一样交给系统链接器）

## 与另外两套实现的关系

| | compiler-rs | compiler-cpp | compiler-arm64 |
|---|---|---|---|
| 语言 | Rust | C++17 | C++17 |
| 后端 | clang 驱动（.ll 文本） | LLVM 库进程内（rustc 方式） | 手写 AArch64 后端（零 LLVM） |
| 链接 | clang | 系统 `cc` | 系统 `as` + `ld` |
| 测试 | 22 | 56 | 50 |
| 产物 | 原生二进制，输出逐字节一致 | 同左 | 同左 |

compiler-cpp 证明了"从 clang 驱动切换到链接 LLVM 库"的路线：前端产物不变，
后端集成方式可换，编译出的二进制行为一致。
