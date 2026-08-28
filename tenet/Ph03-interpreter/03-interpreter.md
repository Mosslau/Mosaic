# Ph03 · 解释器与值系统

> 源码对照：[`impl-rs/src/interpreter.rs`](../impl-rs/src/interpreter.rs) · [`impl-rs/src/value.rs`](../impl-rs/src/value.rs)
> 测试对照：`impl-rs/src/interpreter.rs` 末尾的 `#[cfg(test)] mod tests`

## 1. 概述

**树遍历解释器（Tree-walking Interpreter）** 是理解语言语义最直接的模型：
不需要编译，直接对着 AST 递归求值。

```
AST ──► 表达式：递归求值，返回 Value
    └─► 语句：递归执行，产生副作用
```

Tenet 的解释器是**动态求值 + 运行时检查**：类型不匹配不在编译期发现，
而在运行时报错。这与代码生成端（Go，编译期检查）形成互补——
同一门语言，两种执行模型。

## 2. 值系统（见 `value.rs`）

```rust
enum Value {
    Int(i64),       // 对应类型 int
    Float(f64),     // 对应类型 float
    Bool(bool),     // 对应类型 bool
    Str(String),    // 对应类型 string
    Nil,            // 无返回值的函数调用的结果（内部值）
}
```

### 2.1 二元运算规则

```text
+  : int+int→int    float 参与→float    string+string→拼接
- * : 仅数值；任一为 float → float
/  : int/int 整除（向零截断）；任一 float → 浮点除
%  : 仅 int
== != : 全部类型可比较；int 与 float 互通（1 == 1.0 → true）
< <= > >= : 数值或字符串（字典序）
&& || : 仅 bool，且短路求值
```

### 2.2 短路求值

`&&` 和 `||` 的右侧**只在必要时求值**：

```rust
// 解释器里不是先算两边再合，而是：
if op == And && 左侧为 false { 直接返回 false }   // 右侧不求值！
if op == Or  && 左侧为 true  { 直接返回 true  }   // 右侧不求值！
```

所以 `true || (1 / 0 == 1)` **不会**报除零错误——右侧从未执行。
这是语义正确性的关键细节，测试里专门有一条。

## 3. 表达式求值

```rust
fn eval(&mut self, expr: &Expr, env: &Rc<Env>) -> TResult<Value> {
    match expr {
        Expr::Int(v)      => Ok(Value::Int(*v)),        // 字面量：直接返回
        Expr::Var(name)   => env.get(name),             // 变量：查环境
        Expr::Binary{..}  => { /* 先求左，再求右，应用规则 */ }
        Expr::Call{..}    => self.call(callee, args, env),
        // ...
    }
}
```

求值就是**把语法结构翻译成值**：字面量→值，变量→查环境，
二元→递归求两边再运算，调用→查函数表执行。

## 4. 语句执行与控制流信号

语句执行会产生**副作用**（定义变量、打印、跳转），需要一种机制
把 `return` 和 `break` 从深层嵌套里"传"出来：

```rust
enum Flow {
    Normal,       // 继续下一条
    Break,        // 跳出循环
    Return(Value) // 从函数返回
}
```

```rust
fn exec_stmt(&mut self, stmt: &Stmt, env) -> TResult<Flow> {
    match stmt {
        Stmt::If { .. } => {
            // 条件为真 → 执行 then，否则执行 else
            // 分支里如果出现 Return/Break，原样向上传
        }
        Stmt::While { .. } => {
            // 循环体返回 Break → 吞掉并结束循环
            // 循环体返回 Return → 向上传播（函数提前返回）
        }
        Stmt::Return(expr) => return Ok(Flow::Return(value)),  // 信号！
        // ...
    }
}
```

每个执行块都检查子语句返回的 `Flow`：不是 `Normal` 就停止本块
并向上传递——这就是**控制流信号传播**。

## 5. 函数调用

```rust
fn call(&mut self, callee: &str, args: &[Expr], env) -> TResult<Value> {
    // 1. 查内建函数表（print）
    // 2. 查用户函数表
    // 3. 参数个数校验、类型校验（运行时）
    // 4. 新建调用环境，把参数绑定进去
    // 5. 执行函数体，回收 Flow::Return(v)
}
```

函数调用 = **新建环境 + 绑定参数 + 执行体 + 取回返回值**。
无返回值的函数返回 `Nil`。

## 6. 必会概念清单

1. **解释器 = 递归求值器**：树的深度即调用深度
2. **短路求值影响语义**：`true || (1/0==1)` 不报错
3. **控制流信号**：`return`/`break` 靠 `Flow` 枚举逐层上传
4. **运行时类型检查**：参数类型、运算类型、条件类型
5. **int/int 整除**：`7 / 2 == 3`，`7 / 2.0 == 3.5`——两者不同

## 7. 练习

- 用 REPL 验证 `7 / 2`、`7 / 2.0`、`1 == 1.0`、`"a" < "b"` 的结果
- 给 `Value` 增加 `char` 类型，说出需要改哪些匹配分支
- 设计一个 `len()` 内建函数（返回字符串长度），在解释器里实现它

## 8. 阶段验收

- [ ] 能解释短路求值的执行顺序
- [ ] 能说出 `Flow` 枚举解决了什么问题
- [ ] 能写出一个抛运行时类型错误的测试用例

## 下一阶段

[Ph04 · 作用域与函数](../Ph04-scope-func/04-scope-func.md) — 变量为什么"看不见"。
