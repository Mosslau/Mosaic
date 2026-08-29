# Rust 集合、迭代器与函数式写法阶段

> 面向数据基础设施、异步网络服务方向：本阶段用迭代器写出简洁、可组合的数据处理代码——让"遍历 + 转换 + 聚合"从命令式循环变成一行链式表达式。

## 1. 概述

Rust 集合、迭代器与函数式写法阶段的定位是：**能用 `Iterator` trait 与 `iter`/`iter_mut`/`into_iter` 三种方式让所有权进入迭代器，用 `map`/`filter`/`fold`/`collect` 等适配器与消费器把数据处理写成惰性、可组合的链式表达式，理解闭包捕获的 `Fn`/`FnMut`/`FnOnce` 三种模式，并确信迭代器是零成本抽象**。本阶段是 ph03 数据结构阶段的函数式进阶：集合负责"存"，迭代器负责"算"——同样的数据，用迭代器链表达更简洁、更不易出错，也更贴近数据基础设施里"流式处理"的思维。

| 核心维度 | 覆盖内容 |
|----------|---------|
| Iterator trait 与三种迭代方式 | `iter()`（只读）、`iter_mut()`（可变）、`into_iter()`（消耗） |
| 适配器（adapter） | `map`、`filter`、`take`、`skip`、`enumerate`、`zip`、`chain` |
| 消费器（consumer） | `collect`、`sum`、`fold`、`count`、`any`、`all`、`find`、`max`、`min` |
| 闭包捕获 | `Fn` / `FnMut` / `FnOnce`、`move` 闭包、意外移动的坑 |
| 惰性求值 | 适配器只构建"执行计划"，消费器触发执行 |
| collect 的目标类型 | `Vec`、`HashMap`、`HashSet`、`String`（`FromIterator`） |
| 自定义迭代器 | 实现 `Iterator` trait 的 `next` 与 `Item` |
| 常见函数式模式 | grouping（entry API）、折叠聚合（fold） |

**本阶段边界**：承接 ph08 生命周期（迭代器与闭包中大量出现引用与生命周期，链式写法常见 `&T`、`&&T` 双层引用）；不深入智能指针与内部可变性（ph10，`Box`/`Rc`/`Arc`/`RefCell` 让共享可变成为可能）、错误处理工程化（ph11，`collect::<Result<Vec<_>,_>>` 等错误组合子）、并发与异步（ph12，rayon 并行迭代器与 `Stream` 是迭代器的并发/异步延伸）。

## 2. 来源与演变

Rust 迭代器的设计直接继承**函数式语言的列表处理传统**：Haskell 的 `map`/`filter`/`foldl` 与 Scala 集合库的转换算子是它的直接蓝本。早在 2009 年（Rust 还在 Mozilla 内部早期设计阶段），迭代器就被确立为核心抽象，随后以 RFC 流程固化为标准库 `std::iter` 模块与 `Iterator` trait。Rust 的选择是**惰性 + 单一 `next` 方法 + 适配器组合**：迭代器只描述"怎么取下一个元素"，`map`/`filter` 等适配器返回包装后的新迭代器而不立即执行，比"急切执行每个方法"的集合 API 更可组合——`for` 循环甚至只是 `IntoIterator` 的语法糖（`for x in v` 等价于 `for x in v.into_iter()`）。

`Iterator` trait 在 1.0 前后定型并稳定至今：`type Item` 关联类型描述元素类型，`next() -> Option<Self::Item>` 是唯一必需方法，其余几十个方法（`map`、`filter`、`fold`、`collect`……）全是带默认实现的派生方法。2021 edition 做了一次重要语义修正：**数组的 `into_iter()`**——2021 之前 `[T; N].into_iter()` 因历史原因产出 `&T`（借用），与 `Vec<T>` 不一致，2021 edition 起修正为按值产出 `T`，与所有集合统一。迭代器在 Rust 生态中处于枢纽地位：所有标准库集合、字符串、范围（`1..10`）、文件行都实现 `IntoIterator`；rayon 的并行迭代器 `par_iter` 和异步 `Stream` 都是 `Iterator` 思路的延伸，本阶段的链式思维在它们身上直接复用。

| 时间 | 里程碑 | 影响 |
|------|--------|------|
| 2009 | Rust 早期设计将迭代器列为核心抽象 | 函数式 list 处理（map/filter/fold）成为语言目标 |
| 2014 | RFC 流程下 `std::iter` 与 `Iterator`/`IntoIterator` trait 定型 | for 循环与适配器链获得统一、可组合的接口 |
| 2015 | Rust 1.0：标准库集合全部实现 `IntoIterator` | "可迭代"成为语言级约定，自定义类型可实现 `Iterator` 接入生态 |
| 2018 | edition 2018：`impl Trait` 稳定 | 迭代器链可直接作为返回值（`impl Iterator`），无需装箱成 `Box<dyn Iterator>` |
| 2021 | edition 2021：数组 `into_iter` 语义修正 | `[T; N].into_iter()` 按值产出元素，与 `Vec` 行为统一 |

## 3. 语法与参数

### 3.1 Iterator trait 与三种迭代方式（iter · iter_mut · into_iter）

`Iterator` trait 的核心只有两点：**关联类型 `Item`**（元素类型）与**方法 `next(&mut self) -> Option<Self::Item>`**（取下一个元素，取完返回 `None`）。其余几十个方法全是基于 `next` 的默认实现——这也是"自定义迭代器只需写 `next`"（见 3.7）的原因。三种迭代方式对应三种所有权进入方式：

