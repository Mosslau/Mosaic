# 🏗 Tenet 编译器架构

> 架构设计：Tenet 编译器如何组织、各阶段职责、关键设计决策。
> 语言规范见 [语言规范](./Tenet语言规范.md)，实现细节见 [实现](./Tenet实现.md)，
> 代码在 [`compiler/`](./compiler/)。

## 1. 总体架构：前端自写 + LLVM 后端

与 **clang / rustc 完全相同**的架构——编译器分前端与后端，前端由我们实现，
后端复用 LLVM：

```text
hello.tenet
   │
   ├─▶ 前端（compiler/src/，自己写）
   │    ① lexer.rs     词法分析：字符 → Token 流
   │    ② parser.rs    语法分析：Token → AST（递归下降 + 优先级爬升）
   │    ③ codegen.rs   类型推断 + LLVM IR 生成
   │
   ├─▶ 后端（复用 LLVM/clang，详见 [LLVM后端](./LLVM后端.md)）
   │    ④ clang hello.ll runtime.c -o hello
   │
   └─▶ hello（原生二进制，Mach-O / ELF，直接运行）
```

**为什么这样分**：机器码生成（指令选择、寄存器分配、优化）是编译器里最庞大
也最成熟的部分，rustc 和 clang 都选择复用 LLVM 而非重写——我们同样如此。
前端（词法/语法/类型/IR 生成）才是"语言设计"的体现，也是本项目的核心。

## 2. 模块划分（compiler/src/）

| 模块 | 职责 | 关键设计 |
|------|------|---------|
| `error.rs` | 统一错误类型 | 全链路 `[行:列]` 定位 |
| `token.rs` / `lexer.rs` | 词法分析 | 最长匹配、i64 范围检查、转义序列 |
| `ast.rs` | 抽象语法树 | 表达式/语句枚举 + 运算符常量 |
| `parser.rs` | 语法分析 | 递归下降 + 优先级爬升（Pratt） |
| `codegen.rs` | 类型推断 + LLVM IR | 内存模型（见 §3）、基本块控制流（见 §4） |
| `main.rs` | CLI 驱动 | `build` / `run` / `ir` 三个子命令 + clang 链接 |
| 运行时 `runtime.c` | 字符串支持 | 拼接/比较（链接时编入，类似真实编译器 runtime） |

## 3. 变量模型：alloca + load/store（免 phi）

```llvm
%x.addr = alloca i64          ; 变量 = 栈上槽位
store i64 42, ptr %x.addr     ; let 初始化 → store
%t = load i64, ptr %x.addr    ; 使用 → load
```

**为什么用内存模型而非 SSA 直算**：`let`/赋值/块作用域天然映射到
"栈槽 + 读写"，不需要为 if/while 的汇合点计算 phi 节点——
代码生成显著简化，正确性直观。这是老 LLVM 编译器（如 llvmgcc）的经典做法。

## 4. 控制流：一切翻译为基本块跳转

| Tenet | LLVM IR |
|-------|---------|
| `if (c) {A} else {B}` | `br i1 %c, then, else` → A → `br merge` → B → `br merge` → `merge:` |
| `while (c) {B}` | `br cond` → `cond:` 判 `%c` → `br body/exit` → B → `br cond` → `exit:` |
| `break` | `br %exit`（break 目标栈） |
| `a && b` / `a \|\| b` | 短路：`br i1 %a` 决定是否求值 b，结果存 alloca（免 phi） |
| `return v` | `ret i64 %v`（提前返回天然正确） |

**基本块终止跟踪**：`ret`/`br` 后不能再发指令（LLVM 要求终止指令在块尾），
codegen 用 `terminated` 标志保证每个块恰好一个终止指令。

## 5. 类型映射

| Tenet | LLVM |
|-------|------|
| `int` | `i64` |
| `float` | `double` |
| `bool` | `i1` |
| `string` | `ptr`（i8*，指向堆/全局字符串） |

混合数值运算（int × float）：int 侧 `sitofp i64 → double` 后统一浮点运算。
整除/取模用 `sdiv`/`srem`（**向零截断**，与设计语义一致：`-7/2 == -3`）。

## 6. print 与字符串

- **print**：编译期按参数静态类型拼接 `printf` 格式串
  （`int→%lld`、`float→%g`、`string→%s`、`bool→%s`+select true/false），
  生成一次 `printf` 调用
- **字符串字面量**：`private unnamed_addr constant [N x i8]` 全局常量
- **字符串拼接/比较**：调用运行时库 `tenet_concat`/`tenet_strcmp`
  （`runtime.c` 与产物一起编译链接）

## 7. CLI 设计

```text
tenet build <file> [-o <out>]   词法→语法→类型→LLVM IR→clang→原生二进制
tenet run   <file>              编译到临时文件并直接运行（透传退出码）
tenet ir    <file>              只输出 LLVM IR（调试）
```

- 链接驱动：`clang out.ll runtime.c -o out`；`TENET_CLANG` 可覆盖 clang 路径
- 前端零依赖：纯 Rust 标准库；唯一外部依赖是 clang（后端，与 rustc 依赖 LLVM 同理）

## 8. 兼容性注记

本机 Homebrew LLVM 21 的 IR 解析器对
`getelementptr inbounds (聚合类型, ...)` 语法报 `expected type`，
故字符串常量取址使用不带 `inbounds`/括号的形式：
`getelementptr [{N} x i8], ptr @.str.N, i64 0, i64 0`（语义等价）。

## 9. 演进方向

- `struct`/`array<T>`：LLVM struct 类型 + `gep` 字段访问；数组用堆分配 + 长度前缀
- `Option`/`Result`/`match`/`?`：标签联合 + 分支
- 优化：`-O2` 透传（`clang -O2`），消除 alloca 冗余
- 类型检查器独立为 pass（match 穷尽性等）
- 自举：用 Tenet 写前端（lexer/parser/typecheck）
