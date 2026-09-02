# Rust Trait 与泛型阶段

> 从"具体类型"到"行为抽象"的跨越：trait 定义"能做什么"，泛型把同一份逻辑复用到任意满足约束的类型上——面向数据基础设施与异步网络服务方向，本阶段用 trait 和泛型抽象行为，同时保持类型安全和零成本抽象。

## 1. 概述

Trait 与泛型阶段的定位是：**能用 trait 定义行为契约（"能做什么"）并为多个类型实现它，用泛型函数与泛型结构体写出适用于多种类型的一次性代码，用 trait bound / where 子句约束类型参数的能力边界，理解静态分发与动态分发的取舍，并保持类型安全与零成本抽象**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| trait 定义与实现 | trait 声明、impl 实现、默认方法、方法名冲突 |
| 泛型函数与结构体 | `<T>` 类型参数、泛型函数、泛型结构体与枚举 |
| trait bound 与 where 子句 | `T: Trait`、`+` 组合多约束、where 整理复杂签名 |
| impl Trait | 参数位置匿名泛型、返回值位置不透明类型 |
| 常见 derive trait | Debug、Clone、PartialEq、Eq、Hash 一行生成 |
| 孤儿规则 | 外部 trait × 外部类型禁止 impl，避免全局冲突 |
| 静态分发与单态化 | 编译期为每种类型生成专用代码，零运行时开销 |
| trait 对象与对象安全初步 | dyn Trait、vtable、对象安全条件、异构集合 |

**本阶段边界**：承接 ph06 模块化与 Cargo（本阶段示例按 crate 组织，先建立模块再抽象行为）；不展开生命周期标注深入（ph08）、trait 对象与 dyn 的深入用法（ph08+）、闭包与迭代器深入（ph09）、异步 trait（ph12）、宏与过程宏（[ph15 宏与元编程阶段](../ph15-macros-metaprogramming/15-macros-metaprogramming.md)，本阶段只"用"derive）。

## 2. 来源与演变

trait 的设计直接继承 Haskell 的 **typeclass** 传统（为不同类型提供同一组操作，如 `Show`、`Eq`），但用**孤儿规则（Orphan Rule）与相干性（coherence）**收紧了自由度——同一对 (trait, type) 的实现全程序唯一，这是 trait 与 Java 接口最根本的差异之一。

泛型部分继承 C++ 模板的静态分发思路——编译期实例化（**单态化 monomorphization**），但加上 trait bound 的编译期检查，把模板"实例化时才发现错误"提前到"声明时就检查"。2018 edition 引入 `dyn` 关键字把动态分发显式化：`Box<Trait>` 改为 `Box<dyn Trait>`。

`impl Trait` 的演进值得关注：Rust 1.26 稳定参数与返回值位置的 `impl Trait`；Rust 1.75 稳定 RPITIT（trait 方法返回值位置的 impl Trait），让"返回迭代器"能写进 trait 方法，为 ph12 异步 trait 铺路。

本文示例以 **Edition 2021** 为基线（`impl Trait` 自 1.26 起、`dyn` 显式化自 2018 起），验证工具链 rustc/cargo 1.92.0。

| 时间 | 里程碑 | 影响 |
|------|--------|------|
| 2015 | Rust 1.0：trait 与泛型随语言稳定 | 语法、孤儿规则、静态分发基础成型 |
| 2018 | Edition 2018：`dyn` 关键字 | 动态分发显式化，裸 trait 对象写法淘汰 |
| 2018 | Rust 1.26：impl Trait 稳定 | 参数/返回值位置的匿名类型 |
| 2022 | Rust 1.65：GAT（泛型关联类型）稳定 | 更高级的类型级抽象（拓展内容） |
| 2023 | Rust 1.75：RPITIT | trait 方法返回值位置 impl Trait，可返回迭代器 |

## 3. 语法与参数

### 3.1 trait 定义与实现（方法、默认实现）

**trait 是一组方法签名的契约**：声明"这种类型能做什么"，但不关心"怎么做"。用 `impl Trait for Type` 为具体类型实现：

