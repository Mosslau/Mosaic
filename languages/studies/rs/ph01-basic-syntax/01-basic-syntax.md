# Rust 基础语法阶段

> 面向安全高性能数据基础设施方向，从 Rust 的表达式思维、默认不可变和编译器驱动开发起步。

## 1. 概述

Rust 基础语法阶段的定位是：**能写简单 Rust 程序，理解 Rust 与 C/C++ 在类型、表达式和安全模型上的基础差异**。这个阶段不涉及所有权（Ownership）和借用（Borrowing）——那是第二阶段的内容，但 Rust 的许多设计已经透露出它的安全哲学。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 工具链 | `rustup`、`cargo`、`rustc` |
| 函数 | `fn main`、表达式 vs 语句、`println!` 宏 |
| 变量 | `let`、`mut`、阴影（Shadowing）、常量（const） |
| 类型 | 基本类型、元组（Tuple）、数组 |
| 控制流 | 运算符、`if`、`loop`、`while`、`for`、`match` |
| 测试 | `#[test]`、`assert_eq!`、`cargo test` |

第一天就要用上 `cargo`——这是 Rust 与其他语言最显著的工具链差异。

## 2. 来源与演变

Rust 由 Graydon Hoare 于 2006 年开始设计，Mozilla 于 2009 年赞助，2015 年发布 1.0 稳定版。核心目标是**在不牺牲性能的前提下保证内存安全——不依赖垃圾回收（Garbage Collector, GC）**。

本文示例以 **Edition 2021** 为基线（本文涉及的基础语法在 2015/2018/2021 版次下行为一致），本环境验证工具链为 rustc 1.92.0（默认 Edition 2021）。基础语法与 `cargo` 工具链自 Rust 1.0 起稳定。

| 版本 | 年份 | 标志性变化 |
|------|------|-----------|
| 0.1 | 2012 | 首个公开版本，大量采用垃圾回收 |
| 1.0 | 2015 | 稳定版发布，确立向后兼容承诺 |
| Edition 2018 | 2018 | `impl Trait`、`dyn Trait`、`?` 随处可用、模块路径改进 |
| Edition 2021 | 2021 | 闭包捕获规则更精细、`IntoIterator` for arrays |
| Edition 2024 | 2024 | `impl Trait` 生命周期捕获改进、`unsafe fn` 内 unsafe 操作需显式 `unsafe` 块（lint 默认警告） |

**Edition（版次）不是编译器版本**：同一编译器可以编译不同 Edition 的代码，Edition 控制语法和语义的**可选变更**。

## 3. 语法与参数

### 3.1 工具链：rustup、cargo、rustc

安装 Rust 的官方方式是 **rustup**（工具链管理器）：

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup --version        # 验证安装
rustc --version         # 查看编译器版本
cargo --version         # 查看包管理器版本
```

三者分工：

| 工具 | 角色 | 常用命令 |
|------|------|---------|
| `rustup` | 工具链管理器 | `rustup update`（升级）、`rustup component add clippy rustfmt`（装组件） |
| `cargo` | 包管理器 + 构建系统 | `cargo new hello`（建项目）、`cargo run`（编译并运行）、`cargo check`（只检查不产出二进制，最快） |
| `rustc` | 编译器本体 | `rustc main.rs`（直接编译单文件，日常不用） |

```bash
cargo new hello && cd hello   # 生成 Cargo.toml + src/main.rs
cargo run                     # 编译并运行，输出 Hello, world!
```

学习阶段的日常节奏：改代码 → `cargo check` 秒级验证类型 → `cargo run` 看效果。**不要直接调用 rustc 管理多文件项目**——那是 cargo 的职责。

### 3.2 第一个程序：Hello Rust

```rust
fn main() {
    let name = "Rust";
    println!("Hello, {}", name);
}
```

每个 Rust 程序都有 `fn main()` 作为入口。`println!` 后跟 `!` 表示它是**宏（Macro）**而非普通函数——宏在编译时展开为代码。

### 3.3 变量：let、mut、Shadowing、const

| 概念 | 说明 |
|------|------|
| 默认不可变 | 变量声明后默认不能修改，增强代码安全性 |
| `mut` | 显式声明为可变变量 |
| 阴影（Shadowing） | 用 `let` 重新声明同名变量，可以改变类型 |
| 常量 `const` | 编译期常量，必须标注类型，命名惯例全大写 |

**关键概念**：`let x = 5` 的 `=` 是**绑定（Binding）**——将值绑定到名称，而不是给已存在的变量赋值。Rust 的术语中更常说"绑定"而非"变量"。

```rust
let x = 5;           // 默认不可变（Immutable）
// x = 6;            // 编译错误！x 不可修改