```rust
fn main() {
    let mut nums = vec![10, 20, 30];

    let total: i32 = nums.iter().sum();          // iter()：只读借用，元素 &i32，集合保留
    println!("sum = {total}");

    for n in nums.iter_mut() {                   // iter_mut()：可变借用，元素 &mut i32
        *n += 1;
    }
    println!("{nums:?}");                        // [11, 21, 31]

    let consumed: i32 = nums.into_iter().sum();  // into_iter()：消耗集合，元素 i32
    // println!("{nums:?}");                     // E0382：nums 已被消耗
    println!("consumed = {consumed}");
}
```

| 方式 | 元素类型 | 集合去留 | 适用场景 |
|------|---------|---------|---------|
| `iter()` | `&T` | 保留（只读借用） | 统计、查找、遍历不改数据 |
| `iter_mut()` | `&mut T` | 保留（可变借用） | 原地修改每个元素 |
| `into_iter()` | `T` | 消耗（所有权移入迭代器） | 最后一次使用，把元素所有权交给下游 |

要点与坑：
- **`for x in v` 等价于 `for x in v.into_iter()`**：for 循环默认消耗集合；想借用遍历写 `for x in &v`（`iter()`）或 `for x in &mut v`（`iter_mut()`）。
- **坑：iter 与 into_iter 选择错误**——只读统计却写 `into_iter()`，集合被白白消耗（之后无法再用）；元素是 `String` 等非 `Copy` 类型时还意味着所有权被移走。

### 3.2 适配器（map · filter · take · skip · enumerate · zip · chain）

**适配器（adapter）**接收一个迭代器、返回一个新的迭代器，**不执行任何工作**（惰性，见 3.5），是可以无限组合的"积木"：

```rust
fn main() {
    let picked: Vec<i32> = (1..=20)
        .filter(|n| n % 2 == 0)   // 偶数
        .map(|n| n * n)           // 平方
        .take(5)                  // 取前 5 个
        .skip(1)                  // 跳过第 1 个
        .collect();
    println!("{picked:?}");       // [16, 36, 64, 100]

    for (i, ch) in "abc".chars().enumerate() { print!("{i}:{ch} "); } // 0:a 1:b 2:c
    println!();

    let names = ["api", "db", "cache"];
    let ports = [8000u16, 8001, 8002];
    for (name, port) in names.iter().zip(ports.iter()) { // zip：配对，取较短者
        println!("{name} -> {port}");
    }

    let merged: Vec<i32> = vec![1, 2].into_iter().chain(vec![3, 4]).collect();
    println!("{merged:?}");       // [1, 2, 3, 4]
}
```

| 适配器 | 作用 | 典型用法 |
|--------|------|---------|
| `map` | 对每个元素做变换 | `.map(\|n\| n * 2)` |
| `filter` | 保留满足条件的元素 | `.filter(\|n\| *n > 0)` |
| `take(n)` / `skip(n)` | 取前 n 个 / 跳过前 n 个 | 截断、分页 |
| `enumerate` | 附带从 0 开始的下标 | `(i, value)` 成对产出 |
| `zip` | 两个迭代器按位配对 | 名字与端口一一对应 |
| `chain` | 串联两个同类型迭代器 | 拼接两段数据 |

要点与坑：
- **`filter` 的闭包参数是 `&Self::Item`**：对 `iter()`（元素 `&T`）来说就是 `&&T`，写 `|n| **n % 2 == 0` 或模式 `|&&n| n % 2 == 0`；对 `into_iter()` 则是 `|n| n % 2 == 0`。
- **`map` 闭包参数是 `Self::Item` 本身**：`iter()` 时是 `&T`，`into_iter()` 时是 `T`——同一个链式写法在不同迭代器源上语义不同，这是"所有权进入迭代器的方式"（必会概念）的直接体现。

### 3.3 消费器（collect · sum · fold · count · any · all · find · max · min）

**消费器（consumer）**把迭代器"用掉"，触发真正的求值。`sum`/`count`/`any` 等是便捷消费器，`fold` 是它们的通用底座，`collect` 是最常用的收集消费器：

```rust
fn main() {
    let nums = vec![3, 1, 4, 1, 5, 9, 2, 6];

    let sum: i32 = nums.iter().sum();                    // 求和
    let count = nums.iter().count();                     // 计数
    let has_big = nums.iter().any(|n| *n > 8);           // 存在任一满足
    let first_even = nums.iter().find(|n| **n % 2 == 0); // 第一个满足
    let max = nums.iter().max();                         // 最大值

    println!("sum={sum} count={count} any>8={has_big}");
    println!("first_even={first_even:?} max={max:?}");
}
```

| 消费器 | 作用 | 返回 |
|--------|------|------|
| `collect` | 收集成集合（Vec/HashMap/HashSet/String） | 目标集合 |
| `sum` / `product` | 求和 / 求积 | 数值 |
| `fold(init, \|acc, x\| ...)` | 通用折叠聚合 | 任意类型 |
| `count` | 计数 | `usize` |
| `any` / `all` | 存在性 / 全称判断 | `bool` |
| `find` | 找第一个满足条件的元素 | `Option<T>` |
| `max` / `min` | 最大 / 最小元素 | `Option<T>` |

