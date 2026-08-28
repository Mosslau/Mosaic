# ⚙️ LLVM 后端文档

> LLVM 后端：如何把前端生成的 LLVM IR 变成原生二进制，以及我们生成的 IR 长什么样。
> 前端设计见 [架构](./架构.md)，语言规范见 [语言规范](./语言规范.md)。

## 1. 为什么用 LLVM

机器码生成（指令选择、寄存器分配、指令调度、优化）是编译器里最庞大、
最成熟的部分——**rustc 和 clang 都选择复用 LLVM 而非重写**。我们同样如此：

```text
前端（我们写）           后端（LLVM）
lexer → parser → typecheck → LLVM IR → clang 驱动 → 汇编 → 链接 → 原生二进制
```

分工：**前端体现语言设计，后端复用成熟基础设施**。这也意味着——
前端的产物（LLVM IR）是标准格式，任何支持 LLVM 的工具链都能消费。

## 2. 后端管线（compiler 如何驱动 LLVM）

```text
tenet build hello.tenet
   │  compiler/src/main.rs
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

## 3. 我们生成的 IR 长什么样（hello.tenet 实测）

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

## 4. IR 核心概念（结合我们的实际输出）

| 概念 | 说明 | 我们的用法 |
|------|------|-----------|
| **类型** | `i64`/`double`/`i1`/`ptr` | int/float/bool/string 一一映射 |
| **SSA + 基本块** | 每个值定值一次；块以终止指令结尾 | 变量走内存模型，指令临时名 `%vN` 天然 SSA |
| **终止指令** | `ret`/`br` 必须是块的最后一条指令 | `terminated` 标志保证（见 [架构](./架构.md) §4） |
| **全局常量** | `private unnamed_addr constant` | 字符串字面量、`true`/`false` 串 |
| **内存模型** | `alloca`/`load`/`store` | 变量、短路结果——免 phi |
| **外部声明** | `declare` | `printf`、运行时库函数 |
| **变参调用** | `call i32 (ptr, ...) @printf` | print 的多种类型参数 |

### 我们刻意避开的东西

- **phi 节点**：汇合点（if/while 合并）不需要——变量都在栈槽里，`load` 即取值
- **手写汇编/机器码**：交给 LLVM，我们只生成可读的 IR 文本

## 5. 类型与指令映射

| Tenet | IR | 示例 |
|-------|-----|------|
| `int` | `i64` | `add i64 %a, %b`、`sdiv`（向零截断）、`srem` |
| `float` | `double` | `fadd double`、`fdiv`；int 侧先 `sitofp i64 %x to double` |
| `bool` | `i1` | `icmp slt`、`fcmp olt`、`xor i1 true`（取反） |
| `string` | `ptr` | 拼接 `call @tenet_concat`、比较 `call @tenet_strcmp + icmp` |
| `let` | `alloca + store` | 使用处 `load` |
| `if/while/break` | `br` 基本块 | 见 [架构](./架构.md) §4 |
| `&&`/`\|\|` | 短路跳转 + alloca | 右侧只在需要时求值 |
| `print` | 拼格式串 + `printf` | `%lld`/`%g`/`%s`/bool 用 `select` 选 true/false 串 |

## 6. 调试与检查工具

```bash
cd tenet/compiler

cargo run -- ir examples/fib.tenet            # 只看前端产物（IR）
cargo run -- ir examples/fib.tenet > /tmp/f.ll
llc /tmp/f.ll -o /tmp/f.s                    # 看汇编（LLVM 后端单独跑）
clang -S -O2 /tmp/f.ll -o /tmp/f.opt.s       # 看优化后的汇编
```

对照三份文件（IR → 汇编 → 优化汇编），能直观看到 LLVM 后端如何把
我们的 IR 变成真实机器码。

## 7. 兼容性注记（本机实测）

- **gep 语法**：本机 Homebrew LLVM 21 的 IR 解析器对
  `getelementptr inbounds (聚合类型, ...)` 报 `expected type`，
  故字符串取址使用 `getelementptr [{N} x i8], ptr @.str.N, i64 0, i64 0`
  （不带 `inbounds`/括号，语义等价）
- **target triple**：clang 链接时会提示
  `overriding the module target triple`——无害警告（IR 未写死平台，
  clang 按本机默认平台编译，反而更可移植）

## 8. 演进方向（LLVM 侧）

| 特性 | LLVM 表达 |
|------|-----------|
| `struct` | `%Point = type { i64, i64 }` + `getelementptr` 字段访问 |
| `array<T>` | 堆分配（`malloc`）+ 长度前缀结构 |
| `Option`/`Result` | 标签联合 `{ i1 tag, ...payload }` + 分支 |
| `match` | 对 tag `switch`/`br` |
| 优化 | `clang -O2` 透传；`opt` 跑 pass 后 `llc` |
| 自举 | 前端用 Tenet 重写，后端继续复用 LLVM（与 rustc 完全相同） |