let mut y = 10;      // mut 关键字声明可变变量
y = 20;              // 合法

// 阴影（Shadowing）：重新声明同名变量
let z = 5;
let z = z + 1;       // z = 6，新变量"遮蔽"旧变量
let z = "hello";     // 甚至可以改变类型！
```

`const` 与 `mut` 的区别：

| 对比项 | `let mut` | `const` |
|--------|-----------|---------|
| 可变性 | 运行时可修改 | 永远不可变 |
| 类型标注 | 可省略（推导） | **必须**显式标注 |
| 值 | 任意表达式 | 只能是编译期常量表达式 |
| 命名惯例 | snake_case | SCREAMING_SNAKE_CASE |

```rust
const MAX_POINTS: u32 = 100_000;   // 必须标注类型，编译期确定
// const MAX: u32 = compute();     // 编译错误！不能是运行时才能算出的值

let mut count = 0;
count += 1;                        // mut：运行时可变，作用域内
```

### 3.4 基本类型

| 类型 | 示例 | 说明 |
|------|------|------|
| `i32` | `42` | 有符号 32 位整数（默认整数类型） |
| `u64` | `100u64` | 无符号 64 位整数 |
| `f64` | `3.14` | 双精度浮点（默认浮点类型） |
| `bool` | `true` / `false` | 布尔类型 |
| `char` | `'A'`、`'中'` | Unicode 标量值（4 字节） |
| `&str` | `"hello"` | 字符串切片（借用，第二阶段详解） |
| `String` | `String::from("hi")` | 堆分配的可变字符串 |

```rust
let age: u32 = 30;        // 显式类型标注
let pi = 3.14159_f64;     // 后缀标注
let flag = true;           // 类型推导
let heart_eyed_cat = '😻'; // Rust char 支持 Unicode（4 字节）
```

**数字字面量可读性**——下划线分隔与进制前缀：

```rust
let million = 1_000_000;   // 下划线纯为可读性，编译时忽略
let hex = 0xff;            // 十六进制 = 255
let octal = 0o77;          // 八进制 = 63
let binary = 0b1010;       // 二进制 = 10
let byte = b'A';           // 字节字面量（u8）= 65
```

**String 与 &str 的基础操作**——本阶段只需掌握创建与拼接：

```rust
let s1 = String::from("Hello");  // 堆上可增长的字符串
let s2 = "world";                // 字符串字面量，类型是 &str

let joined = format!("{} {}", s1, s2);  // 拼接首选 format!，返回新 String
println!("{}", joined);                 // Hello world

let owned = s1 + " " + s2;       // + 拼接也行，但会"消耗"s1（原因在 ph02 所有权）
// println!("{}", s1);           // 编译错误！s1 已被移动
```

> 本阶段先记住两条实践规则：拼接用 `format!`（直观且不消耗原值）；`String` 和 `&str` 为什么不能随意互转，等 ph02 讲清所有权就明白了。

### 3.5 复合类型：元组与数组

```rust
// 元组（Tuple）：固定长度，元素类型可不同
let tup: (i32, f64, char) = (500, 6.4, 'A');
let (x, y, _) = tup;       // 解构（Destructuring）；用不到的元素用 _ 丢弃，避免 unused warning
println!("{} {}", tup.0, tup.1);  // 索引访问