要点与坑：
- **`find`/`max`/`min` 返回 `Option`**：空迭代器没有"第一个"也没有"最值"，必须处理 `None`（ph04 知识在此复用）。
- **`fold` 是"万能消费器"**：`sum`/`count`/`max` 都能用 `fold` 手写（见示例 3）；自定义聚合（同时算多个统计量）用 `fold` 最顺手。

### 3.4 闭包捕获与 Fn / FnMut / FnOnce

闭包会**捕获**（capture）定义处环境中的变量。按捕获方式，编译器把闭包归入三个 trait 之一——这也是 `map`/`filter`/`fold` 对闭包参数约束的理论基础：

```rust
fn main() {
    // Fn：只读捕获（& 借用），可多次调用
    let base = 100;
    let add_base = |x: u32| x + base;
    println!("{} {}", add_base(1), add_base(2)); // 101 102
    println!("base = {base}");                    // 只是借用，仍可用

    // FnMut：可变捕获（&mut 借用），可多次调用且能改状态
    let mut counter = 0;
    let mut bump = || { counter += 1; };
    bump();
    bump();
    println!("counter = {counter}"); // 2

    // FnOnce：按值捕获，把捕获值 move 出去，只能调用一次
    let name = String::from("alice");
    let take = || name;              // name 的所有权进入闭包
    let owned = take();
    // let _again = take();          // E0382：name 已被 move 出，闭包不可复用
    println!("{owned}");
}
```

| Trait | 捕获方式 | 可调用次数 | 代表场景 |
|-------|---------|-----------|---------|
| `FnOnce` | 按值移动（或借用） | 一次 | `into_iter`、把捕获值交出去 |
| `FnMut` | `&mut` 借用 | 多次（可改状态） | 带计数器的闭包、`for_each` |
| `Fn` | `&` 借用 | 多次（只读） | 只读谓词、比较器 |

要点与坑：
- **包含关系：`Fn` ⊆ `FnMut` ⊆ `FnOnce`**：能当 `Fn` 用的闭包也能传给要求 `FnMut`/`FnOnce` 的地方，反之不行——编译器按"闭包实际怎么用捕获变量"自动归类。
- **坑：闭包意外移动**——闭包体内写 `|| name`（返回 `name` 本身）就会按值捕获并 move 出，调用后 `name` 不可再用；只想读它就写 `|| name.len()` 或 `|| name.clone()`；`move` 关键字强制按值捕获（常用于 ph12 跨线程场景）。

### 3.5 惰性求值与链式组合

**惰性求值（lazy evaluation）**：适配器只构建"执行计划"，**不执行任何工作**；只有消费器（`collect`/`sum`/`fold`/for 循环）出现时，元素才被逐一带过整条链。后果：链条再长也零运行时开销（只组合类型），以及**无限迭代器必须用 `take` 限界**：

```rust
fn main() {
    let nums = vec![1, 2, 3, 4, 5];

    // 适配器只构建"执行计划"，不执行任何工作
    let planned = nums.iter().map(|n| {
        println!("map 执行于 {n}");
        n * 10
    });
    println!("链条已构建，map 尚未执行");
    let result: Vec<i32> = planned.collect(); // 消费器触发真正的求值
    println!("result: {result:?}");

    // 坑：无限迭代器 + 无界消费器 = 永不结束
    // let endless: Vec<u32> = (0..).collect(); // 挂死：无限迭代器没有终点
    let first_five: Vec<u32> = (0..).take(5).collect(); // 先用 take 限界再消费
    println!("{first_five:?}"); // [0, 1, 2, 3, 4]
}
```

要点与坑：
- **链式组合的本质是"类型组合"**：每加一个适配器，迭代器类型就嵌套一层（见 4.2）；写长链时关注"每一步输入输出是什么"而不是"中间有多少个临时集合"。
- **坑：无限迭代器**——`(0..)`、`repeat(x)`、`cycle()` 都没有终点，必须 `take(n)` 限界后再消费，否则程序挂死。

### 3.6 collect 到 Vec / HashMap / HashSet / String

`collect` 的完整形态是 `collect::<Target>()` 或 `let target: Target = ...`：**目标类型由标注决定**（`FromIterator` 机制见 4.4）。同一个迭代器可以收集成不同集合：

```rust
use std::collections::{HashMap, HashSet};

fn main() {
    let nums = vec![1, 2, 3, 4, 5, 2, 3];

    let squares: Vec<i32> = nums.iter().map(|n| n * n).collect();                // Vec
    let unique: HashSet<i32> = nums.iter().copied().collect();                   // HashSet（去重）
    let parity: HashMap<i32, i32> = nums.iter().map(|n| (n % 2, *n)).collect();  // HashMap
    let joined: String = ['R', 'u', 's', 't'].into_iter().collect();             // String

    println!("{squares:?}"); // [1, 4, 9, 16, 25, 4, 9]
    println!("{unique:?}");  // {1, 2, 3, 4, 5}
    println!("{parity:?}");  // {0: 2, 1: 3}（键为 0/1，值为最后一个同奇偶的数）
    println!("{joined}");    // Rust
}
```

要点与坑：
- **坑：collect 类型推断失败（E0282）**——不写目标类型直接 `let x = ...collect();` 会报"无法推断类型"；在 `let` 标注或写 `::<Vec<_>>`。看到 E0282 先补类型标注。
- **坑：`iter()` collect 出引用集合**——`nums.iter().collect::<Vec<_>>()` 得到 `Vec<&i32>`，想要拥有值用 `into_iter()` 或 `.copied()`/`.cloned()`；**collect 到 HashMap 的前提是产出 `(K, V)` 元组**，重复键后到者覆盖先者，所以词频统计要用 `entry` API（见 3.9）。

