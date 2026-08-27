# Ph05 · 代码生成（Codegen → Go）

> 源码对照：[`impl/src/codegen.rs`](../../../impl/src/codegen.rs)
> 测试对照：`impl/src/codegen.rs` 末尾的 `#[cfg(test)] mod tests`

## 1. 概述

**代码生成（Code Generation）** 把 AST 翻译成另一种语言的源码——
这是「源码到源码（source-to-source）」的编译器：输入是 Tenet，
输出是 Go。解释器在运行时做类型检查，而 Go 的编译器会在**编译期**
替我们做类型检查——于是生成的 Go 代码必须是类型正确的。

```
同一棵 AST
   ├──► 解释器：递归求值，运行时检查
   └──► 代码生成：递归翻译，交给 Go 编译期检查
```

## 2. 核心映射

| Tenet | Go | 说明 |
|-------|----|----|
| `int` | `int64` | 平台无关的整数宽度 |
| `float` | `float64` | |
| `bool` | `bool` | |
| `string` | `string` | |
| `let x: T = v;` | `var x T = v;` | |
| `while (c) { }` | `for c { }` | **Go 没有 while**，语法翻译 |
| `print(...)` | `fmt.Println(...)` | 触发 `import "fmt"` |
| `fn f(a: int) -> int { }` | `func f(a int64) int64 { }` | |
| `break;` | `break;` | |

结构上：函数声明 → 包级 `func`；顶层语句 → 塞进 `func main()`。
生成的完整 Go 文件：

```go
package main

import "fmt"

func fib(n int64) int64 {
    if (n < 2) {
        return n;
    }
    return (fib((n - 1)) + fib((n - 2)));
}

func main() {
    var i int64 = 0;
    for (i <= 10) {
        fmt.Println("fib(", i, ") =", fib(i));
        i = (i + 1);
    }
}
```

## 3. 静态类型推断

`let` 可以省略类型标注：`let x = 1 + 2.5;`。
代码生成器必须静态推出 `x` 的类型——规则与解释器完全一致：

```rust
fn infer_type(expr) -> Option<Type> {
    Int 字面量      → Int
    Float 字面量    → Float
    变量            → 查符号表（记录已声明的变量类型）
    二元运算        → 按运算规则：+ 可能 int/float/string；比较 → bool
    函数调用        → 查函数签名表的返回类型
}
```

符号表（`symbols: HashMap<String, Type>`）是代码生成器的"变量类型环境"，
等价于解释器的 `Env`，但只存类型不存值。函数参数进入符号表，
函数体结束后恢复——保证函数间互不污染。

推断失败的场景：

```tenet
fn f() { }        // 无返回类型
let x = f();      // 推断不出 x 的类型 → 编译错误，提示显式标注
```

## 4. 三个容易翻车的细节

### 4.1 浮点字面量必须保留小数点

Rust 的 `f64` 打印 `2.0` 会得到 `"2"`。如果直接输出：

```go
fmt.Println(7 / 2)      // Go 整数除法 → 3（错误！）
```

Tenet 里 `7 / 2.0` 是浮点除法，必须生成 `(7 / 2.0)` → 3.5。
修复：输出前检查字符串是否含 `.`，没有就补 `.0`。

### 4.2 `import "fmt"` 必须按需生成

Go 对**未使用的 import 直接编译失败**。因此要预先扫描整个 AST，
只要任何地方（包括函数体内）调用了 `print` 才生成 `import "fmt"`。

### 4.3 字符串转义

Tenet 字符串里的 `\n`、`\"` 等要**二次转义**成 Go 字面量：

```rust
"a\nb"  → 生成  "a\\nb"   （Go 源码里的写法）
```

## 5. 端到端验证

```bash
# 解释器执行
cargo run -- run examples/fib.tenet

# 生成 Go 并真实编译运行，输出应与解释器一致
cargo run -- codegen examples/fib.tenet > fib.go
go run fib.go
```

`examples/` 下 4 个示例（hello / fib / fizzbuzz / scope）
都经过解释器与 Go 双端验证，输出逐字节一致。

## 6. 必会概念清单

1. **代码生成 = 语义保持的翻译**：同一行为，不同语法
2. **类型推断与解释器语义对齐**：两端必须一致
3. **按需 import**：Go 的未使用 import 是编译错误
4. **字面量要小心格式化**：`2.0` 丢小数点会改变除法语义
5. **符号表 = 只存类型的 Env**：函数作用域要保存/恢复

## 7. 练习

- 生成 `fizzbuzz.tenet` 的 Go 代码，观察 `else if` 链如何翻译
- 给 Tenet 增加 `not` 关键字（等价 `!`），修改 codegen 的对应分支
- 设计一个 `double(x: int) -> int` 内建函数，需要改哪些文件？

## 8. 阶段验收

- [ ] 能说出 `while` 到 Go 的翻译规则
- [ ] 能解释类型推断为什么必须与解释器规则一致
- [ ] 生成的 Go 代码能通过 `go run` 直接执行且输出正确

## 里程碑

到这里，Tenet 已经走完「词法 → 语法 → 语义 → 代码生成」的完整管线。
回头看仓库里 6 种语言的 Roadmap——C 的语法、Go 的工程、Rust 的实现、
Python 的求值模型，都在这一千多行 Rust 里汇成了一条线。

下一步方向见 [tenet.md 后续演进](../tenet.md)：闭包、复合类型、
字节码 VM、静态类型检查器。