// 数组（Array）：固定长度，元素类型相同，分配在栈上
let arr: [i32; 5] = [1, 2, 3, 4, 5];
let zeros = [0; 100];      // 100 个 0 的数组
println!("{} {}", arr[0], arr.len());
```

| 类型 | 长度 | 元素类型 | 内存位置 |
|------|------|---------|---------|
| 元组 `(T, U)` | 固定 | 可不同 | 栈 |
| 数组 `[T; N]` | 固定 | 必须相同 | 栈 |
| `Vec<T>` | 动态 | 必须相同 | 堆（第三阶段学） |

### 3.6 运算符

| 类别 | 运算符 | 示例 |
|------|--------|------|
| 算术 | `+ - * / %` | `a + b`, `x % 2` |
| 关系 | `== != < > <= >=` | `a == b` |
| 逻辑 | `&& \|\| !` | `a && b`（短路求值） |
| 位运算 | `& \| ^ << >>` | `n & 1`（判断奇偶） |
| 赋值 | `= += -= *= /=` | `x += 1` |
| 范围 | `..` `..=` | `1..5`（左闭右开）、`1..=5`（闭区间） |

**注意**：
- Rust **没有** `++`/`--`——用 `x += 1` 代替
- 没有三元运算符——`if` 本身就是表达式：`let max = if a > b { a } else { b };`
- debug 模式下整数溢出会 panic，release 模式下静默回绕（wrapping）

### 3.7 控制流：if、loop、while、for、match

**if 是表达式**——它有返回值：

```rust
let condition = true;
let number = if condition { 5 } else { 6 };  // if 表达式返回值
// 注意：两个分支必须返回相同类型
```

**loop 无限循环**——也可以返回值：

```rust
let mut counter = 0;
let result = loop {
    counter += 1;
    if counter == 10 {
        break counter * 2;   // break 返回值
    }
};
println!("{}", result);    // 20
```

**while 和 for**：

```rust
let mut n = 3;
while n > 0 {
    println!("{}", n);
    n -= 1;
}

let arr = [10, 20, 30, 40];
for element in arr.iter() {
    println!("{}", element);
}

// 范围表达式
for i in 1..5 {     // 1..5 是 1,2,3,4（左闭右开）
    println!("{}", i);
}
for i in (1..=5).rev() {  // 1..=5 是 1,2,3,4,5，rev() 反转
    println!("{}", i);
}
```

**match 模式匹配**——基础阶段就引入：

```rust
let day = 3;
match day {
    1 => println!("Monday"),
    2 => println!("Tuesday"),
    3 => println!("Wednesday"),
    _ => println!("Other day"),   // _ 是通配符
}

// match 也是表达式
let grade = match 85 {
    90..=100 => 'A',
    80..=89  => 'B',
    70..=79  => 'C',
    _        => 'F',
};
```

### 3.8 函数：表达式与语句

```rust
// 语句（Statement）：不返回值，以分号结尾
let x = 5;   // 语句

// 表达式（Expression）：有返回值，不以分号结尾
x + 1        // 表达式 = 6

fn add(a: i32, b: i32) -> i32 {
    a + b    // 最后一行无分号 = 返回值（表达式）
}

fn greet(name: &str) -> String {
    format!("Hello, {}", name)  // 返回 String
}
```

**关键概念**：Rust 中函数体最后一个表达式就是返回值。加上分号就变成语句，返回 `()`（单元类型，Unit Type）。

### 3.9 类型转换：没有隐式转换

对比 C/C++ 的"小范围自动向大范围提升"，Rust 几乎**不做任何隐式转换**——`i32` 不会自动变成 `i64`，整数不会自动变浮点：

```rust
// 编译错误！Rust 不允许隐式转换
let a: i32 = 5;
let b: i64 = a;              // E0308：expected `i64`, found `i32`

let x: i32 = 5;
let y: f64 = x as f64 / 2.0; // 用 as 显式转换：2.5
```

**为什么**：隐式转换是"整型提升/截断"类 bug 的温床（C 里 `7 / 2` 得到 `3` 这类问题）。Rust 的选择是让类型变换**显式可见**——编译器不猜，你写 `as` 就表明"我知道这里在变类型"。

常用转换形态：

```rust
let n = 3.99_f64;
let truncated = n as i32;      // 3：as 向零截断（不是四舍五入）
let c = 'A' as u8;             // 65：字符转字节
let back = 65_u8 as char;      // 'A'
let big: i64 = 42_i32 as i64;  // 拓宽也要显式写
```

> ⚠️ `as` 是"尽力转换"：截断、可能溢出（`u8` 转成放不下的值会回绕）都不报错。需要"转换失败就报错"的场景要用 `TryFrom`/`parse`——`"42".parse::<i32>()` 返回 `Result`，这是 ph02 之后错误处理阶段的内容；本阶段掌握 `as` 的基础转换即可。

### 3.10 单元测试：#[test] 与 assert_eq!

cargo 内置测试框架，不需要任何依赖。测试函数用 `#[test]` 标注，写在被测代码同一个文件底部即可：

