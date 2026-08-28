# Ph02 · 语法分析与 AST

> 源码对照：[`tenet-rs/src/parser.rs`](../../tenet-rs/src/parser.rs) · [`tenet-rs/src/ast.rs`](../../tenet-rs/src/ast.rs)
> 测试对照：`tenet-rs/src/parser.rs` 末尾的 `#[cfg(test)] mod tests`

## 1. 概述

**语法分析（Parsing）** 把 Token 流组织成**抽象语法树（AST）**。
AST 丢弃了源码的表层细节（括号、分号、空白），只保留**结构**：

```
        "1 + 2 * 3"                          "1 + 2 * 3"
            │ Token 流                             │ Parser
            ▼                                     ▼
   [Int(1)] [Plus] [Int(2)] [Star] [Int(3)]    Binary(Add)
                                                   ├── Int(1)
                                                   └── Binary(Mul)
                                                         ├── Int(2)
                                                         └── Int(3)
```

AST 是所有后端（解释器、代码生成器）的**共同输入**——这就是
「万语归宗」：不同的后端消费同一棵树。

## 2. AST 的设计（见 `ast.rs`）

Tenet 的 AST 用 Rust `enum` 表达，两种节点：

### 2.1 表达式 `Expr`

```rust
enum Expr {
    Int(i64), Float(f64), Str(String), Bool(bool),  // 字面量
    Var(String),                                    // 变量读取
    Assign { name: String, value: Box<Expr> },      // 赋值
    Unary { op: UnaryOp, expr: Box<Expr> },         // -x  !x
    Binary { op: BinaryOp, lhs: Box<Expr>, rhs: Box<Expr> },
    Call { callee: String, args: Vec<Expr> },       // f(1, 2)
}
```

为什么 `lhs`/`rhs` 是 `Box<Expr>`？因为树是递归结构，`Box` 让
每个节点的大小确定（指针大小），否则 `enum` 无法静态确定尺寸。

### 2.2 语句 `Stmt`

```rust
enum Stmt {
    Let { name, ty: Option<Type>, value: Expr },
    Expr(Expr),                                     // 表达式语句
    If { cond, then_branch: Vec<Stmt>, else_branch: Option<Vec<Stmt>> },
    While { cond, body: Vec<Stmt> },
    Return(Option<Expr>),
    Break,
    Block(Vec<Stmt>),                               // 裸块 { ... }
    FnDecl { name, params: Vec<(String, Type)>, ret: Option<Type>, body: Vec<Stmt> },
}
```

注意 `If`/`While`/`Block` 里是 `Vec<Stmt>`（语句序列），
不是单个 `Stmt`——因为块（`{ ... }`）天然是语句的容器。

## 3. 递归下降解析

Tenet 采用**递归下降（Recursive Descent）**：每种语法结构对应
一个函数，函数之间互相调用，调用层级就是语法嵌套层级。

```rust
parse_stmt()   → let / fn / if / while / return / break / 表达式语句
parse_block()  → { parse_stmt()* }
parse_expr()   → 优先级爬升
parse_unary()  → -x 或 !x 或 parse_primary()
parse_primary()→ 字面量 / 变量 / 调用 / (表达式)
```

### 3.1 优先级爬升（Pratt Parsing）

二元运算符按优先级表处理：

```text
||          （最低）
&&
==  !=
<  <=  >  >=
+  -
*  /  %
一元 -  !   （最高）
```

```rust
fn parse_binary(min_prec: u8) -> Expr {
    let mut lhs = parse_unary();
    loop {
        let (op, prec) = 当前运算符的优先级;
        if prec < min_prec { break; }          // 优先级不够，让给外层
        lhs = Binary { op, lhs, rhs: parse_binary(prec + 1) };  // 左结合
    }
}
```

**左结合**的关键：递归调用时传 `prec + 1`，同优先级运算符
会继续被当前层吃掉，形成左结合树：`a - b - c` → `(a - b) - c`。

### 3.2 `else if` 链

Tenet 的 `else if` 没有专门的语法节点——它就是**嵌套的 if 语句**：

```text
if (a) { ... } else if (b) { ... } else { ... }
        │
        ▼
If { cond: a, else: [ If { cond: b, else: [...] } ] }
```

解析器把 `else` 后面的 `if` 当成一个普通语句塞进 else 分支。
这个设计让语法和 AST 都保持最小。

## 4. 语法错误的定位

```text
输入:  let x: int = 1        （缺分号）
输出:  [1:15] 期望 `;`，但遇到 文件末尾

输入:  if x > 0 { }          （if 缺左括号）
输出:  [1:4] 期望 `(`，但遇到 标识符 `x`
```

错误信息统一为「期望 X，但遇到 Y」，并带上当前 Token 的行列。

## 5. 必会概念清单

1. **AST 是后端的公共接口**：解释器和代码生成器只认这棵树
2. **`Box` 打破递归枚举**：让树节点大小确定
3. **递归下降 = 语法结构 ↔ 函数结构**一一对应
4. **优先级爬升**：`min_prec` + `prec + 1` 实现左结合
5. **`else if` 是嵌套 if**：语法最小化的一课

## 6. 练习

- 画出 `-2 * 3 + 4` 的 AST 树形图，再对照 `cargo run -- repl` 输入验证
- 给 Tenet 增加一个 `for (i = 0; i < n; i = i + 1)` 语句，说出要改哪些文件
- 思考：`2 < 3 < 4` 会解析成什么？为什么运行时才报错？

## 7. 阶段验收

- [ ] 能手写 `parse_expr` 的优先级表并解释左结合
- [ ] 能说出 `if` 的 else 分支为什么是 `Option<Vec<Stmt>>`
- [ ] 能给语法错误写一条"期望 X 但遇到 Y"风格的报错测试

## 下一阶段

[Ph03 · 解释器与值系统](../Ph03-interpreter/03-interpreter.md) — 让 AST 真正跑起来。