### 3.7 自定义迭代器（实现 Iterator）简介

实现 `Iterator` 只需提供 `Item` 与 `next`，标准库免费送你 `map`/`filter`/`fold`/`take` 等全部方法——你的类型立即"接入生态"。常见做法是定义一个**持有状态**的结构体：

```rust
// 斐波那契数列迭代器：状态就是前两个数（无限迭代器）
struct Fibonacci {
    a: u64,
    b: u64,
}

impl Iterator for Fibonacci {
    type Item = u64;

    fn next(&mut self) -> Option<u64> {
        let next = self.a;
        self.a = self.b;
        self.b = next + self.b;
        Some(next) // 永不返回 None
    }
}

fn main() {
    let first_ten: Vec<u64> = Fibonacci { a: 0, b: 1 }.take(10).collect();
    println!("{first_ten:?}"); // [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
}
```

要点与坑：
- `next` 接收 `&mut self`：迭代器内部状态可变（`a`/`b` 前移）；**有穷迭代器耗尽后要返回 `None`**，`take`/`collect` 等消费器依赖这个约定。
- 无限迭代器（如本示例）必须配合 `take(n)` 使用；`std::iter` 的 `from_fn`/`successors` 可用闭包快速造迭代器，实现 `size_hint` 能让 `collect` 预分配容量。

### 3.8 集合与迭代器的借用（在循环中修改集合）

迭代器持有集合的借用期间，不能对集合做结构性修改（push/remove/insert）——借用规则的直接后果，也是本阶段最常见的借用冲突：

```rust
fn main() {
    let mut nums = vec![1, 2, 3, 4, 5, 6];

    // 方案 1：先收集要加的数据，循环结束后再修改
    let extra: Vec<i32> = nums.iter().map(|n| n * 10).collect();
    nums.extend(extra);
    println!("{nums:?}"); // [1, 2, 3, 4, 5, 6, 10, 20, 30, 40, 50, 60]

    // 方案 2：原地修改用 iter_mut
    for n in nums.iter_mut() {
        *n += 1;
    }
    println!("{nums:?}");

    // 方案 3：按条件删除用 retain（内部封装了安全的"边遍历边删"）
    let mut words = vec![String::from("a"), String::from("bb"), String::from("ccc")];
    words.retain(|w| w.len() >= 2);
    println!("{words:?}"); // ["bb", "ccc"]
}
```

要点与坑：
- **`for n in &nums` 与 `for n in nums.iter()` 完全等价**：循环体里 `nums` 处于借用状态，任何对 `nums` 的可变操作都被拒绝（E0502：`// for n in &nums { nums.push(*n); }`）。
- **删元素不要手写索引循环**：边遍历边 `remove(i)` 会跳过元素、索引错位；用 `retain`（或 `Vec::drain`）表达"保留满足条件的"，或"先算出结果集再一次性修改"。

### 3.9 常见函数式模式（grouping 用 entry API、折叠聚合）

把迭代器思维与集合 API 结合，两类高频模式：

```rust
use std::collections::HashMap;

fn main() {
    let logs = [("api", "INFO"), ("db", "ERROR"), ("api", "ERROR"), ("cache", "INFO"), ("db", "INFO"), ("api", "INFO")];

    // 模式 1：grouping —— entry API 分组计数
    let mut counts: HashMap<&str, u32> = HashMap::new();
    for (source, _level) in logs {
        *counts.entry(source).or_insert(0) += 1;
    }
    println!("{counts:?}"); // {"api": 3, "db": 2, "cache": 1}

    // 模式 2：折叠聚合 —— fold 把序列压成一个值
    let total = [1, 2, 3, 4].iter().fold(0, |acc, n| acc + n);
    println!("total: {total}"); // 10

    // 进阶：fold 直接构建 HashMap（按首字母分组）
    let words = ["apple", "avocado", "banana", "cherry", "blueberry"];
    let buckets: HashMap<char, Vec<&str>> = words.iter().fold(HashMap::new(), |mut acc, w| {
        let initial = w.chars().next().unwrap();
        acc.entry(initial).or_default().push(w);
        acc
    });
    println!("{buckets:?}");
}
```

要点与坑：
- **`entry(key).or_insert(0)` 一次哈希查找完成"取到可变引用"**：配合 `+= 1` 是分组计数的标准写法；`or_default()` 为"不存在就放一个空集合"而设。
- **fold 构建集合时闭包要返回 `acc`**：`fold` 要求"把累加器还给我"，忘记返回 `acc` 是新手最常犯的编译错误；两个模式可嵌套（fold 外层聚合、entry 内层分组，见示例 4）。

## 4. 底层原理

### 4.1 迭代器是零成本抽象（单态化后内联）

"零成本抽象"指：**用迭代器链写的代码与手写 for 循环生成相同的机器码**。`Iterator` 是泛型 trait，`iter()` 与各适配器的返回类型都是**具体的泛型类型**，调用链在编译期被**单态化（monomorphization）**：每个 `next` 内联展开、闭包内联成普通函数体、`filter` 的判断与 `map` 的变换直接在寄存器/栈上流转，**没有虚函数调用、没有中间集合、没有运行时开销**：