```rust
fn add(a: i32, b: i32) -> i32 {
    a + b
}

fn add_u8(x: u8, y: u8) -> u8 { x + y }   // 独立函数：编译器不做跨函数常量折叠

#[cfg(test)]
mod tests {
    use super::*;   // 引入外层模块的函数

    #[test]
    fn test_add() {
        assert_eq!(add(2, 3), 5);       // 相等断言：失败会打印两个值
        assert_ne!(add(2, 3), 6);       // 不相等断言
        assert!(add(2, 3) > 0);         // 布尔断言
    }

    #[test]
    #[should_panic]                     // 预期 panic 的测试
    fn test_overflow() {
        add_u8(255, 1);   // 运行时溢出 panic（debug 模式，见 3.6）
        // 注意：直接写 255_u8 + 1 会在编译期被 arithmetic_overflow 拦下，
        // 连测试都编不过——所以运行时溢出要用函数参数传入
    }
}
```

> 💡 上面这个"溢出测试"还隐藏了一课：`arithmetic_overflow` lint 会在**编译期**拦截常量溢出表达式（这正是 Rust 静态检查的价值），想演示运行时 panic 必须让值经过函数参数传进来。

运行方式：

```bash
cargo test     # 运行全部测试，输出 passed/failed 统计
cargo test test_add   # 只跑名字匹配的测试
```

要点：测试代码放在 `#[cfg(test)]` 模块里，只在 `cargo test` 时编译，`cargo build` 会跳过它们。本阶段的练习和项目都要求为每个函数补上 `assert_eq!` 断言——这也是验证"函数返回值 = 最后一个表达式"最直接的方式。

## 4. 底层原理

### 4.1 Rust 编译流程

```
.rs 源文件 → rustc 编译 → 二进制可执行文件
            ↓
      cargo build → target/debug/可执行文件
```

- **rustc** 是编译器，直接编译单个文件
- **cargo** 是包管理器和构建系统，管理依赖、运行测试、格式化代码
- **`cargo check`** 只做类型检查不生成二进制，速度比 `cargo build` 快很多——学习阶段推荐用 `cargo check` 快速验证代码是否通过编译
- 编译时执行大量**静态检查**（类型检查、借用检查、未使用变量警告等），编译通过本身就过滤了大量 bug

### 4.2 默认不可变的设计哲学

```rust
let x = 5;
// x = 6;  // 编译错误
```

Rust 默认不可变背后的逻辑：
1. 不可变数据可以安全地被多处引用，不会有意外修改
2. 当你需要修改时，必须显式声明 `mut`——这是**意图表达**
3. 编译器可以基于不可变性做更多优化

这与 C/C++ 的"默认可变"形成鲜明对比，是 Rust 安全模型的基础。

### 4.3 表达式 vs 语句

大多数语言中 `if`/`loop`/`match` 是语句，但在 Rust 中它们都是**表达式**——这意味着它们有值：

```rust
// 在 Rust 中这很自然：
let status = if ok { "success" } else { "error" };

// 等价于 C++ 的三元运算符：
// auto status = ok ? "success" : "error";
```

表达式思维贯穿 Rust 的每个角落，函数返回值也是表达式的自然推演。

### 4.4 println! 是宏

```rust
println!("{0} + {1} = {2}", a, b, a + b);
println!("{name} is {age} years old", name="Alice", age=30);
println!("{:?}", (1, "two", 3.0));   // Debug 输出，元组可直接打印：`(1, "two", 3.0)`
// println!("{:#?}", some_struct);   // 美化 Debug 输出——struct 是 ph02 之后的内容，此处先埋个钩子
```

`println!` 后的 `!` 表示宏调用。宏在编译期展开为代码，可以接收可变数量的参数并进行**编译期格式字符串检查**——格式错误会在编译时报错，而不是运行时报错。

**常用格式说明符**：

| 格式 | 用途 | 示例 |
|------|------|------|
| `{}` | 默认 Display 输出（面向用户） | `println!("{}", 42)` → `42` |
| `{:?}` | Debug 输出（面向开发者） | `println!("{:?}", (1, 2))` → `(1, 2)` |
| `{:#?}` | 美化 Debug 输出 | 多行缩进显示结构 |
| `{:p}` | 指针地址 | `println!("{:p}", &x)` |

