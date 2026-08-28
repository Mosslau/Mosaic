# ⚙️ LLVM 后端文档

> LLVM 后端：如何把前端生成的 LLVM IR 变成原生二进制，以及我们生成的 IR 长什么样。
> 前端设计见 [Tenet架构](./Tenet架构.md)，语言规范见 [Tenet语言规范](./Tenet语言规范.md)。

## 1. 为什么用 LLVM

机器码生成（指令选择、寄存器分配、指令调度、优化）是编译器里最庞大、
最成熟的部分——**rustc 和 clang 都选择复用 LLVM 而非重写**。我们同样如此：

```text
前端（我们写）           后端（LLVM）
lexer → parser → typecheck → LLVM IR → clang 驱动 → 汇编 → 链接 → 原生二进制
```

分工：**前端体现语言设计，后端复用成熟基础设施**。这也意味着——
前端的产物（LLVM IR）是标准格式，任何支持 LLVM 的工具链都能消费。

## 2. 为什么用 clang 驱动，而不是链接 LLVM 库

### 2.1 两种方式其实是同一套 LLVM 后端

```text
链接 LLVM 库（rustc 方式）     clang 驱动（我们的方式）
rustc 进程内调用 LLVM 后端      clang 进程调用 LLVM 后端
        ↓                              ↓
     同一个 LLVM 后端（指令选择/寄存器分配/优化）
```

**clang 本身就是"把 LLVM 库链接进去的驱动壳"**——我们用 clang，
等于用"打包好的 LLVM 后端"，而不是自己动手链接那份库。

### 2.2 为什么我们选 clang 驱动

| 维度 | 链接 LLVM 库（rustc 方式） | clang 驱动（我们的方式） |
|------|---------------------------|--------------------------|
| 依赖 | 要装 LLVM **开发库**（头文件 + libLLVM） | 只要有 **clang 可执行文件** |
| IR 生成 | 用 LLVM C++ API 在内存里构建 | 写 **.ll 文本**（可读、可调试） |
| 集成 | 进程内函数调用 | 子进程 + 文件 |
| 版本兼容 | LLVM C++ API **每年大变**，要持续维护 | LLVM IR 文本格式**稳定**（有版本保证） |
| 编译/体积 | 链接后二进制几百 MB、编译极慢 | 纯 Rust 前端，秒级编译 |
| 教学价值 | 先学 LLVM API 才能动手 | `tenet ir` 直接看产物，IR 即文档 |

**核心原因：我们现在的重心是前端（语言设计），不是后端工程。**
用文本 IR + clang 驱动，把"机器码生成"这个最庞大最成熟的领域完整外包，
同时保住 IR 的可读性——这正是一个教学型编译器该有的取舍。

### 2.3 rustc 为什么链接库

rustc 需要深度控制：LTO、增量编译、codegen 并行、JIT、自定义 pass……
这些都需要进程内 API。它也有一个团队专门维护 LLVM 版本兼容。
这是**产品化阶段的工程投入，不是架构必需**。

### 2.4 什么时候该切换成链接 LLVM 库

当出现这些需求时再换（也换得起，因为前端产物不变）：

```text
- 需要 JIT（编译即执行，不用落盘）
- 需要自定义 LLVM pass / LTO
- 要省掉子进程 + 文件 IO 的开销（编译性能）
- 自举后期 / 产品化
```

中间还有一条路：继续外部驱动但更"纯后端"——用 `llc`（LLVM 后端独立工具）
代替 clang，把链接交给系统 `ld`。

**一句话**：rustc 是"把 LLVM 请进门当员工"，我们是"把 LLVM 当外部供应商"——
活都是同一批人（LLVM 后端）干的，区别只是合同形式。
现阶段外包更省事、更好教学；哪天需要精细控制，再签正式合同（链接库）也不迟，
**前端一行都不用改**。

### 2.5 两种方式都已实现（实测对照）

本仓库两个编译器前端分别走了两条路，共享同一套语言与前端设计：

| | compiler-rs | compiler-cpp |
|---|---|---|
| 前端 | Rust（lexer/parser/typecheck） | C++17（lexer/parser/typecheck） |
| IR 构建 | 生成 `.ll` 文本 | LLVM C++ API（IRBuilder 内存构建） |
| IR → 机器码 | clang 驱动（外部进程） | **LLVM 后端库（进程内 TargetMachine）** |
| 链接 | clang 驱动 | 系统 `cc` |
| 实测 | ✅ 原生二进制运行正确 | ✅ 原生二进制运行正确，输出一致 |

compiler-cpp 证明了"切换成链接 LLVM 库"的路线：前端产物不变（都是同一套
AST/类型逻辑），后端从外部驱动换成进程内库，编译出的二进制行为一致。


## 3. 后端管线（compiler 如何驱动 LLVM）

```text
tenet build hello.tenet
   │  compiler-rs/src/main.rs
   ├─① 前端生成 IR 文本（.ll）
   ├─② 写入临时文件 + 内嵌运行时库 runtime.c
   ├─③ 执行：clang out.ll runtime.c -o hello
   └─④ hello —— 原生可执行文件
```

| 工具 | 角色 | 我们的用法 |
|------|------|-----------|
| `clang` | 编译器驱动 | 读 .ll → 汇编 → 链接（含运行时库） |
| `llc` | LLVM 后端 | 调试用：IR → 汇编（`llc hello.ll -o hello.s`） |
| `opt` | 优化器 | 演进：跑 LLVM pass |
| `clang -O2` | 优化开关 | 演进：透传优化（当前未开启） |