```rust
// 下面两种写法编译后的机器码几乎相同（都内联为一个循环）
fn iter_sum(data: &[i32]) -> i32 {
    data.iter().filter(|&&n| n % 2 == 0).sum()
}

fn loop_sum(data: &[i32]) -> i32 {
    let mut s = 0;
    for &n in data {
        if n % 2 == 0 { s += n; }
    }
    s
}

fn main() {
    let v = [1, 2, 3, 4, 5, 6];
    assert_eq!(iter_sum(&v), loop_sum(&v));
    println!("{}", iter_sum(&v)); // 12
}
```

要点与坑：零成本的代价是**类型很长**——链式迭代器的类型是嵌套的（见 4.2），所以返回值常用 `impl Iterator`；`Box<dyn Iterator>` 才是"有运行时开销的迭代器"（虚表分发），只在类型无法静态表达时才用。

### 4.2 适配器的组合结构（嵌套类型，编译器优化消除）

每个适配器都是一个**零大小的包装结构体**：持有"上一个迭代器 + 闭包/参数"。`(1..=20).filter(...).map(...)` 的真实类型是 `Map<Filter<RangeInclusive<i32>, 闭包A>, 闭包B>`——`map` 包住 `filter`，`filter` 包住 `RangeInclusive`。`next()` 被调用时像剥洋葱一样逐层取元素：外层 `next` 调用内层 `next`，**每一层只做自己那一点事，层与层之间没有临时存储**。优化器看到这些零大小包装与内联后的 `next`，会把嵌套"展平"成单个循环。理解这层结构的意义：**链式组合不是"先建集合 A 再建集合 B"，而是类型层面的叠加**，链条长短不增加运行时代价，只增加编译期类型复杂度。

### 4.3 闭包捕获的三种模式与所有权转移

闭包的底层实现是一个**匿名结构体（环境，environment）**，捕获的变量成为它的字段；捕获方式决定字段类型：

| 捕获方式 | 环境字段 | trait 归类 |
|---------|---------|-----------|
| 按引用（只读） | `&T` | `Fn` |
| 按可变引用 | `&mut T` | `FnMut` |
| 按值（move） | `T` | `FnOnce`（若 move 出则仅此） |

`map`/`filter` 等适配器要求闭包参数是 `FnMut`（要多次调用）；`Fn` 自动满足 `FnMut`，所以只读谓词随便写；一旦闭包**把捕获值 move 出环境**（如 `|| name`），它只能实现 `FnOnce`，传给要求 `FnMut` 的适配器会报 E0525。所有权转移的完整链条是：`into_iter()` 把元素所有权移进迭代器 → 消费器逐元素取出 → 闭包按需捕获/移动——**每一步的"谁拥有数据"都由类型系统钉死**，这正是"所有权进入迭代器的方式"（必会概念）的含义。

### 4.4 collect 的 FromIterator 机制

`collect` 的方法签名是 `fn collect<B: FromIterator<Self::Item>>(self) -> B`：把"迭代器的每一项"喂给 `B::from_iter`，由**目标类型自己定义如何构造**：

| 目标类型 | from_iter 的行为 | 前置要求 |
|---------|-----------------|---------|
| `Vec<T>` | 依次 push | 任意 `Item` |
| `HashSet<T>` | 依次 insert（自动去重） | `Item: Hash + Eq` |
| `HashMap<K, V>` | 依次 insert（重复键覆盖） | `Item = (K, V)` |
| `String` | 拼接 | `Item = char` 或 `&str` |
| `Option<T>` / `Result<T, E>` | 短路收集 | `Item = Option<T>` / `Result<T, E>` |

这就是为什么 `collect` 必须写类型标注：**目标类型决定语义**，编译器无法从"把元素收集起来"推断出该收集成什么。注意 `String` 的 `FromIterator<char>` 与 `Vec<char>` 的差异：同样是字符迭代器，标注不同结果不同。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 批量数据转换（数组/列表 → 变换后的新集合） | `map` + `collect` 到 Vec |
| 数据过滤与截断（保留满足条件的记录、取 Top-N） | `filter`、`take`、`skip` |
| 统计聚合（求和、均值、最值、计数） | `sum`、`fold`、`count`、`max`/`min` |
| 词频统计、按字段分组 | `collect` 到 HashMap + `entry` API |
| 流式处理日志/文件行（逐行过滤 + 聚合） | `lines()` + 迭代器链（示例 4） |
| 原地更新集合元素（批量改字段、统一加分） | `iter_mut()` |
| 构造去重集合与映射表 | `collect` 到 `HashSet` / `HashMap` |
| 遍历两个集合的配对关系（端口↔服务、键↔值） | `zip`、`enumerate` |

**不适合**此阶段的事项：
- 智能指针组合（`Box`/`Rc`/`Arc`/`RefCell`，ph10）：迭代器返回共享引用、内部可变等需要它们，本阶段只用借用。
- 错误处理工程化（ph11）：`collect::<Result<Vec<_>, _>>()` 短路收集、迭代器中的 `?` 等错误组合子属于下一阶段。
- 并发与异步流（ph12）：rayon 并行迭代器、`Stream`（迭代器的异步版）、借用跨 `.await` 的限制均未涉及；宏展开（ph15）同样不涉及。

## 6. 代码示例

### 示例 1：用迭代器重写 for 循环统计（map/filter/fold 版本）

roadmap 练习"用迭代器重写 for 循环统计"的标准题：统计及格人数与平均分，先写命令式版本再替换成迭代器：