```rust
trait Describable {
    fn describe(&self) -> String;          // 只有签名：实现者必须提供
    fn summary(&self) -> String {          // 默认实现：实现者可以覆盖
        format!("[{}]", self.describe())
    }
}
struct Server { name: String }
impl Describable for Server {
    fn describe(&self) -> String { format!("server:{}", self.name) }
}
fn main() {
    let s = Server { name: String::from("db-01") };
    println!("{}", s.describe()); // server:db-01（自己的实现）
    println!("{}", s.summary());  // [server:db-01]（默认实现）
}
```
要点与坑：
- trait 与 Java 接口的关键区别：**可以带默认实现**，且实现是"显式的"——类型不会隐式满足 trait（对比 Go 的结构类型，见第七节）。
- **坑：trait 方法名冲突**——两个 trait 定义同名方法时，直接调用 `x.tag()` 报歧义错误（E0034），用**完全限定语法（fully qualified syntax）**消除：
```rust
trait A { fn tag(&self) -> String; }
trait B { fn tag(&self) -> String; }
struct X;
impl A for X { fn tag(&self) -> String { String::from("a") } }
impl B for X { fn tag(&self) -> String { String::from("b") } }
fn main() {
    let x = X;
    println!("{}", <X as A>::tag(&x)); // 完全限定语法：指定 trait 与方法
    println!("{}", <X as B>::tag(&x));
}
```

### 3.2 泛型函数与结构体（<T>）

**泛型（generics）**用类型参数 `<T>` 把"具体类型"替换成"任意类型"，一份代码适用多种类型。`Option<T>`、`Result<T, E>`、`Vec<T>`、`HashMap<K, V>` 全部是泛型：

```rust
struct Pair<A, B> {
    first: A,
    second: B,
}
fn first_of<A, B>(pair: &Pair<A, B>) -> &A {
    &pair.first
}
fn main() {
    let p = Pair { first: 10u32, second: 20u32 };
    println!("first: {}", first_of(&p));
    let mixed = Pair { first: String::from("x"), second: 3.14 };
    println!("second: {}", mixed.second);
}
```
要点：
- 类型参数在调用点由编译器**推断**，也可显式标注：`first_of::<u32, u32>(&p)`。
- **坑：未使用的类型参数**——声明了类型参数但字段用不到，报 `E0392`（unused type parameter）；真需要"只占位"时用 `PhantomData`（ph10 展开）。
- 泛型 impl 块：`impl<A, B> Pair<A, B> { ... }`，只有涉及类型参数的方法需要写 `<A, B>`。

### 3.3 trait bound 与 where 子句

泛型参数不能无约束地使用——**trait bound（trait 约束）**声明"T 必须实现了某个 trait 才能这样用"。写法两种：内联 `T: Trait` 与 **where 子句**（约束多、签名长时更可读）：

```rust
use std::fmt::Display;
fn print_twice<T: Display>(value: T) {       // 内联 bound
    println!("{} {}", value, value);
}
fn describe<T>(value: T) -> String           // where 子句：等价写法
where
    T: Display,
{
    format!("value = {value}")
}
fn main() {
    print_twice(42);                          // i32 满足 Display
    print_twice(String::from("hello"));       // String 满足 Display
    println!("{}", describe(3.14));
}
```
要点与坑：
- **多约束用 `+` 组合**：`T: Clone + Display + PartialOrd`。
- **坑：bound 不足**——泛型函数里调用 `value.max(other)` 但只约束了 `T: Display`，报 `E0599`（method not found）；补齐 `T: PartialOrd` 即可。
- 泛型参数的"能力"完全由 bound 决定，这正是类型安全的来源：**不满足 bound 的调用点在编译期就报错**（如 `print_twice(vec![1, 2])` 报 E0277）。
- 想用 `{:?}` 打印必须加 `T: Debug` 约束——最常见的初学者错误。

### 3.4 impl Trait 参数与返回值

**`impl Trait`** 是"匿名泛型"：`fn f(x: impl Display)` 等价于 `fn f<T: Display>(x: T)` 但无需命名类型参数。返回值位置的 `impl Trait` 是**不透明类型（opaque type）**：调用者只知道返回类型实现了 Trait，不知道具体类型：

```rust
use std::fmt::Display;
fn greet(name: impl Display) -> String {            // 参数位置：匿名泛型
    format!("hello, {name}!")
}
fn make_double(value: impl Display + Clone) -> impl Display {  // 返回位置：不透明类型
    let s = value.to_string();
    format!("{s}{s}")
}
fn main() {
    println!("{}", greet("rust"));
    println!("{}", make_double(7));
}
```
要点与坑：
- 参数位置与 `<T: Trait>` 完全等价，纯粹是语法糖；返回位置语义不同——泛型返回类型由**调用者**决定，`impl Trait` 返回类型由**实现者**决定。
- **坑：返回位置必须返回单一具体类型**——`if cond { a } else { b }` 两个分支返回不同类型（哪怕都实现同一 trait）会报 `E0308`；此时需要 `Box<dyn Trait>`（3.8）。
- `impl Trait` 不能用作结构体字段（用泛型或 `Box<dyn>`），与生命周期的组合见 ph08。

