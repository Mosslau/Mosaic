# Tenet 语言设计 Roadmap

> 万语归宗——分析 C++ / Rust / Python 的设计，继承优点、拒绝包袱，
> 合成一门属于自己的语言。完整语言规范见 [`grammar.md`](./grammar.md)，
> 设计决策溯源见 [`design-notes.md`](./design-notes.md)。

> 📌 **本文档是 Tenet 语言的设计说明书**（语法、语义、管线设计）。
> 目前处于**设计阶段**：先定设计决策与规范，实现暂缓（三端实现的完整代码
> 曾存在于本仓库，设计成熟后再重建）。

## 语言速览

Tenet 是吸收了 C++ / Rust / Python 设计的**静态类型语言**：语法骨骼像 C 家族，
安全与抽象学 Rust，开发体验学 Python，资源哲学学 C++ 的 RAII。

```tenet
// 标量与类型推断（Python 式 let，Rust 式签名）
let name: string = "Tenet";
let year = 2026;                 // 推断为 int

// struct 组合（C / Rust：无继承，组合优先）
struct Point {
    x: int;
    y: int;
}
let origin: Point = Point { x: 0, y: 0 };
print("origin:", origin.x, origin.y);

// array + 索引 + len
let primes: array<int> = [2, 3, 5, 7];
print("primes:", len(primes), "first:", primes[0]);

// Option：显式空值，无 null（Rust）
fn find(nums: array<int>, target: int) -> Option<int> {
    let i: int = 0;
    while (i < len(nums)) {
        if (nums[i] == target) { return Some(i); }
        i = i + 1;
    }
    return None;
}

// Result + ?：显式错误传播，无异常（Rust）
fn half(n: int) -> Result<int, string> {
    if (n % 2 != 0) { return Err("不是偶数"); }
    return Ok(n / 2);
}
let h = half(10)?;               // Ok → 10；Err → 当前函数立即返回 Err

// match：穷尽性分支（Rust）
match find(primes, 5) {
    Some(i) => print("found at", i),
    None => print("not found"),
}
```

| 维度 | 设计 |
|------|------|
| 类型系统 | 标量 `int`/`float`/`bool`/`string` + 复合 `array<T>`/`struct` + `Option<T>`/`Result<T,E>` |
| 变量 | `let` 声明，类型标注可选（局部静态推断）；赋值 `=`（值语义） |
| 函数 | `fn f(a: int) -> int`，显式返回类型，递归，`?` 错误传播 |
| 数据建模 | `struct` 组合（无继承）；字段访问 `.` |
| 控制流 | `if/else`、`while`（唯一循环）、`break`/`continue`、`match` |
| 空值 | `Option<T>`（`None`/`Some`），无 null |
| 错误 | `Result<T,E>`（`Ok`/`Err`）+ `?` 显式传播，无异常 |
| 内存 | 自动管理：值语义 + 引用计数，无指针 |
| 注释 | `//` 行注释、`/* */` 块注释 |
| 内建 | `print(...)`、`len(x)` |

## 实现阶段（暂缓）

Tenet 当前聚焦**设计**：语法、语义与管线已在 [grammar.md](./grammar.md) 固化，
设计取舍记录在 [design-notes.md](./design-notes.md)。
可运行的完整实现（Rust / Python / C++ 三端，语义一致、Go 输出逐字节相同）
曾在本仓库中验证过 v1 设计的可行性，现阶段已移出，待 v2 设计定稿后重建。

## 阶段路线

> 每个阶段是独立的设计主题，可单独阅读；实现恢复后补充源码对照。

### 1. 词法分析阶段

> 📖 [Ph01-lexer/01-lexer.md](./Ph01-lexer/01-lexer.md)

把源码字符串切成 Token 流：字面量、关键字、运算符、注释与空白。

- **目标**：理解「字符 → 词法单元」的映射，能写出带行列号的 Tokenizer
- **必会概念**：最长匹配、关键字 vs 标识符、转义序列、错误定位（行:列）
- **阶段验收**：能说明 `==` 为什么不能拆成两个 `=`；能说出 `3.` 和 `3` 的词法区别

### 2. 语法分析与 AST 阶段

> 📖 [Ph02-parser-ast/02-parser-ast.md](./Ph02-parser-ast/02-parser-ast.md)

把 Token 流变成抽象语法树（AST），验证语法正确性。

- **目标**：掌握递归下降解析与优先级爬升（Pratt Parsing）
- **必会概念**：优先级表、左结合、一元/二元表达式、错误恢复、`else if` 链
- **阶段验收**：能画出 `1 + 2 * 3` 的 AST；能解释 `-x * y` 为什么是 `(-x) * y`

### 3. 解释器与值系统阶段

> 📖 [Ph03-interpreter/03-interpreter.md](./Ph03-interpreter/03-interpreter.md)

直接对 AST 求值：表达式递归求值，语句递归执行。

- **目标**：理解「树遍历求值」这一解释器核心模型
- **必会概念**：短路求值、运行时类型检查、`return`/`break` 的控制流信号传播
- **阶段验收**：能解释 `true || (1 / 0 == 1)` 为什么不报除零错误

### 4. 作用域与函数阶段

> 📖 [Ph04-scope-func/04-scope-func.md](./Ph04-scope-func/04-scope-func.md)

块作用域、词法作用域链、函数调用与递归。

- **目标**：实现变量遮蔽、赋值查找、参数传递与递归调用栈
- **必会概念**：环境（Environment）与父指针、遮蔽（Shadowing）、调用帧
- **阶段验收**：能解释内层 `let x` 为何不影响外层 `x`；能说明递归为什么能工作

### 5. 代码生成阶段

> 📖 [Ph05-codegen/05-codegen.md](./Ph05-codegen/05-codegen.md)

把 AST 翻译成 Go 源码——源码到源码的编译器。

- **目标**：理解「语义相同、语法不同」的代码生成过程
- **必会概念**：类型映射、静态类型推断、`while` → `for` 的语法翻译、字符串转义
- **阶段验收**：能说明 `7 / 2.0` 为什么必须保留小数点；生成的 Go 代码可被 `go run` 直接执行

## 与仓库里 6 种语言的关系

| 参考对象 | Tenet 学到了什么 |
|---------|-----------------|
| C | 语法风格（`{}`、`;`、运算符优先级）、静态类型思想、标量 + 数组 + struct 的数据模型 |
| C++ | 值语义、RAII 资源管理思想、性能意识（分析见 tenet-cpp/） |
| Go | 代码生成目标语言、`:=` 式类型推断、`for` 即唯一循环 |
| Rust | 组合优先（trait 思想）、`Option`/`Result` + `?`、`match` 穷尽性、错误带位置（分析见 tenet-rs/） |
| Python | 类型推断、REPL、`print` 内建、可读性与上手体验（分析见 tenet-py/） |
| Java | 词法作用域、函数调用栈等语义的对照 |

## 后续演进方向

- **trait / 方法**：给 struct 加行为抽象（吸收 Rust trait，仍无继承）
- **泛型**：类型参数化（吸收 C++ 模板 / Rust 泛型，最后再加）
- **字节码 VM**：AST 编译为字节码 + 虚拟机执行，性能提升一个数量级
- **类型检查器独立阶段**：把 grammar.md 5.3 的静态检查从解释器剥离为独立编译阶段
- **模块 / 多文件**：工程化组织
- **自举**：用 Tenet 写 Tenet 编译器（吸收 clang/rustc/CPython 的参考实现模式）