```rust
fn main() {
    let scores = vec![72, 88, 95, 41, 60, 100, 33];

    // 命令式版本：for 循环 + 可变累加器
    let mut pass_count = 0;
    let mut total = 0;
    for &s in &scores { if s >= 60 { pass_count += 1; total += s; } }
    println!("命令式: 及格 {pass_count} 人, 平均 {:.1}", total as f64 / pass_count as f64);

    // 迭代器版本 1：filter + count / sum
    let pass_count2 = scores.iter().filter(|&&s| s >= 60).count();
    let total2: i32 = scores.iter().filter(|&&s| s >= 60).sum();
    println!("迭代器: 及格 {pass_count2} 人, 平均 {:.1}", total2 as f64 / pass_count2 as f64);

    // 迭代器版本 2：一个 fold 同时算两个统计量（只遍历一次）
    let (cnt, sum) = scores.iter().filter(|&&s| s >= 60)
        .fold((0, 0), |(cnt, sum), &s| (cnt + 1, sum + s));
    println!("fold:   及格 {cnt} 人, 平均 {:.1}", sum as f64 / cnt as f64);
}
```

要点与坑：
- `filter(|&&s| s >= 60)` 中谓词收到 `&&i32`，用模式 `&&s` 一次剥掉两层引用；`fold` 累加闭包收到 `&i32`，用 `&s` 解构。
- **一个 `fold` 同时算多个统计量**（人数 + 总分），只遍历一次——迭代器版本消灭了 `mut` 累加器与"先初始化再循环"的样板。

### 示例 2：collect 到 Vec 和 HashMap（分组统计词频）

roadmap 练习"练习 collect 到 Vec 和 HashMap"：`(K, V)` 对可直接收集成 `HashMap`，重复键需要 `entry` API 累加：

```rust
use std::collections::HashMap;

fn main() {
    let text = "the quick brown fox jumps over the lazy dog the fox";

    // collect 到 Vec：分词
    let words: Vec<&str> = text.split_whitespace().collect();

    // (键, 值) 对组成的迭代器可以直接 collect 到 HashMap
    let lengths: HashMap<&str, usize> = words.iter().map(|w| (*w, w.len())).collect();
    println!("lengths: {lengths:?}");

    // 词频统计：重复键不能裸 collect（后者会覆盖），用 entry API 累加
    let mut freq: HashMap<&str, u32> = HashMap::new();
    for w in words {
        *freq.entry(w).or_insert(0) += 1;
    }

    // 按词频降序输出
    let mut ranking: Vec<(&str, u32)> = freq.into_iter().collect();
    ranking.sort_by(|a, b| b.1.cmp(&a.1));
    for (word, count) in &ranking {
        println!("{word}: {count}");
    }
}
```

要点与坑：
- **`collect` 到 HashMap 的两个前提**：迭代器产出 `(K, V)` 元组、目标类型标注（`HashMap<&str, usize>`）——缺一不可；**裸 collect 遇到重复键会覆盖**，词频必须用 `entry(key).or_insert(0) += 1` 累加。
- `freq.into_iter().collect::<Vec<_>>()` 把 HashMap 转成可排序的 `(K, V)` 列表，配合 `sort_by` 得到排行榜——"集合 ↔ 迭代器 ↔ 集合"的转换是日常操作。

### 示例 3：用 fold 实现聚合（sum/自定义聚合）

roadmap 练习"用 fold 实现聚合"：`fold` 是万能聚合器，`sum`/`count`/`max` 都是它的特例；自定义聚合（同时算多个统计量、构建集合）用 `fold`：

```rust
use std::collections::HashMap;

fn main() {
    let nums = [3, 1, 4, 1, 5, 9, 2, 6];

    // 自定义聚合：一个 fold 同时求最大、最小、个数
    let (max, min, count) = nums.iter().fold(
        (i32::MIN, i32::MAX, 0),
        |(mx, mn, cnt), &n| (mx.max(n), mn.min(n), cnt + 1),
    );
    println!("max={max} min={min} count={count}");

    // 用 fold 构建 HashMap：词频统计的纯函数式版本
    let words = ["rust", "go", "rust", "c", "rust", "go"];
    let freq: HashMap<&str, u32> = words.iter().fold(HashMap::new(), |mut acc, w| {
        *acc.entry(w).or_insert(0) += 1;
        acc
    });
    println!("{freq:?}"); // {"rust": 3, "go": 2, "c": 1}

    // sum 只是 fold 的特例：fold(0, |acc, n| acc + n)
    let sum_fold = nums.iter().fold(0, |acc, n| acc + n);
    println!("sum via fold: {sum_fold}"); // 31
}
```

要点与坑：
- **`fold(init, |acc, x| new_acc)` 的三要素**：初始值（决定累加器类型）、折叠函数（返回新累加器）、累加器贯穿全程——`sum`/`count` 只是"acc 是数值"的特例。
- **坑：fold 构建集合时忘记返回 `acc`**——闭包必须把累加器"还回去"（`acc` 作为最后一行），否则类型不匹配。

### 示例 4：日志数据聚合器（过滤异常记录 + 错误分布/延迟分布/来源统计）

roadmap 推荐项目"**日志数据聚合器**"：过滤异常记录，并计算错误分布、延迟分布和来源统计。综合运用 filter/map/fold/entry API：