### 3.5 常见 derive trait（Debug / Clone / PartialEq / Hash）

`#[derive(...)]` 让编译器**自动生成** trait 实现，省去大量 boilerplate：
| derive trait | 生成的能力 | 必要条件 |
|-------------|-----------|---------|
| `Debug` | `{:?}` 格式化输出 | 所有字段实现 Debug |
| `Clone` | `.clone()` 深拷贝 | 所有字段实现 Clone |
| `PartialEq` | `==` / `!=` | 所有字段实现 PartialEq |
| `Eq` | 等价关系（配合 PartialEq） | 需先有 PartialEq |
| `Hash` | 供 HashMap / HashSet 作 key | 所有字段实现 Hash |

```rust
use std::collections::HashSet;
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
struct DocId { shard: u32, seq: u64 }
fn main() {
    let id = DocId { shard: 1, seq: 42 };
    let copy = id.clone();                                  // Clone
    println!("{:?} == {:?} -> {}", id, copy, id == copy);   // Debug + PartialEq
    let mut set = HashSet::new();                           // Hash + Eq：可作 key
    set.insert(id);
    set.insert(DocId { shard: 1, seq: 43 });
    println!("set size: {}", set.len());
}
```
要点与坑：
- **坑：derive 条件传递**——字段包含 `f64` 时不能 derive `Eq`/`Hash`（浮点没有全序、哈希不稳定），只保留 `PartialEq`。
- derive 只适合"逐字段实现"的简单情况；自定义比较/哈希逻辑必须手写 impl（见示例 5）。
- `PartialEq` 与 `Eq` 的区别：`Eq` 是自反等价关系，HashMap key 需要 `Eq + Hash`；`f64` 有 `PartialEq` 但没有 `Eq`。

### 3.6 孤儿规则（Orphan Rule）

**孤儿规则**：`impl Trait for Type` 中，trait 与类型**至少有一个**必须定义在当前 crate——你不能为外部类型实现外部 trait：

```rust
struct LocalType;   // 本地类型
// 合法：本地 trait × 本地类型
trait LocalTrait { fn tag(&self) -> &'static str; }
impl LocalTrait for LocalType {
    fn tag(&self) -> &'static str { "local" }
}
// 合法：外部 trait × 本地类型（至少一个是本地的即可）
impl std::fmt::Display for LocalType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "LocalType")
    }
}
fn main() {
    let t = LocalType;
    println!("{} / {}", t.tag(), t);
}
```
要点与坑：
- **坑：`impl Display for Vec<MyType>` 非法**（E0117）——Vec 是外部类型、Display 是外部 trait，两者都不属于当前 crate。为外部类型补能力只能用 **newtype 模式**：`struct MyVec(Vec<MyType>);` 再为 MyVec 实现（ph10 深化）。
- 孤儿规则让 trait 的实现"有唯一归属"，避免两个 crate 对同一 (trait, type) 给出冲突实现（原理见 4.3）。

### 3.7 静态分发与单态化初步

调用泛型函数时，编译器为**每一组具体类型参数生成一份专用代码**——这就是**静态分发（static dispatch）**与**单态化（monomorphization）**：

```rust
fn largest<T: PartialOrd>(items: &[T]) -> Option<&T> {
    items.iter().max_by(|a, b| a.partial_cmp(b).unwrap())
}
fn main() {
    println!("{}", largest(&[3u32, 9, 5]).unwrap());            // 生成 u32 版本
    println!("{}", largest(&[1.5f64, -2.0, 3.25]).unwrap());    // 生成 f64 版本
    println!("{}", largest(&["rust", "go", "python"]).unwrap()); // 生成 &str 版本
}
```
要点：
- `largest` 只有一份源码，编译产物里却有三份机器码——这就是"**零成本抽象**"：没有运行时查找，还能各自内联优化。
- **代价是代码膨胀（code bloat）**：类型组合越多二进制越大；极端场景可用动态分发（3.8）缓解，原理对比见 4.1/4.2。

### 3.8 trait 对象与对象安全初步（dyn Trait）

当需要"不同类型的值放进同一个集合、用同一套方法"时，泛型（类型编译期确定）就不够了——需要 **trait 对象（trait object）** `dyn Trait`，运行时通过 vtable 动态分发：