clang 路径可用环境变量 `TENET_CLANG` 覆盖；默认用 PATH 上的 `clang`。

## 4. 我们生成的 IR 长什么样（hello.tenet 实测）

```llvm
; Tenet 编译器生成（前端自写 → LLVM IR → clang 链接）
declare i32 @printf(ptr, ...)          ; 外部函数声明（变参）
declare ptr @tenet_concat(ptr, ptr)    ; 运行时库：字符串拼接
declare i32 @tenet_strcmp(ptr, ptr)    ; 运行时库：字符串比较

@.str.true  = private unnamed_addr constant [5 x i8] c"true\00"
@.str.false = private unnamed_addr constant [6 x i8] c"false\00"
@.str.0 = private unnamed_addr constant [6 x i8] c"Tenet\00"   ; 字符串字面量全局常量

define i32 @main() {
entry:
  %v1 = getelementptr [6 x i8], ptr @.str.0, i64 0, i64 0   ; 字符串取址
  %v2 = alloca ptr                                           ; let name: string → 栈槽
  store ptr %v1, ptr %v2                                     ; 初始化
  %v3 = alloca i64                                           ; let year: int → 栈槽
  store i64 2026, ptr %v3
  ...
  %v9 = call i32 (ptr, ...) @printf(ptr %v8, ptr %v5, ptr %v6, ptr %v7)  ; print
  ret i32 0
}
```

## 5. IR 核心概念（结合我们的实际输出）

| 概念 | 说明 | 我们的用法 |
|------|------|-----------|
| **类型** | `i64`/`double`/`i1`/`ptr` | int/float/bool/string 一一映射 |
| **SSA + 基本块** | 每个值定值一次；块以终止指令结尾 | 变量走内存模型，指令临时名 `%vN` 天然 SSA |
| **终止指令** | `ret`/`br` 必须是块的最后一条指令 | `terminated` 标志保证（见 [架构](./Tenet架构.md) §4） |
| **全局常量** | `private unnamed_addr constant` | 字符串字面量、`true`/`false` 串 |
| **内存模型** | `alloca`/`load`/`store` | 变量、短路结果——免 phi |
| **外部声明** | `declare` | `printf`、运行时库函数 |
| **变参调用** | `call i32 (ptr, ...) @printf` | print 的多种类型参数 |

### 我们刻意避开的东西

- **phi 节点**：汇合点（if/while 合并）不需要——变量都在栈槽里，`load` 即取值
- **手写汇编/机器码**：交给 LLVM，我们只生成可读的 IR 文本

## 6. 类型与指令映射

| Tenet | IR | 示例 |
|-------|-----|------|
| `int` | `i64` | `add i64 %a, %b`、`sdiv`（向零截断）、`srem` |
| `float` | `double` | `fadd double`、`fdiv`；int 侧先 `sitofp i64 %x to double` |
| `bool` | `i1` | `icmp slt`、`fcmp olt`、`xor i1 true`（取反） |
| `string` | `ptr` | 拼接 `call @tenet_concat`、比较 `call @tenet_strcmp + icmp` |
| `let` | `alloca + store` | 使用处 `load` |
| `if/while/break` | `br` 基本块 | 见 [架构](./Tenet架构.md) §4 |
| `&&`/`\|\|` | 短路跳转 + alloca | 右侧只在需要时求值 |
| `print` | 拼格式串 + `printf` | `%lld`/`%g`/`%s`/bool 用 `select` 选 true/false 串 |

## 7. 调试与检查工具

```bash
cd tenet/compiler

cargo run -- ir examples/fib.tenet            # 只看前端产物（IR）
cargo run -- ir examples/fib.tenet > /tmp/f.ll
llc /tmp/f.ll -o /tmp/f.s                    # 看汇编（LLVM 后端单独跑）
clang -S -O2 /tmp/f.ll -o /tmp/f.opt.s       # 看优化后的汇编
```

对照三份文件（IR → 汇编 → 优化汇编），能直观看到 LLVM 后端如何把
我们的 IR 变成真实机器码。

## 8. 兼容性注记（本机实测）

- **gep 语法**：本机 Homebrew LLVM 21 的 IR 解析器对
  `getelementptr inbounds (聚合类型, ...)` 报 `expected type`，
  故字符串取址使用 `getelementptr [{N} x i8], ptr @.str.N, i64 0, i64 0`
  （不带 `inbounds`/括号，语义等价）
- **target triple**：clang 链接时会提示
  `overriding the module target triple`——无害警告（IR 未写死平台，
  clang 按本机默认平台编译，反而更可移植）

## 9. 演进方向（LLVM 侧）

| 特性 | LLVM 表达 |
|------|-----------|
| `struct` | `%Point = type { i64, i64 }` + `getelementptr` 字段访问 |
| `array<T>` | 堆分配（`malloc`）+ 长度前缀结构 |
| `Option`/`Result` | 标签联合 `{ i1 tag, ...payload }` + 分支 |
| `match` | 对 tag `switch`/`br` |
| 优化 | `clang -O2` 透传；`opt` 跑 pass 后 `llc` |
| 自举 | 前端用 Tenet 重写，后端继续复用 LLVM（与 rustc 完全相同） |
