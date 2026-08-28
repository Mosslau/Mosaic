# Ph04 · 作用域与函数

> 源码对照：[`tenet-rs/src/env.rs`](../../tenet-rs/src/env.rs) · [`tenet-rs/src/interpreter.rs`](../../tenet-rs/src/interpreter.rs)
> 测试对照：`tenet-rs/src/interpreter.rs` 的 `block_scoping_shadows` / `recursion_fib` 测试

## 1. 概述

「变量在哪里可见」是语言语义的核心问题。Tenet 采用经典的
**词法作用域（Lexical Scoping）**：变量可见性由源码结构决定，
与运行路径无关。

## 2. 环境（Environment）：作用域链

环境就是**变量名 → 值的映射**，加上一个指向父环境的指针：

```rust
// env.rs 的简化结构
struct Env {
    vars: RefCell<HashMap<String, Value>>,  // 本层的变量
    parent: Option<Rc<Env>>,                // 父作用域
}
```

```
全局环境 (global)
   │ parent: None
   │ vars: { x: 1 }
   │
   ├── 块环境 A { let x = 2 }
   │      └─ parent → 全局
   │
   └── 函数调用环境 { a: 3, b: 4 }
          └─ parent → 全局
```

### 2.1 定义（define）与查找（get）

```rust
fn define(&self, name, value)  // 只写当前层 —— 允许遮蔽
fn get(&self, name)            // 当前层没有 → 沿 parent 向上找
fn assign(&self, name, value)  // 沿链找到「第一个」同名变量并修改
```

- **定义**永远落在当前层 → 内层 `let x` 会**遮蔽**外层 `x`
- **查找 / 赋值**沿链向上 → 内层可以直接修改外层的变量
- 找不到 → 运行时错误 `未定义的变量 x`

## 3. 作用域的创建点

Tenet 中**只有 4 处**会新建作用域：

| 位置 | 代码 | 效果 |
|------|------|------|
| 裸块 `{ ... }` | `Stmt::Block` | 块内 `let` 块外不可见 |
| `if` 分支 | `if (c) { ... }` | 分支内变量不泄漏 |
| `while` 循环体 | `while (c) { ... }` | 每次迭代都是新环境 |
| 函数调用 | `fn f(...) { ... }` | 参数 + 局部变量隔离 |

**顶层不建作用域**：顶层 `let` 直接进入全局环境——
这是 REPL 能跨行记住变量的关键（每行都是"顶层"）。

## 4. 遮蔽（Shadowing）与赋值

```tenet
let x: int = 1;          // 全局 x = 1
{
    let x: int = 2;      // 块内新 x，遮蔽全局 x
    print(x);            // 2
}
print(x);                // 1 —— 块结束，遮蔽消失
```

```tenet
let counter: int = 0;
{
    counter = counter + 10;   // 没有 let！这是赋值，沿链找到全局 counter
}
print(counter);               // 10 —— 全局被修改
```

**区分 `let` 和赋值**：`let` 定义新变量（可能遮蔽），
`=` 赋值修改已有变量。这正是 `Env::define` 与 `Env::assign` 的差别。

## 5. 函数调用与递归

```rust
fn call(callee, args, env) {
    let call_env = Env::child(&self.global);   // 新环境，父=全局
    for (参数, 实参) { call_env.define(参数名, 实参值); }
    let flow = exec_block(&f.body, &call_env); // 执行函数体
    match flow { Flow::Return(v) => v, ... }
}
```

**递归为什么能工作？**

```tenet
fn fib(n: int) -> int {
    if (n < 2) { return n; }
    return fib(n - 1) + fib(n - 2);   // 调用自己
}
```

1. 函数名 `fib` 存放在**全局函数表**（`HashMap<String, Function>`），
   不随调用环境销毁
2. `fib(10)` 调用 → 新建环境 E1，绑定 `n=10` → 执行体遇到 `fib(n-1)`
   → 又在函数表里找到 `fib` → 新建环境 E2，绑定 `n=9` …
3. 每一层调用都有**独立的 `n`**，互不干扰；返回时逐层回收

这就是**调用栈**的模型：每个调用帧（环境）独立存在，
函数表是共享的。Tenet 目前**没有闭包**，函数不捕获调用方的局部
环境，因此调用环境的父指针固定指向全局——这是后续演进的切入点。

## 6. 必会概念清单

1. **作用域 = 环境链**：`define` 写当前层，`get`/`assign` 向上找
2. **遮蔽 vs 赋值**：`let` 新建，`=` 修改，两者语义不同
3. **只有块 / if / while / 函数**会新建作用域
4. **函数表全局共享** → 递归天然成立
5. **每个调用帧独立** → 参数互不干扰

## 7. 练习

- 预测下面的输出，再用 REPL 验证：
  `let x: int = 5; { let x: int = 10; { x = x + 1; print(x); } print(x); } print(x);`
- 思考：如果去掉 `Env::child` 的父指针，函数还能递归吗？
- 实现 `Env` 的一个 `contains(name)` 方法，并说明它的用途

## 8. 阶段验收

- [ ] 能画出三层嵌套作用域的环境链
- [ ] 能解释「内层赋值改外层、内层 let 不改外层」
- [ ] 能说明递归调用为什么不会互相污染参数

## 下一阶段

[Ph05 · 代码生成](../Ph05-codegen/05-codegen.md) — 把同一棵 AST 翻译成 Go。