```rust
trait Shape {
    fn area(&self) -> f64;
    fn name(&self) -> &'static str;
}
struct Circle { r: f64 }
struct Square { side: f64 }
impl Shape for Circle {
    fn area(&self) -> f64 { std::f64::consts::PI * self.r * self.r }
    fn name(&self) -> &'static str { "circle" }
}
impl Shape for Square {
    fn area(&self) -> f64 { self.side * self.side }
    fn name(&self) -> &'static str { "square" }
}
fn print_area(shape: &dyn Shape) {
    println!("{} area: {:.2}", shape.name(), shape.area());
}
fn main() {
    let shapes: Vec<Box<dyn Shape>> = vec![          // 异构集合
        Box::new(Circle { r: 1.0 }),
        Box::new(Square { side: 2.0 }),
    ];
    for s in &shapes { print_area(s.as_ref()); }     // Box<dyn Shape> -> &dyn Shape
}
```
要点与坑：
- `dyn Trait` 必须放在指针后面（`&dyn`、`Box<dyn>`、`Rc<dyn>`），因为 trait 对象大小未知（unsized）。
- **坑：对象安全（object safety）**——方法带**泛型参数**、返回 `Self`、或接收者不是 `self`/`&self`/`&mut self` 的 trait 不能当 trait 对象，`Box<dyn 该trait>` 报 `E0038`。判断标准：**trait 的所有方法都必须能通过 vtable 调用**。
- 何时用 dyn：确实需要异构集合/运行时多态时；能用泛型就用泛型（性能与内联更好）。

### 3.9 关联类型与运算符重载 trait 初步

**关联类型（associated type）**：trait 内部声明一个"由实现者决定"的类型占位符（`Iterator` 的 `Item` 是最著名的例子）。**运算符重载**本质是标准库 trait：`+` 是 `Add`、`*` 是 `Mul`：

```rust
use std::ops::Add;
trait Summary {
    type Item;                     // 关联类型：实现者决定
    fn first(&self) -> Option<&Self::Item>;
}
struct Wrapper(Vec<i32>);
impl Summary for Wrapper {
    type Item = i32;
    fn first(&self) -> Option<&i32> { self.0.first() }
}
#[derive(Debug, Clone, Copy, PartialEq)]
struct Metric { value: f64 }
impl Add for Metric {              // 运算符重载：实现 Add trait
    type Output = Metric;
    fn add(self, other: Metric) -> Metric { Metric { value: self.value + other.value } }
}
fn main() {
    let w = Wrapper(vec![10, 20, 30]);
    println!("first: {:?}", w.first());          // 关联类型：&i32
    let a = Metric { value: 1.5 };
    let b = Metric { value: 2.5 };
    println!("a + b = {:?}", a + b);             // 运算符重载
}
```
要点：
- 关联类型 vs 泛型参数：同一 trait 只能有一个 `type Item`（实现者固定），而泛型参数可让一个类型多次实现同一 trait（如 `From<T>`）。需要"每次实现都换类型"用泛型，需要"与类型强绑定"用关联类型。
- 常用运算符 trait：`Add`/`Sub`/`Mul`/`Div`（算术）、`Neg`（一元负）、`Index`（`v[i]`）、`Display`/`ToString`（格式化）。

## 4. 底层原理

### 4.1 单态化（monomorphization）与静态分发的零成本实现

泛型代码在编译期经历"复制 + 替换"：对每一组具体类型参数，编译器把 `<T>` 替换成具体类型、生成一份专用机器码。`largest::<u32>` 与 `largest::<f64>` 是**两个不同的函数**，调用点直接调用对应版本——没有虚表、没有间接跳转，这就是"零成本"：甚至可以被内联，达到手写专用函数的性能。代价是**代码膨胀**：`HashMap<String, Vec<u8>>` 与 `HashMap<u64, f64>` 各有一份完整实现。缓解：核心逻辑放非泛型函数、泛型只做薄封装，或用 trait 对象（4.2）把类型变化推迟到运行时。

### 4.2 trait 对象（dyn）的 vtable 与动态分发

`&dyn Shape` 是一个**胖指针（fat pointer）**：数据指针 + 指向 **vtable**（虚函数表）的指针。vtable 是一张函数指针表，每个方法对应一个槽位；调用 `shape.area()` 时先查 vtable 再间接调用。同一份 `print_area` 代码可以处理 Circle 和 Square，**具体调用哪个函数在运行时才确定**——这是动态分发。
| 维度 | 静态分发（泛型） | 动态分发（dyn） |
|------|----------------|----------------|
| 类型确定时机 | 编译期 | 运行期（通过 vtable） |
| 调用开销 | 直接调用，可内联 | 每次多一次间接跳转 |
| 代码膨胀 | 每类型组合一份 | 无（共享一份代码） |
| 适用场景 | 类型在编译期已知 | 异构集合、插件式架构 |

