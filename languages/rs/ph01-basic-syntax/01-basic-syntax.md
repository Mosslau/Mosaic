# Rust 基础语法阶段

> 面向安全高性能数据基础设施方向，从 Rust 的表达式思维、默认不可变和编译器驱动开发起步。

## 1. 概述

Rust 基础语法阶段的定位是：**能写简单 Rust 程序，理解 Rust 与 C/C++ 在类型、表达式和安全模型上的基础差异**。这个阶段不涉及所有权（Ownership）和借用（Borrowing）——那是第二阶段的内容，但 Rust 的许多设计已经透露出它的安全哲学。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 工具链 | `rustup`、`cargo`、`rustc` |
| 函数 | `fn main`、表达式 vs 语句、`println!` 宏 |
| 变量 | `let`、`mut`、常量、阴影（Shadowing） |
| 类型 | 基本类型、元组（Tuple）、数组 |
| 控制流 | 运算符、`if`、`loop`、`while`、`for`、`match` |

第一天就要用上 `cargo`——这是 Rust 与其他语言最显著的工具链差异。

## 2. 来源与演变

Rust 由 Graydon Hoare 于 2006 年开始设计，Mozilla 于 2009 年赞助，2015 年发布 1.0 稳定版。核心目标是**在不牺牲性能的前提下保证内存安全——不依赖垃圾回收（Garbage Collector, GC）**。

| 版本 | 年份 | 标志性变化 |
|------|------|-----------|
| 0.1 | 2012 | 首个公开版本，大量采用垃圾回收 |
| 1.0 | 2015 | 稳定版发布，确立向后兼容承诺 |
| Edition 2018 | 2018 | `impl Trait`、`dyn Trait`、`?` 随处可用、模块路径改进 |
| Edition 2021 | 2021 | 闭包捕获规则更精细、`IntoIterator` for arrays |
| Edition 2024 | 2024 | let 链（`if let ... && let ...`）、`impl Trait` 生命周期捕获改进、`unsafe fn` 内 unsafe 操作需显式 `unsafe` 块（lint 默认警告） |

**Edition（版次）不是编译器版本**：同一编译器可以编译不同 Edition 的代码，Edition 控制语法和语义的**可选变更**。

## 3. 语法与参数

### 3.1 第一个程序：Hello Rust

```rust
fn main() {
    let name = "Rust";
    println!("Hello, {}", name);
}
```

每个 Rust 程序都有 `fn main()` 作为入口。`println!` 后跟 `!` 表示它是**宏（Macro）**而非普通函数——宏在编译时展开为代码。

### 3.2 变量：let、mut、Shadowing

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

| 概念 | 说明 |
|------|------|
| 默认不可变 | 变量声明后默认不能修改，增强代码安全性 |
| `mut` | 显式声明为可变变量 |
| 阴影（Shadowing） | 用 `let` 重新声明同名变量，可以改变类型 |
| 常量 `const` | 编译期常量，必须标注类型，命名惯例全大写 |

**关键概念**：`let x = 5` 的 `=` 是**绑定（Binding）**——将值绑定到名称，而不是给已存在的变量赋值。Rust 的术语中更常说"绑定"而非"变量"。

### 3.3 基本类型

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

### 3.4 复合类型：元组与数组

```rust
// 元组（Tuple）：固定长度，元素类型可不同
let tup: (i32, f64, char) = (500, 6.4, 'A');
let (x, y, z) = tup;       // 解构（Destructuring）
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

### 3.5 运算符

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

### 3.6 控制流：if、loop、while、for、match

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

### 3.7 函数：表达式与语句

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
println!("{:#?}", complex_struct);  // 美化调试输出
```

`println!` 后的 `!` 表示宏调用。宏在编译期展开为代码，可以接收可变数量的参数并进行**编译期格式字符串检查**——格式错误会在编译时报错，而不是运行时报错。

**常用格式说明符**：

| 格式 | 用途 | 示例 |
|------|------|------|
| `{}` | 默认 Display 输出（面向用户） | `println!("{}", 42)` → `42` |
| `{:?}` | Debug 输出（面向开发者） | `println!("{:?}", vec![1,2])` → `[1, 2]` |
| `{:#?}` | 美化 Debug 输出 | 多行缩进显示结构 |
| `{:p}` | 指针地址 | `println!("{:p}", &x)` |

**关键区别**：`{}` 需要类型实现 `Display` trait，`{:?}` 需要实现 `Debug` trait。基础阶段最实用的技巧——给结构体加 `#[derive(Debug)]` 就能用 `{:?}` 打印调试信息。

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

## 6. 代码示例

### 示例 1：猜数字游戏（基础版）

```rust
use std::io;

fn main() {
    println!("猜数字（1-100）！");

    let secret = 42;    // 固定答案，后续阶段用随机数

    loop {
        println!("请输入你的猜测：");

        let mut guess = String::new();
        io::stdin()
            .read_line(&mut guess)
            .expect("读取失败");

        let guess: i32 = guess.trim().parse().expect("请输入数字");

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

### 阶段验收标准

- 能独立创建并运行 cargo 项目（`cargo new` / `cargo run`）
- 能解释 `mut`、shadowing、表达式返回值的含义
- 能写出使用 `if`、`loop`、`for`、`match` 的程序
- 能根据编译错误定位基础语法问题并修复
- 能使用 `println!` 进行格式化输出和调试

### 进入下一阶段前

确保能完成以下练习：
- 写 Hello Rust
- 猜数字游戏（基础版）
- 温度转换器
- 九九乘法表
- 素数判断
- 把 `if`/`else` 分支改写成 `match`
- 对比 `let x = 5;` 与 `x = 5;` 的行为差异
- 命令行计算器（支持加减乘除、错误输入提示）

### 推荐项目

- **命令行计算器**：支持加减乘除、错误输入提示和基础测试

### 下一阶段

[所有权 Ownership 阶段](../ph02-ownership/02-ownership.md) — 掌握 Rust 最核心的内存管理规则：move、借用、生命周期。
