# Tenet 语言与编译器（完整文档）

> 万语归宗——分析 C++ / Rust / Python 的设计，继承优点、拒绝包袱，
> 合成一门属于自己的语言，并用三种自主度实现编译器。
> 本文档是 Tenet 的**唯一完整文档**：设计溯源、语言规范、架构、LLVM 后端、实现。
> 入口与快速开始见 [README.md](./README.md)。

## 目录

1. [设计溯源](#1-设计溯源)：为什么这么设计
2. [语言规范](#2-语言规范)：语言是什么（文法/类型/语义）
3. [编译器架构](#3-编译器架构)：编译器怎么组织
4. [LLVM 后端](#4-llvm-后端)：IR 如何变成二进制
5. [实现](#5-实现)：三个编译器怎么写
6. [演进方向](#6-演进方向)

---

## 1. 设计溯源

### 1.1 设计总原则

**少即是多，一种惯用法。** 从 Go 学到"克制"，从 C++ 学到"多范式的代价"，
从 Rust 学到"把错误提前到最早阶段"，从 Python 学到"开发者体验优先"。

### 1.2 三语言吸收矩阵（核心设计决策）

C++ / Rust / Python 的核心主张互相矛盾，Tenet 的每个设计点都是一次**调和**：

| 设计点 | C++ 的主张 | Rust 的主张 | Python 的主张 | Tenet 的调和 |
|---|---|---|---|---|
| 类型 | 静态 | 静态（更严格） | 动态 | **静态 + 局部推断**；灵活只保留"print 接受任意类型" |
| 错误 | 异常 | Result + `?` | 异常 | **Result + `?`**（显式错误路径，吸收 Rust） |
| 抽象 | 继承 + 模板 | trait + 泛型 | 鸭子类型 | **struct 组合**（无继承） |
| 内存 | RAII + 智能指针 | 所有权 + 借用 | 引用计数 + GC | **自动管理**：值语义 + 引用计数 |
| 范式 | 多范式并存 | 单一惯用法 | 动态灵活 | **一种惯用法** |
| 体验 | 复杂 | 严格 | 极佳 | **REPL + 可读性 + 友好报错** |
| 性能 | 极致 | 极致 | 差 | **值语义 + 零隐式开销原则** |

**一句话**：语法骨骼像 C 家族，安全与抽象学 Rust，开发体验学 Python，资源哲学学 C++ 的 RAII。

### 1.3 特性溯源

| Tenet 特性 | 来源语言 | 借鉴点 | 取舍说明 |
|---|---|---|---|
| `{}` + `;` 块语法 | C / C++ / Go / Java | 块结构 | 最通用形态，心智负担最低 |
| 唯一循环 `while` | Go | "一种循环"哲学 | Go 只有 `for`；Tenet 取 `while` 形态 |
| `let` + 类型推断 | Rust × Go × Python | `let` 声明 + `:=`/Python 推断 | 标注可省，推断规则与语义一致 |
| `fn f(a: int) -> int` | Rust | 显式返回类型 | 读签名即知契约 |
| 标量类型 | C | 最小类型集 | 先标量后复合，逐步扩展 |
| `struct` + 字段 `.` | C / Rust | 组合优先 | 无继承 |
| `array<T>` + `[]` + `len` | C / Go | 复合容器 | 吸收 Go slice 思想 |
| `Option<T>` / `Result<T,E>` / `?` | Rust | 显式空值与错误 | 消灭 null；错误是值不是意外 |
| `match` + 模式 + `_` | Rust | 穷尽性分支 | 编译器强迫覆盖全部分支 |
| `continue` | C 家族 | 循环控制补全 | `while` + `break`/`continue` 完整 |
| 静态类型 + 解释/编译执行 | C/Go × Python | 两种执行模型折中 | 类型静态，迭代体验动态 |
| 无类无继承 | Go / Rust | 组合优先 | 继承的多态陷阱直接不做 |
| `print` 内建 | Python | 简单输出 | print 接受任意类型（鸭子精神） |
| 短路 `&&`/`\|\|` | Python 等 | 惰性求值最小形态 | 右侧只在需要时求值 |
| 块作用域 + 遮蔽 | C 家族 | 词法作用域 | `{}` 新建作用域 |
| 错误带 `[行:列]` | Rust 错误文化 | 错误是值不是意外 | 全链路可定位 |
| 自包含直接编译运行 | 反 Go 依赖 | 编译器即执行器 | 产物不依赖外部工具链 |
| 代码生成到 LLVM | Go / rustc | 目标即"可运行的汇编" | 前端自写 + LLVM 后端 |

### 1.4 拒绝清单

| 拒绝的特性 | 来源 | 拒绝理由 |
|---|---|---|
| 继承 / 类层次 | C++ / Java | 菱形继承、脆弱基类 |
| 异常 try/catch | C++ / Java / Python | 隐式控制流（用 Result 替代） |
| 闭包 / 函数一等值 | Python / Rust | 需要函数类型与捕获环境 |
| 运算符重载 | C++ / Python | 可读性灾难 |
| 泛型 | Java / C++ / Rust | 复杂度远超当前收益（演进最后加） |
| 移动语义 | C++ | 标量 + 值语义，问题不存在 |
| 借用检查 / 生命周期 | Rust | 无指针 + 引用计数绕开 |
| 完全动态类型 | Python | 类型错误拖到运行时 |
| 模板元编程 / 宏 | C++ | 教学语言不需要编译期计算 |
| 多范式并存 | C++ | 一种惯用法 |
| 生成器 / yield | Python | 无大数据场景 |
| trait / 方法 | Rust | struct 先落地，行为抽象放演进 |

---

## 2. 语言规范

### 2.1 设计定位

| 维度 | 定位 |
|------|------|
| 类型 | 静态类型 + 局部类型推断（let 可省标注） |
| 内存 | 自动管理：值语义 + 引用计数（无指针、无手动释放） |
| 抽象 | 组合优先：struct + 顶层函数（无继承） |
| 错误 | 显式：`Result<T, E>` + `?` 传播（无异常） |
| 空值 | 显式：`Option<T>`（无 null） |
| 范式 | 一种惯用法：语句 + 表达式 + 函数 |

### 2.2 词法

```text
字面量  INT / FLOAT（`3.` 合法，Go 风格）/ STRING（\n \t \" \\ 转义）/ BOOL
关键字  let fn struct if else while match break continue return
        true false None Some Ok Err
        int float bool string array Option Result
符号    ( ) { } [ ] , : ; -> . = == != < <= > >= + - * / % && || ! ?
```

### 2.3 完整文法（EBNF）

```text
program         := stmt*
stmt            := let_stmt ';' | fn_decl | struct_decl | if_stmt | while_stmt
                 | match_stmt | return_stmt ';' | break_stmt ';' | continue_stmt ';'
                 | expr_stmt ';' | block
let_stmt        := 'let' IDENT (':' type)? '=' expr
fn_decl         := 'fn' IDENT '(' param_list? ')' ('->' type)? block
struct_decl     := 'struct' IDENT '{' field* '}'
if_stmt         := 'if' '(' expr ')' block ('else' (if_stmt | block))?
while_stmt      := 'while' '(' expr ')' block
match_stmt      := 'match' expr '{' match_arm+ '}'
match_arm       := pattern '=>' (expr ';' | block)
return_stmt     := 'return' expr?
type            := 'int' | 'float' | 'bool' | 'string'
                 | 'array' '<' type '>' | 'Option' '<' type '>' | 'Result' '<' type ',' type '>'
                 | IDENT                 (* struct 类型名 *)
expr            := assignment
assignment      := logic_or ('=' assignment)?
logic_or        := logic_and ('||' logic_and)*
logic_and       := equality ('&&' equality)*
equality        := comparison (('==' | '!=') comparison)*
comparison      := term (('<' | '<=' | '>' | '>=') term)*
term            := factor (('+' | '-') factor)*
factor          := unary (('*' | '/' | '%') unary)*
unary           := ('-' | '!') unary | postfix
postfix         := primary ('.' IDENT | '[' expr ']' | '?' | '(' arg_list? ')')*
primary         := INT | FLOAT | STRING | 'true' | 'false'
                 | 'None' | 'Some' '(' expr ')' | 'Ok' '(' expr ')' | 'Err' '(' expr ')'
                 | '[' arg_list? ']' | IDENT '{' field_init_list? '}' | IDENT | '(' expr ')'
pattern         := literal | 'None' | 'Some' '(' pattern ')' | 'Ok' '(' pattern ')'
                 | 'Err' '(' pattern ')' | IDENT | '_'
```

### 2.4 运算符优先级（低 → 高）

```text
=              赋值（右结合）
|| &&          逻辑（短路）
== !=          相等
< <= > >=      比较
+ -            加减
* / %          乘除模
- !            一元
. [ ] ( ) ?    成员访问 / 索引 / 调用 / 错误传播（后缀，最紧）
```

### 2.5 类型系统

```text
标量  int | float | bool | string
复合  array<T>（动态数组）| struct 名（具名字段）
可选  Option<T> = None | Some(T)         无 null
错误  Result<T, E> = Ok(T) | Err(E)      E 默认 string
```

推断规则：字面量 → 标量；`+` 全 string → string / 有 float → float / 全 int → int；
`- * /` 有 float → float；`%` 仅 int；比较与 `&&`/`||` → bool；调用 → 返回类型。

静态检查（类型检查器阶段）：变量先声明后使用、运算数类型匹配、
条件必须 bool、`match` 穷尽（Option 必须含 None 分支）、函数参数/返回类型核对。

### 2.6 求值语义要点

| 规则 | 语义 |
|------|------|
| 值语义 | struct/array 赋值与传参按值拷贝；无指针 → 无别名修改、无悬垂 |
| 整除 | int/int **向零截断**（`-7/2 == -3`） |
| 短路 | `&&`/`\|\|` 右侧只在需要时求值（`true \|\| (1/0==1)` 不报错） |
| 作用域 | 块 `{}` 新建作用域；内层 `let` 遮蔽外层；赋值沿链找外层 |
| `?` | `Ok(v)` → `v`；`Err(e)` → 当前函数立即返回 `Err(e)` |
| match | 自上而下第一个命中；穷尽性由类型检查器保证 |
| 错误报告 | 全链路 `[行:列]`，错误即值（非异常） |

---

## 3. 编译器架构

### 3.1 总体架构：前端自写 + 后端复用

与 **clang / rustc 完全相同**的架构——前端由我们实现，后端复用 LLVM
（或完全自写，见三实现）：

```text
hello.tenet
   ├─▶ 前端（自己写）  词法 → 语法 → 类型检查 → LLVM IR
   ├─▶ 后端           复用 LLVM（clang 驱动 / 进程内库）或手写（arm64）
   └─▶ hello          原生二进制（Mach-O / ELF），直接运行
```

### 3.2 模块划分（以 compiler-rs 为例，三实现同构）

| 模块 | 职责 |
|------|------|
| `error` | 统一错误类型，全链路 `[行:列]` 定位 |
| `token` / `lexer` | 词法分析（最长匹配、i64 范围、转义序列） |
| `ast` | 抽象语法树 |
| `parser` | 语法分析（递归下降 + 优先级爬升） |
| `codegen` / `backend` | 类型推断 + 代码生成（LLVM IR 或 arm64 汇编） |
| `main` | CLI（build / run / ir·asm）+ 后端驱动 |

### 3.3 三种后端集成方式（自主度阶梯）

| | compiler-rs | compiler-cpp | compiler-arm64 |
|---|---|---|---|
| 前端 | Rust | C++17 | C++17 |
| IR 构建 | 生成 `.ll` 文本 | LLVM C++ API（IRBuilder 内存） | AST 直出 arm64 汇编 |
| IR → 机器码 | clang 驱动（外部进程） | LLVM 后端库（进程内） | **自己写**（指令选择/寄存器/栈帧/调用约定） |
| 链接 | clang | 系统 `cc` | 系统 `as` + `ld` |
| LLVM/clang | 有（clang） | 有（LLVM 库） | **零** |
| 测试 | 22 | 56 | 50 |

三套实现共享同一套语言设计，编译产物**输出逐字节一致**——「万语归宗」的验证：
同一门语言，三种自主度级别的编译器。

---

## 4. LLVM 后端

### 4.1 为什么用 LLVM

机器码生成（指令选择、寄存器分配、优化）是编译器里最庞大最成熟的部分——
**rustc 和 clang 都选择复用 LLVM 而非重写**。前端体现语言设计，后端复用成熟基础设施。

### 4.2 复用 LLVM 的两种方式（compiler-rs 与 compiler-cpp）

```text
链接 LLVM 库（rustc 方式）     外部驱动（clang 方式）
进程内调用 LLVM 后端            clang 进程调用 LLVM 后端
        ↓                               ↓
     同一个 LLVM 后端（指令选择/寄存器分配/优化）
```

**clang 本身就是"把 LLVM 库链接进去的驱动壳"**。区别只是合同形式：
rustc 把 LLVM"请进门当员工"（进程内库，compiler-cpp 同样如此），
clang 方式"当外部供应商"（compiler-rs）。

| 维度 | 链接 LLVM 库 | clang 驱动 |
|------|-------------|-----------|
| 依赖 | LLVM 开发库（头文件 + libLLVM） | 只要 clang 可执行文件 |
| IR 生成 | C++ API 内存构建 | `.ll` 文本（可读可调试） |
| 集成 | 进程内函数调用 | 子进程 + 文件 |
| 版本兼容 | C++ API 每年大变 | IR 文本格式稳定 |
| 能力上限 | JIT / LTO / 自定义 pass / 常量折叠 | 受限于外部驱动 |

rustc 走链接库路线是因为需要深度控制（LTO、增量编译、codegen 并行、JIT、自定义 pass）
——产品化阶段的工程投入，不是架构必需。compiler-cpp 证明了切换到链接库只需
重写后端集成，前端一行不改。

### 4.3 从 IR 到二进制：LLVM 内部发生了什么

对 LLVM 系两个实现成立（compiler-arm64 不走 LLVM，自己完成指令选择与寄存器分配）：

```text
LLVM IR
  ① 验证 verifyModule
  ② 优化 passes（常量折叠/死代码消除/内联/向量化）——compiler-cpp 实测 7/2.0 折叠成 3.5
  ③ 指令选择 SelectionDAG / GlobalISel（IR → AArch64 add 等）
  ④ 寄存器分配（虚拟 → 物理 x0-x30 / d0-d31）
  ⑤ 指令调度与布局
  ⑥ MC 汇编层 → 对象文件 .o
  ⑦ 链接器（解析符号、重定位）→ 可执行二进制
```

观察每一层：

```bash
tenet ir examples/fib.tenet        # ① 之前：前端产物（IR）
llc fib.ll -o fib.s                # ③④⑤：汇编（指令选择+寄存器分配后）
clang -S -O2 fib.ll                # ②：优化后的汇编
file fib / nm fib | grep tenet_    # 产物格式 / 链接进来的符号
```

---

## 5. 实现

### 5.1 三个编译器的实现要点

**compiler-rs（Rust，clang 驱动）**
- IR 文本化：`tenet ir` 直接看产物，教学即文档
- 变量 = alloca + load/store 内存模型（免 phi）；控制流 = 基本块 + br
- `terminated` 标志保证每块恰好一个终止指令
- print 编译期拼 printf 格式串；字符串经内嵌 runtime.c
- 兼容：LLVM 21 解析器对 `getelementptr inbounds (聚合类型)` 有兼容问题，
  取址用不带 `inbounds`/括号的形式

**compiler-cpp（C++17，LLVM 库进程内）**
- IRBuilder 内存构建 IR；短路用 CreatePHI（进程内 API 最简洁）
- **LLVMContext 生命周期**（头号坑）：Module 持有 Context 引用，二者必须随
  `CompiledModule{ctx, mod}` 一起转移，否则悬空段错误
- 后端：InitializeAllTargets → TargetMachine → legacy::PassManager → .o → cc 链接
- LLVM 21 API 差异：Triple/Host 在 TargetParser、verifyModule 签名、
  setTargetTriple 收 Triple、getOpcode 返回 unsigned
- 常量折叠自动生效（进程内库的天然优化）

**compiler-arm64（C++17，手写 AArch64 后端，零 LLVM）**
- 栈式表达式求值：`stp reg, xzr, [sp, #-16]!` 压栈，无需寄存器活跃度分析
- **Apple Silicon：sp 恒 16 字节对齐**（头号坑）：8 字节 push 触发 EXC_ARM_SP_ALIGN，
  push/pop 一律 16 字节单位（浮点占位 d31）
- 调用约定：用户函数 AAPCS（x0-x7/d0-d7）；print 走 Apple 变参约定
  （fmt 在 x0，变参压栈，实测与 clang 一致）
- 字符串经 libc（strlen/malloc/memcpy/strcmp），内嵌 arm64 运行时
- Apple 寻址：`adrp/add @PAGE/@PAGEOFF`；常量放 __TEXT 段（浮点 .align 3）
- 函数前 `.globl _name`（否则 ld 找不到入口）

### 5.2 测试策略

| 实现 | 数量 | 断言方式 |
|---|---|---|
| compiler-rs | 22 | 词法/语法文本 + IR 模式 |
| compiler-cpp | 56 | 词法/语法文本 + **LLVM Module 结构断言** |
| compiler-arm64 | 50 | 词法/语法文本 + **汇编模式断言** |

### 5.3 如何扩展一个特性（以 `continue` 为例，三步走）

1. **词法**：token 加关键字，lexer 关键字表加映射
2. **语法**：ast 加 `Stmt::Continue`，parser 的 `parse_stmt` 加分支
3. **代码生成**：backend/codegen 加分支——跳回循环条件标签
   （需要一个"循环条件标签"栈，与现有 break 目标栈对称）

每个新特性配：单元测试 + 端到端示例（编译运行验证）。

---

## 6. 演进方向

```text
struct / array<T>    ← C / Rust（数据建模；arm64 后端：栈布局 + 索引寻址）
Option / Result / match / ?  ← Rust（标签联合 + 分支）
优化 -O2             ← LLVM opt / peephole（手写后端）
trait / 方法          ← Rust（行为抽象，仍无继承）
泛型                 ← Java / C++ / Rust（最后再加）
模块 / 多文件         ← Go / Java（分离编译 + 链接）
const 编译期常量      ← C / C++ constexpr
自举                 ← clang / rustc（用 Tenet 写 Tenet 编译器）
```