### 4.3 孤儿规则的动机：避免冲突实现

如果允许"为外部类型实现外部 trait"，两个 crate 可能对同一个 (trait, type) 给出**冲突实现**，而编译器无法发现：每个 crate 独立编译，互相不知晓对方的存在。孤儿规则把 impl 的"归属"限定在 trait 或 type 的定义方，冲突只能发生在定义方自己内部——编译器因此总能全局检查。这与 Haskell typeclass 的取舍不同：Haskell 靠全局 coherence 检查保证唯一性，Rust 用更保守的孤儿规则换取"独立编译也安全"，代价是给外部类型补能力时只能用 newtype 模式绕行。

### 4.4 泛型与 trait bound 在编译期的检查

泛型代码的检查分两步，顺序很重要：**先做类型检查（基于 bound），再做单态化**。泛型函数体只被检查一次——编译器不看你传入的具体类型，只按 `T: Display` 提供的抽象接口检查——这就是为什么错误发生在"声明处"而不是"实例化处"。

每个调用点则做 bound 验证：`print_twice(vec![1, 2])` 报 `E0277`。常见错误映射：E0277（bound 不满足）、E0599（方法不在 trait 里/未引入作用域）、E0308（分支类型不一致）、E0117（孤儿规则）、E0038（对象安全）。**所有 trait 错误都在编译期暴露，运行时不存在"类型没有该方法"的崩溃**——这是 trait 相对 Python 鸭子类型的根本优势。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 多个结构体共享同一行为（日志/索引/向量统一编码） | trait 定义与实现 |
| 同一逻辑适用多种类型（统计、比较、查找） | 泛型函数 + trait bound |
| 复杂签名需要多个约束（K 可哈希 + V 可相加） | where 子句、`+` 组合 |
| 工厂函数隐藏具体返回类型（返回迭代器/闭包） | impl Trait |
| 快速获得打印/比较/克隆/哈希能力 | derive trait |
| 异构集合（不同类型同放一个 Vec） | dyn Trait + Box |
| 为 HashMap 设计可哈希的复合键 | derive/自定义 Hash + PartialEq |
| 为外部类型补充本地能力 | newtype 模式 + 孤儿规则 |

**不适合**此阶段的事项：
- 生命周期标注深入（ph08）：本阶段示例全部避开显式生命周期参数，泛型与生命周期组合留到下一阶段。
- trait 对象与 dyn 深入（ph08+）、异步 trait（ph12）：对象安全细化、`async fn` in trait 后续展开。
- 闭包与迭代器深入（ph09）：本阶段只用最简闭包与 `Iterator` 方法，`map`/`filter`/`fold` 完整用法在集合阶段。
- 宏与过程宏（[ph15 宏与元编程阶段](../ph15-macros-metaprogramming/15-macros-metaprogramming.md)）：本阶段只"用" derive，自定义 derive 宏属于宏阶段。

## 6. 代码示例

> 说明：以下 5 个示例的完整可运行文件在 [`examples/`](./examples/) 目录，均为单文件、零第三方依赖，验证环境 rustc 1.92.0，统一用 `rustc examples/ex0X-*.rs -o /tmp/ex0X && /tmp/ex0X` 编译运行（命令见 examples/README.md）。

### 示例 1：为多个结构体实现同一个 trait（Encode 编码 trait）

roadmap 推荐项目"序列化接口"的核心：为**日志记录 LogRecord、索引元数据 IndexMeta、向量记录 VectorRecord** 实现统一的 `Encode` trait，再用一个泛型函数通吃三种类型：