```rust
use std::collections::HashMap;

// 一条日志：来源、级别、耗时（毫秒）
#[derive(Debug)]
struct LogEntry {
    source: &'static str,
    level: &'static str,
    latency_ms: u32,
}

fn main() {
    let logs = vec![
        LogEntry { source: "api", level: "ERROR", latency_ms: 512 },
        LogEntry { source: "db", level: "ERROR", latency_ms: 3200 },
        LogEntry { source: "cache", level: "ERROR", latency_ms: 88 },
        LogEntry { source: "api", level: "WARN", latency_ms: 240 },
        LogEntry { source: "api", level: "INFO", latency_ms: 12 },
        LogEntry { source: "db", level: "INFO", latency_ms: 3 },
        LogEntry { source: "cache", level: "INFO", latency_ms: 1 },
    ];

    // 1) 过滤异常记录：非 INFO 级别，或延迟超过 500ms
    let abnormal: Vec<&LogEntry> = logs
        .iter()
        .filter(|e| e.level != "INFO" || e.latency_ms > 500)
        .collect();
    println!("异常记录 {} 条", abnormal.len());

    // 2) 错误分布：按级别分组计数（entry API）
    let mut by_level: HashMap<&str, u32> = HashMap::new();
    for e in &abnormal {
        *by_level.entry(e.level).or_insert(0) += 1;
    }
    println!("错误分布: {by_level:?}");

    // 3) 延迟分布：map 把延迟映射到分档，再分组计数
    let mut lat_dist: HashMap<&str, u32> = HashMap::new();
    for b in abnormal.iter().map(|e| match e.latency_ms {
        ..=100 => "<=100ms",
        101..=1000 => "101ms-1s",
        _ => ">1s",
    }) {
        *lat_dist.entry(b).or_insert(0) += 1;
    }
    println!("延迟分布: {lat_dist:?}");

    // 4) 来源统计：fold 聚合每个来源的异常条数与平均延迟
    let source_stats: HashMap<&str, (u32, u64)> = abnormal
        .iter()
        .fold(HashMap::new(), |mut acc, e| {
            let stat = acc.entry(e.source).or_insert((0, 0));
            stat.0 += 1;
            stat.1 += e.latency_ms as u64;
            acc
        });
    let mut rows: Vec<(&str, u32, f64)> = source_stats
        .into_iter()
        .map(|(src, (cnt, total))| (src, cnt, total as f64 / cnt as f64))
        .collect();
    rows.sort_by(|a, b| b.1.cmp(&a.1));
    for (src, cnt, avg) in rows {
        println!("{src}: 异常 {cnt} 条, 平均延迟 {avg:.1}ms");
    }
}
```

要点与坑：
- 四步聚合共用一条 `abnormal`（`Vec<&LogEntry>`，零拷贝借用）：**过滤 → 分组 → 映射分档 → 折叠**，覆盖本阶段所有必会概念。
- **`map` 产出"分档标签"再分组**是延迟分布的标准套路；`fold` 的累加器是 `HashMap<&str, (u32, u64)>`（条数 + 总延迟）。扩展方向（ph13）：`read_to_string` 读真实日志、`lines()` 逐行解析、输出 CSV。

### 示例 5：闭包捕获三种模式演示（Fn/FnMut/FnOnce 的编译行为）

roadmap 必会概念"闭包 Fn/FnMut/FnOnce"与阶段验收"不会因闭包捕获造成意外移动"的验证题。用三个泛型函数把三种 trait 约束"钉死"，观察编译行为：

```rust
// 三个泛型函数把三种闭包 trait 约束"钉死"：
fn run_once<F: FnOnce() -> String>(f: F) -> String { f() } // 可 move 出捕获值，只能一次
fn run_mut<F: FnMut()>(mut f: F) { f(); f(); }             // 可改捕获变量，可多次
fn run_fn<F: Fn() -> u32>(f: F) -> u32 { f() + f() }       // 只读捕获，可多次

fn main() {
    // FnOnce：|| tag2 按值捕获——调用后 tag2 的所有权被移出（意外移动的现场）
    let tag2 = String::from("v2");
    let moved = run_once(|| tag2);
    // println!("{tag2}"); // E0382：use of moved value
    println!("{moved}");

    // FnMut：计数器闭包被调用两次
    let mut counter = 0;
    run_mut(|| counter += 1);
    println!("counter = {counter}"); // 2

    // Fn：只读闭包；Fn ⊆ FnMut ⊆ FnOnce，所以也能传给 run_once
    let base = 100;
    println!("run_fn: {}", run_fn(|| base + 1));      // (101) + (101) = 202
    println!("run_once: {}", run_once(|| format!("tag-{base}"))); // 借用捕获也满足 FnOnce
    println!("base = {base}");                        // 只借用，未移动
}
```

要点与坑：
- **同一条 `println!("{tag2}")` 报 E0382**：`|| tag2` 把 `tag2` 按值捕获（move 进闭包环境），调用时所有权跟着返回值移出——之后任何使用都失败。**想只读就写 `|| tag2.len()` 或 `|| tag2.clone()`**。
- 三种 trait 是"能力"而非"标签"：编译器按闭包体对捕获变量的使用方式自动归类；`Fn` 闭包能传给要求 `FnMut`/`FnOnce` 的位置（子集关系），反之不行（把 `FnOnce` 闭包传给要求 `FnMut` 的 `map` 会报 E0525）。

## 7. 总结

### 关键要点