**关键区别**：`{}` 需要类型实现 `Display` trait，`{:?}` 需要实现 `Debug` trait。基础阶段先记住：基本类型、元组、数组都自带 `Debug`，可直接用 `{:?}` 打印；自定义类型加 `#[derive(Debug)]` 也能用（struct还没学到，这里是预告）。

### 4.5 编译器是学习伙伴：把报错当提示

Rust 编译器的错误信息是出了名的"话多"，但这恰恰是给学习者的福利——它不只是说"错了"，还告诉你**为什么错、该怎么改**。以 3.9 的类型不匹配为例，完整报错长这样：

```text
error[E0308]: mismatched types
 --> src/main.rs:3:18
  |
3 |     let b: i64 = a;    // a 是 i32
  |                  ^ expected `i64`, found `i32`
  |
help: you can convert an `i64` from an `i32`
  |
3 |     let b: i64 = a.into();
  |                   ~~~~~~~~
```

读法三要素：**错误码**（`E0308`，可搜官网按码查）；**位置**（`3:18` 是第 3 行第 18 列）；**help**（编译器常直接给出改法建议）。学习阶段的节奏因此变成"写错 → 读报错 → 按提示修 → 编译通过"，而不是对着代码干瞪眼——把编译器当作随时在线的代码评审，是 Rust 学习体验里最不一样的部分。

## 5. 使用场景

基础语法阶段适合解决的问题：

| 场景 | 涉及知识点 |
|------|-----------|
| 计算器 | 变量、算术、match 分支 |
| 猜数字游戏 | 循环、条件、输入输出 |
| 温度转换 | 函数、表达式、类型转换 |
| 字符串处理 | `String`、`&str`、拼接 |
| 数组操作 | 数组定义、for 遍历、索引访问 |

**不适合**此阶段的事项：
- 涉及所有权的数据传递（第二阶段）
- 使用 `Vec`、`HashMap` 等堆分配集合（第三阶段）
- 文件读写、网络编程

**通往所有权：本阶段埋下的三个钩子**

基础阶段刻意绕开了所有权（Ownership），但三处细节已经在为它铺垫：

| 你在这个阶段见到的现象 | 问题 | 在哪个阶段解开 |
|----------------------|------|--------------|
| `&str` 叫"字符串**切片**"、`&x` 取地址 | 那个 `&` 到底是什么？为什么叫"借用"（borrow）？ | ph02 所有权与借用 |
| `String::from("hi")` 要显式构造、`String` 能增长而 `&str` 不能 | 一个在堆上、一个在栈/静态区，内存从哪来、谁负责释放？ | ph02 / ph03 数据结构 |
| 示例里 `read_line(&mut guess)` 要写 `&mut` | 为什么要区分"可变借用"？别处能用吗？ | ph02 |
| 元组、数组能直接赋值给新变量 | 值被"复制"还是"移动"了？基本类型为什么感觉像复制？ | ph02（Copy 语义） |

带着这三个问题进入第二阶段，ownership 就不是"从天而降的抽象规则"，而是对这些现象的正面回答——Rust 的学习曲线因此是**一路还债**：基础阶段欠下的"为什么"，后面每个阶段逐个兑现。

## 6. 代码示例

> 本节每个示例的完整可运行文件在 [`examples/`](./examples/) 目录，验证环境 rustc 1.92.0，用 `rustc` 直接编译（命令见 examples/README.md）。示例 1 演示了不 panic 的输入解析写法（`match parse` + 提示后继续），替代了常见教程里的 `expect`——避免在学习初期养成"出错就 panic"的习惯。

### 示例 1：猜数字游戏（基础版）

```rust
use std::io;

fn main() {
    println!("猜数字（1-100）！");

    let secret = 42;    // 固定答案，后续阶段用随机数

    loop {
        println!("请输入你的猜测：");

        let mut guess = String::new();
        if io::stdin().read_line(&mut guess).is_err() {
            println!("读取输入失败");
            continue;
        }

        // 解析失败给出提示后继续，而不是 panic
        let guess: i32 = match guess.trim().parse() {
            Ok(n) => n,
            Err(_) => {
                println!("请输入数字");
                continue;
            }
        };

        match guess.cmp(&secret) {
            std::cmp::Ordering::Less    => println!("太小！"),
            std::cmp::Ordering::Greater => println!("太大！"),
            std::cmp::Ordering::Equal   => {
                println!("猜对了！");
                break;
            }
        }
    }
}
```