```rust
// 行为契约：所有"可编码"的类型都实现它
trait Encode {
    fn encode(&self) -> String;
    fn encode_pretty(&self) -> String {      // 默认实现：可被覆盖
        format!("[{}]", self.encode())
    }
}
struct LogRecord { ts: u64, level: String, message: String }
struct IndexMeta { name: String, index_type: String, column_count: u32 }
struct VectorRecord { id: u64, dims: u32, values: Vec<f32> }
impl Encode for LogRecord {
    fn encode(&self) -> String { format!("{} {} {}", self.ts, self.level, self.message) }
}
impl Encode for IndexMeta {
    fn encode(&self) -> String { format!("{} {} {}", self.name, self.index_type, self.column_count) }
}
impl Encode for VectorRecord {
    fn encode(&self) -> String {
        let vals: Vec<String> = self.values.iter().map(|v| format!("{v}")).collect();
        format!("{} {} [{}]", self.id, self.dims, vals.join(","))
    }
}
// 泛型函数：只依赖 Encode 提供的 encode()，不关心具体类型
fn dump_all<T: Encode>(items: &[T]) {
    for item in items { println!("{}", item.encode()); }
}
fn main() {
    let logs = vec![
        LogRecord { ts: 1700000000, level: String::from("INFO"), message: String::from("boot ok") },
        LogRecord { ts: 1700000001, level: String::from("ERROR"), message: String::from("disk full") },
    ];
    let metas = vec![
        IndexMeta { name: String::from("pk_users"), index_type: String::from("btree"), column_count: 1 },
    ];
    let vectors = vec![VectorRecord { id: 1, dims: 3, values: vec![0.1, 0.2, 0.3] }];
    dump_all(&logs);
    println!("pretty: {}", logs[0].encode_pretty()); // 默认实现
    dump_all(&metas);
    dump_all(&vectors);
}
```
这就是"**用 trait 表达能力而不是具体类型**"：`dump_all` 只依赖 `Encode` 契约，将来新增 `StorageRecord` 只需 `impl Encode`，函数零改动。

完整文件：`examples/ex01-encode-trait.rs`

### 示例 2：泛型函数 + trait bound（把重复函数改造成泛型函数）

roadmap 练习"把重复函数改造成泛型函数"的标准套路：先找出两个几乎相同的函数，抽象出类型参数与 bound：

```rust
// 改造前：fn max_score(scores: &[u32]) -> Option<u32> { scores.iter().copied().max() }
//          fn max_ts(timestamps: &[u64]) -> Option<u64> { timestamps.iter().copied().max() }
// 改造后：一个泛型函数，T: Ord + Copy 覆盖所有"可全序比较可拷贝"类型
fn max_of<T: Ord + Copy>(items: &[T]) -> Option<T> {
    items.iter().copied().max()
}
// max_by_key：按 key 取最大元素（key 由调用方传入；T: Clone 以便返回 owned 值）
fn max_by_key<T: Clone, K: Ord>(items: &[T], key: impl Fn(&T) -> K) -> Option<T> {
    items.iter().max_by(|a, b| key(a).cmp(&key(b))).cloned()
}
// 泛型统计：sum 适用于任何"有默认值 + 可拷贝 + 可相加"的数值类型
fn sum<T: Default + Copy + std::ops::Add<Output = T>>(items: &[T]) -> T {
    let mut total = T::default();
    for &item in items { total = total + item; }
    total
}
fn main() {
    let scores = [85u32, 92, 78, 95];
    println!("max: {}", max_of(&scores).unwrap());
    println!("sum: {}", sum(&scores));
    println!("avg: {:.2}", sum(&scores) as f64 / scores.len() as f64);
    let words = ["rust", "go", "c", "python"];
    // Reverse 反转比较：取"最短"的那个
    println!("shortest: {}", max_by_key(&words, |w| std::cmp::Reverse(w.len())).unwrap());
}
```
要点：`max_of` 一行覆盖了 `max_score` 与 `max_ts` 两个函数；`max_by_key` 把"按什么比较"也参数化（key 函数），是 `T: Ord` 无法表达的场景——**抽象程度由 bound 决定，不要过度设计**。

完整文件：`examples/ex02-generic-fn.rs`

### 示例 3：where 子句约束复杂泛型（多 trait 组合）

约束超过两个时，where 子句让签名保持可读；泛型结构体的 impl 块同样支持 where：