1. **迭代器 = `Item` + `next`**：`Iterator` trait 只有这两个必需元素，其余几十个方法全是基于 `next` 的默认实现——自定义迭代器只需写 `next`。
2. **三种迭代方式对应三种所有权**：`iter()`（`&T`，集合保留）、`iter_mut()`（`&mut T`，原地改）、`into_iter()`（`T`，集合被消耗）；`for x in v` 等价于 `for x in v.into_iter()`。
3. **适配器惰性、消费器触发**：`map`/`filter`/`take` 只组合"执行计划"，`collect`/`sum`/`fold` 才真正求值；无限迭代器必须用 `take` 限界；`filter` 谓词收到 `&Self::Item`（`iter()` 时是 `&&T`）。
4. **collect 的目标类型由标注决定**（E0282 补标注）；产出 `(K, V)` 对才能收集成 `HashMap`，重复键会覆盖，词频用 `entry` API。
5. **fold 是万能聚合器**：`sum`/`count`/`max` 都是特例；累加器可以是数值、元组（多统计量）或集合（fold 构建 HashMap），闭包记得返回 `acc`。
6. **闭包捕获三模式**：`Fn`（`&` 捕获）、`FnMut`（`&mut` 捕获）、`FnOnce`（按值捕获），且 `Fn ⊆ FnMut ⊆ FnOnce`；`|| name` 会把 `name` move 出环境（意外移动）。
7. **借用冲突在迭代器中同样成立**：迭代器持有集合借用期间不能 push/remove；先收集后修改、`iter_mut` 原地改、`retain` 安全删除是三种解法。
8. **零成本抽象**：迭代器链单态化内联成与手写循环相同的机器码，适配器是零大小嵌套类型；只有 `Box<dyn Iterator>` 才引入虚表开销。
9. **分组统计的标准套路**：`entry(key).or_insert(0) += 1` 一次哈希查找完成计数；`map` 分档 + `entry` 计数得到分布。

### 跨语言对比：函数式集合处理

| 维度 | Rust Iterator | Python 推导式 | Java Stream | C++ ranges | JS 数组方法 |
|------|---------------|---------------|-------------|-----------|-------------|
| 惰性求值 | 默认惰性，消费器触发 | 推导式急切求值 | 惰性，终端操作触发 | 惰性（view） | 数组方法急切 |
| 链式组合 | `.map().filter().collect()` | 推导式嵌套/生成器 | `.map().filter().collect()` | 视图组合 `\|` | `.map().filter().reduce()` |
| 类型安全 | 编译期类型推导 + 借用检查 | 动态类型 | 泛型编译期检查 | 模板编译期检查 | 动态类型 |
| 并行支持 | rayon `par_iter`（生态） | 无 | `parallelStream` | 无（需适配） | 无 |
| 运行时开销 | 零成本（单态化内联） | 解释执行 | 中间对象/装箱开销 | 零成本 | 函数调用开销 |
| 典型聚合 | `fold`/`sum`/`collect` | `sum`/推导式 | `reduce`/`collect` | `fold` | `reduce`/`join` |

### 阶段验收标准

- 能根据场景选择 `iter`、`iter_mut`、`into_iter`，并说出各自的元素类型与集合的去留。
- 能读懂常见链式迭代器（map/filter/fold/collect 组合）：说出每一步的输入、输出与是否消耗。
- 不会因闭包捕获造成意外移动：能判断闭包是按值、`&mut` 还是 `&` 捕获，以及调用后捕获变量是否还能用。
- 能解释惰性求值与零成本抽象：适配器不执行、消费器触发；迭代器链编译后与手写循环等价。
- 能说出 `filter` 谓词收到 `&Self::Item`（`&&T`）与 `collect` 需要类型标注的原因。

### 进入下一阶段前

确保能完成以下练习：

- 用迭代器重写 for 循环统计（提示：`for` 累加 → `iter().filter().sum()/count()`，一个 `fold` 同时算多统计量；对照示例 1）。
- 练习 collect 到 Vec 和 HashMap（提示：`(K, V)` 对组成的迭代器可直接 collect 到 `HashMap`；词频统计用 `entry` API 而非裸 collect；对照示例 2）。
- 用 fold 实现聚合（提示：`fold(初始值, |acc, x| ...)`，累加器可以是元组或集合；对照示例 3）。
- 制造并修复一次"闭包意外移动"（提示：闭包里写 `|| name` 而不是 `|| name.len()`，观察 E0382 与 E0525；对照示例 5）。
- 口述一段迭代器链的行为（提示：从示例 4 的日志聚合器任选一段，说出 filter/map/fold 每一步的输入输出与所有权）。

### 推荐项目

- **日志数据聚合器**（roadmap 推荐项目）：过滤异常记录，并计算错误分布、延迟分布和来源统计。示例 4 已给出核心实现。扩展方向：改用 `lines()` 解析真实日志文件（ph13）、把来源统计做成"来源 → 异常条数 / 平均延迟"的排序报表、增加时间窗口滑动聚合。

### 下一阶段

[智能指针阶段](../ph10-smart-pointers/10-smart-pointers.md) —— Box/Rc/Arc/RefCell、内部可变性、循环引用与 Weak、自定义 Drop。迭代器阶段学会了"用借用安全地遍历与转换"，智能指针阶段则回答"数据需要共享/可变/跨线程时怎么办"：`Rc`/`Arc` 让迭代器可以产出共享引用，`RefCell` 把借用检查从编译期挪到运行期，`Box<dyn Iterator>` 让无法静态书写的迭代器链也能装箱传递——两个阶段的知识将在所有权模型中汇合。