完整文件：`examples/ex01-guessing-game.rs`

### 示例 2：温度转换器

```rust
fn celsius_to_fahrenheit(c: f64) -> f64 {
    c * 9.0 / 5.0 + 32.0
}

fn fahrenheit_to_celsius(f: f64) -> f64 {
    (f - 32.0) * 5.0 / 9.0
}

fn main() {
    let temps_c = [0.0, 20.0, 37.0, 100.0];

    println!("摄氏度 -> 华氏度：");
    for c in temps_c.iter() {
        let f = celsius_to_fahrenheit(*c);
        println!("  {}°C = {:.1}°F", c, f);
    }

    // 使用 match 选择转换方向
    let mode = 'F'; // 'F' 表示华氏转摄氏，'C' 反之
    let value = 98.6;
    let result = match mode {
        'C' => celsius_to_fahrenheit(value),
        'F' => fahrenheit_to_celsius(value),
        _   => {
            println!("未知模式");
            0.0
        }
    };
    println!("Result: {:.1}", result);
}
```

完整文件：`examples/ex02-temperature-converter.rs`

### 示例 3：九九乘法表

```rust
fn main() {
    for i in 1..=9 {
        for j in 1..=i {
            print!("{}×{}={:<2}  ", j, i, i * j);
        }
        println!();
    }
}
```

完整文件：`examples/ex03-multiplication-table.rs`

### 示例 4：素数判断

```rust
fn is_prime(n: u32) -> bool {
    if n < 2 {
        return false;
    }
    let mut i = 2;
    while i * i <= n {
        if n % i == 0 {
            return false;
        }
        i += 1;
    }
    true
}

fn main() {
    print!("1-100 的素数: ");
    for i in 1..=100 {
        if is_prime(i) {
            print!("{} ", i);
        }
    }
    println!();
}
```

完整文件：`examples/ex04-is-prime.rs`

## 7. 总结

### 关键要点

1. **默认不可变**：`let` 声明的变量默认不可修改，`mut` 显式声明可变
2. **表达式有值**：`if`、`loop`、`match`、函数体最后一行都是表达式，有返回值
3. **语句无值**：以 `;` 结尾的是语句，返回单元类型 `()`
4. **match 穷尽检查**：编译器强制覆盖所有分支，遗漏会导致编译错误
5. **cargo 第一天就要用**：`cargo new`、`cargo build`、`cargo run` 是日常操作
6. **静态类型 + 类型推导**：类型在编译期确定，但大部分场景下编译器可以自动推导

### 跨语言对比：基础语法

| 特性 | C | C++ | Rust |
|------|---|-----|------|
| 变量默认 | 可变 | 可变 | **不可变** |
| if 表达式 | 语句 | 语句 | **表达式** |
| 循环 | for/while/do-while | for/while/do-while | for/while/loop |
| 多分支 | switch | switch | **match**（穷尽检查） |
| 包管理 | 无 | 无内置 | **cargo** |
| 代码格式化 | 手动 | 手动 | **cargo fmt** |

### 阶段验收清单

- [ ] 能独立创建并运行 cargo 项目（`cargo new` / `cargo run`）
- [ ] 能解释 `mut`、shadowing、表达式返回值的含义
- [ ] 能区分 `const` 与 `let mut` 的适用场景
- [ ] 能写出使用 `if`、`loop`、`for`、`match` 的程序
- [ ] 能根据编译错误定位基础语法问题并修复
- [ ] 能使用 `println!` 进行格式化输出和调试
- [ ] 能用 `#[test]` + `assert_eq!` 为函数编写基本测试

### 动手练习

本阶段练习见 [exercises/](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [project/](./project/)：命令行计算器——循环读入算式，支持加减乘除、错误输入提示和基础单元测试。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[所有权 Ownership 阶段](../ph02-ownership/02-ownership.md) — 掌握 Rust 最核心的内存管理规则：move、借用、生命周期。