```rust
use std::collections::HashMap;
use std::hash::Hash;
// K 可哈希（HashMap key）、V 可拷贝可相加（累加）：三组约束
fn group_and_sum<K, V>(pairs: &[(K, V)]) -> HashMap<K, V>
where
    K: Clone + Eq + Hash,
    V: Copy + Default + std::ops::Add<Output = V>,
{
    let mut acc: HashMap<K, V> = HashMap::new();
    for (k, v) in pairs {
        let entry = acc.entry(k.clone()).or_insert_with(V::default);
        *entry = *entry + *v;
    }
    acc
}
// 泛型结构体：impl 块上的 where 约束
#[derive(Debug)]
struct Counter<K> { counts: HashMap<K, u64> }
impl<K> Counter<K>
where
    K: Eq + Hash,
{
    fn new() -> Self { Counter { counts: HashMap::new() } }
    fn add(&mut self, key: K) { *self.counts.entry(key).or_insert(0) += 1; }
    fn total(&self) -> u64 { self.counts.values().sum() }
}
fn main() {
    let orders = vec![
        (String::from("alice"), 100u32),
        (String::from("bob"), 200),
        (String::from("alice"), 150),
    ];
    println!("totals: {:?}", group_and_sum(&orders));
    let mut c = Counter::new();
    c.add(String::from("INFO"));
    c.add(String::from("WARN"));
    c.add(String::from("INFO"));
    println!("{:?} total={}", c.counts, c.total());
}
```
要点：where 可以出现在三处——函数签名末尾、泛型 impl 块、`impl<T: Trait>` 内联；规则是**约束超过两个就进 where**，让"签名短、约束清楚"。

完整文件：`examples/ex03-where-clause.rs`

### 示例 4：impl Trait 返回值（返回迭代器/闭包）

"隐藏具体返回类型"是 impl Trait 最典型的用途：迭代器链的类型签名极其冗长，用 `impl Iterator<Item = T>` 一句话盖住；工厂函数返回闭包同理（闭包深入 ph09）：

```rust
// 返回迭代器：隐藏 (0..=limit).filter(...) 的具体类型
fn range_evens(limit: u32) -> impl Iterator<Item = u32> {
    (0..=limit).filter(|n| n % 2 == 0)
}
// 返回闭包：make_adder(5) 得到一个"加 5"的函数
fn make_adder(base: i32) -> impl Fn(i32) -> i32 {
    move |x| x + base
}
fn main() {
    let evens: Vec<u32> = range_evens(10).collect();
    println!("{:?}", evens); // [0, 2, 4, 6, 8, 10]
    let add5 = make_adder(5);
    println!("add5(37) = {}", add5(37)); // 42
}
```
要点与坑：
- `impl Iterator<Item = u32>` 是**不透明类型**：调用者能迭代、能 collect，但不知道底层是 `Filter<RangeInclusive<u32>, ...>`，也无法命名该类型——这正是目的（隐藏实现细节，便于后续替换实现）。
- **坑：一个函数只能返回一种具体类型**——`if cond { a } else { b }` 两个分支类型不同时，改用 `Box<dyn Iterator<Item = u32>>`（3.8）。
- `move` 闭包把 `base` 的所有权移入闭包，闭包才能独立存活（ph09 展开）。

完整文件：`examples/ex04-impl-trait.rs`

### 示例 5：derive trait 与自定义 PartialEq/Hash（可哈希键结构体）

HashMap 的 key 需要 `Eq + Hash`。derive 是"逐字段"语义；需要"只按部分字段比较/哈希"时手写 impl——注意**一致性**：相等的 key 必须哈希相同（反之不必）：

```rust
use std::collections::HashMap;
use std::hash::{Hash, Hasher};
// derive 版：DocId 作为完整 key（所有字段参与比较与哈希）
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
struct DocId { shard: u32, seq: u64 }
// 自定义版：ShardKey 只按 shard 判定相等与哈希——同一分片的所有键视为同一个 key
#[derive(Debug, Clone)]
struct ShardKey {
    shard: u32,
    #[allow(dead_code)] // 演示用：label 故意不参与比较/哈希
    label: String,
}
impl PartialEq for ShardKey {
    fn eq(&self, other: &Self) -> bool { self.shard == other.shard }
}
impl Eq for ShardKey {}
impl Hash for ShardKey {
    fn hash<H: Hasher>(&self, state: &mut H) { self.shard.hash(state); }
}
fn main() {
    let mut docs: HashMap<DocId, String> = HashMap::new();
    docs.insert(DocId { shard: 1, seq: 42 }, String::from("doc-a"));
    println!("lookup: {:?}", docs.get(&DocId { shard: 1, seq: 42 }));
    // 按分片聚合：label 不同但 shard 相同 → 视为同一个 key，累加
    let mut by_shard: HashMap<ShardKey, u64> = HashMap::new();
    *by_shard.entry(ShardKey { shard: 2, label: String::from("a") }).or_insert(0) += 10;
    *by_shard.entry(ShardKey { shard: 2, label: String::from("b") }).or_insert(0) += 20;
    let total = by_shard.get(&ShardKey { shard: 2, label: String::from("x") }).unwrap();
    println!("shard 2 total: {}", total); // 30
}
```
要点与坑：
- **坑：一致性破坏**——若手写 `Hash` 只哈希 shard，但 `PartialEq` 仍比较 label，HashMap 会把"相等"的 key 分到不同桶（或反之），查找行为错乱；`PartialEq` 与 `Hash` 必须用同一套判定逻辑。
- derive 的 Hash 是确定性的逐字段哈希；自定义版本适用于"聚合键""分组键"这类语义（如按分片聚合）。

