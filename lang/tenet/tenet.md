# Tenet 语言设计 Roadmap

> 万语归宗——学了 6 种语言之后，亲手实现一门属于自己的语言。
> 用 Rust 从零搭建完整的语言管线：**词法 → 语法 → 语义 → 代码生成**。

## 语言速览

Tenet 是一门小型静态类型语言，刻意保持最小可用：

```tenet
// 变量、类型、print
let name: string = "Tenet";
let year: int = 2026;
print("Hello,", name, year);

// 函数与递归
fn fib(n: int) -> int {
    if (n < 2) { return n; }
    return fib(n - 1) + fib(n - 2);
}

// 循环与控制流
let i: int = 0;
while (i < 10) {
    if (i % 2 == 0) { print(i); }
    i = i + 1;
}
```

| 维度 | 设计 |
|------|------|
| 类型系统 | 4 种标量类型：`int` / `float` / `bool` / `string` |
| 变量 | `let` 声明（类型标注可选，缺省时静态推断） |
| 函数 | `fn` 声明，支持递归、`->` 返回类型 |
| 控制流 | `if / else if / else`、`while`、`break`、`return` |
| 注释 | `//` 行注释、`/* */` 块注释 |
| 后端 | ① 树遍历解释器 ② 源码到源码的 Go 代码生成 |

## 两种实现、两套执行方式

同一门语言，两种宿主实现，语义完全一致，Go 输出逐字节相同：

```bash
# Rust 实现（tenet-rs/）
cd tenet-rs
cargo run -- run examples/fib.tenet      # 解释执行
cargo run -- repl                         # 交互式 REPL
cargo run -- codegen examples/fib.tenet  # 生成 Go 源码（stdout）

# Python 实现（tenet-py/）
cd tenet-py
python3 -m tenet run examples/fib.tenet
python3 -m tenet repl
python3 -m tenet codegen examples/fib.tenet
```

## 阶段路线

> 每个阶段与 `tenet-rs/` 中的真实源码一一对应，学习时边读文档边读代码。

### 1. 词法分析阶段

> 📖 [Ph01-lexer/01-lexer.md](./Ph01-lexer/01-lexer.md) · 源码 [`tenet-rs/src/lexer.rs`](../../tenet-rs/src/lexer.rs)

把源码字符串切成 Token 流：字面量、关键字、运算符、注释与空白。

- **目标**：理解「字符 → 词法单元」的映射，能写出带行列号的 Tokenizer
- **必会概念**：最长匹配、关键字 vs 标识符、转义序列、错误定位（行:列）
- **阶段验收**：能说明 `==` 为什么不能拆成两个 `=`；能说出 `3.14` 和 `3` 的词法区别

### 2. 语法分析与 AST 阶段

> 📖 [Ph02-parser-ast/02-parser-ast.md](./Ph02-parser-ast/02-parser-ast.md) · 源码 [`tenet-rs/src/parser.rs`](../../tenet-rs/src/parser.rs) / [`tenet-rs/src/ast.rs`](../../tenet-rs/src/ast.rs)

把 Token 流变成抽象语法树（AST），验证语法正确性。

- **目标**：掌握递归下降解析与优先级爬升（Pratt Parsing）
- **必会概念**：优先级表、左结合、一元/二元表达式、错误恢复、`else if` 链
- **阶段验收**：能画出 `1 + 2 * 3` 的 AST；能解释 `-x * y` 为什么是 `(-x) * y`

### 3. 解释器与值系统阶段

> 📖 [Ph03-interpreter/03-interpreter.md](./Ph03-interpreter/03-interpreter.md) · 源码 [`tenet-rs/src/interpreter.rs`](../../tenet-rs/src/interpreter.rs) / [`tenet-rs/src/value.rs`](../../tenet-rs/src/value.rs)

直接对 AST 求值：表达式递归求值，语句递归执行。

- **目标**：理解「树遍历求值」这一解释器核心模型
- **必会概念**：短路求值、运行时类型检查、`return`/`break` 的控制流信号传播
- **阶段验收**：能解释 `true || (1 / 0 == 1)` 为什么不报除零错误

### 4. 作用域与函数阶段

> 📖 [Ph04-scope-func/04-scope-func.md](./Ph04-scope-func/04-scope-func.md) · 源码 [`tenet-rs/src/env.rs`](../../tenet-rs/src/env.rs)

块作用域、词法作用域链、函数调用与递归。

- **目标**：实现变量遮蔽、赋值查找、参数传递与递归调用栈
- **必会概念**：环境（Environment）与父指针、遮蔽（Shadowing）、调用帧
- **阶段验收**：能解释内层 `let x` 为何不影响外层 `x`；能说明递归为什么能工作

### 5. 代码生成阶段

> 📖 [Ph05-codegen/05-codegen.md](./Ph05-codegen/05-codegen.md) · 源码 [`tenet-rs/src/codegen.rs`](../../tenet-rs/src/codegen.rs)

把 AST 翻译成 Go 源码——源码到源码的编译器。

- **目标**：理解「语义相同、语法不同」的代码生成过程
- **必会概念**：类型映射、静态类型推断、`while` → `for` 的语法翻译、字符串转义
- **阶段验收**：能说明 `7 / 2.0` 为什么必须保留小数点；生成的 Go 代码可被 `go run` 直接执行

## 与仓库里 6 种语言的关系

| 参考对象 | Tenet 学到了什么 |
|---------|-----------------|
| C | 语法风格（`{}`、`;`、运算符优先级）、静态类型思想 |
| Go | 代码生成目标语言、`:=` 式类型推断、`for` 即唯一循环 |
| Rust | 实现语言：`enum` 表达 AST、`Result` 处理错误、所有权管理环境 |
| Python | 动态求值模型（树遍历解释器）的思想原型 |
| Java / C++ | 词法作用域、函数调用栈等语义的对照 |

## 后续演进方向

- **闭包**：函数作为一等值，捕获定义时环境（需要在类型系统中加入函数类型）
- **复合类型**：数组 / 结构体，把类型系统从标量扩展到容器
- **字节码 VM**：AST 编译为字节码 + 虚拟机执行，性能提升一个数量级
- **静态类型检查器**：把解释器里的运行时检查前移到编译期
- **更完善的标准库**：字符串处理、文件 IO、集合操作