完整文件：`examples/ex05-derive-hash.rs`

## 7. 总结

### 关键要点

1. **trait 是行为契约**："能做什么"与"怎么做"分离，显式 `impl` 实现，可带默认实现。
2. **泛型 = 一份代码适用多种类型**：类型参数在调用点推断，能力由 bound 决定。
3. **trait bound 是类型安全的来源**：不满足约束的调用在编译期报 E0277/E0599，运行时不可能"方法不存在"。
4. **where 子句整理复杂约束**：约束超过两个、或写在泛型 impl 上时用 where，保持签名可读。
5. **impl Trait 两种位置两种语义**：参数位置是匿名泛型（等价 `<T: Trait>`），返回位置是不透明类型（由实现者决定、只能返回单一类型）。
6. **derive 一行生成常见 trait**：Debug / Clone / PartialEq / Eq / Hash，条件是所有字段都实现了对应 trait。
7. **孤儿规则保全局唯一**：impl 的 trait 或 type 至少一个属于当前 crate；绕行方案是 newtype。
8. **静态分发零成本、动态分发更灵活**：泛型单态化可内联但代码膨胀，`dyn Trait` 走 vtable 但类型可异构。
9. **对象安全限制 dyn 的使用**：泛型方法、返回 Self 等方法使 trait 不能成为 trait 对象（E0038）。

### 跨语言对比：接口与泛型抽象

| 维度 | Rust trait | Go interface | Java interface | C++ 模板 | Python duck typing |
|------|-----------|--------------|----------------|----------|-------------------|
| 抽象单元 | trait（签名 + 默认实现） | interface（方法集） | interface（默认方法） | 模板 + concept（C++20） | 无显式声明 |
| 实现方式 | 显式 `impl`，孤儿规则 | 隐式满足（结构类型） | 显式 implements | 实例化时隐式满足 | 运行期属性查找 |
| 分发方式 | 泛型静态分发 / dyn 动态分发 | 动态分发 | 动态分发（虚方法表） | 编译期模板实例化 | 运行期动态 |
| 类型检查时机 | 编译期（声明处检查 bound） | 编译期（接口满足性） | 编译期 | 实例化时才检查 | 运行期才报错 |
| 多态集合 | `Vec<Box<dyn Trait>>` | `[]interface{}` | `List<Interface>` | 同构容器（无擦除） | list 任意混装 |
| 零成本抽象 | 单态化零开销 | 无（vtable 间接调用） | 无（虚方法） | 零开销（内联模板） | 无（运行期查找） |

### 阶段验收清单

- [ ] 能用 trait 表达能力而不是具体类型：泛型函数/结构体只依赖 trait bound 提供的方法，不依赖具体类型
- [ ] 能解释泛型单态化的基本影响：每类型组合生成专用代码，零运行时开销、可内联，但存在代码膨胀
- [ ] 能处理常见 trait bound 编译错误：E0277、E0599、E0308、E0117、E0038 各是什么原因、怎么修
- [ ] 能区分静态分发与动态分发：泛型 vs `dyn Trait` 的适用场景与性能特征
- [ ] 能用 derive 生成常见 trait，并知道何时必须手写 impl（自定义比较/哈希逻辑）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：为多个结构体实现同一个 trait、把重复函数改造成泛型函数、用 where 子句约束复杂泛型、用 impl Trait 改写返回迭代器的函数、自定义 PartialEq 与 Hash 共 5 题。完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**序列化接口**——为日志记录（LogRecord）、索引元数据（IndexMeta）、向量记录（VectorRecord）实现统一编码 trait，支持 CSV/JSON 两种编码策略与批量导出，含单元测试。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[生命周期 Lifetime 阶段](../ph08-lifetimes/08-lifetimes.md) —— 生命周期标注、省略规则、结构体中的引用、`'static`。trait 与泛型解决了"行为怎么抽象"，生命周期解决"引用能活多久"：`&str` 字段、返回引用的泛型函数、trait 方法中的生命周期参数，都将在下一阶段与泛型组合出现。
