# Rust 所有权 Ownership 阶段

> 面向安全高性能数据基础设施方向，掌握 Rust 最核心的内存管理规则：不依赖 GC、不手动 free，用所有权和借用检查在编译期保证内存安全。

## 1. 概述

Rust 所有权阶段的定位是：**理解一个值何时被创建、移动、借用和销毁，并能根据场景选择传值、不可变借用或可变借用**。这是 Rust 与 C/C++/Java/Go 在内存模型上最根本的差异，也是后续理解 `Vec`、`HashMap`、trait、生命周期和并发安全的基础。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 所有权规则 | 一个值只有一个 owner；owner 离开作用域时释放；ownership 可移动 |
| 移动语义 | 赋值、传参、返回值都会发生 move；move 后旧变量不可用 |
| Copy / Clone | Copy 类型按位复制；Clone 是显式深拷贝；String / Vec 不实现 Copy |
| 借用 | 不可变引用 `&T`、可变引用 `&mut T`；借用不拥有资源 |
| 引用规则 | 同一作用域内：多个只读引用 **或** 一个独占可变引用 |
| 引用作用域 | NLL（Non-Lexical Lifetimes）：引用活到最后一次使用 |
| 字符串与切片 | `String`、`&String`、`&str`、slice `&[T]` 的转换与选择 |

**本阶段边界**：不展开生命周期标注（`'a`）、智能指针（`Box`/`Rc`/`Arc`）和内部可变性（`RefCell`），那些属于 **ph08 生命周期** 和 **ph10 智能指针**。

## 2. 来源与演变

内存管理大致经历过三条路线：完全手动、垃圾回收、RAII + 编译期约束。Rust 的所有权模型来自后两者的融合，并借用了线性类型（linear/affine type）和区域推导（region inference）的思想：资源只能被使用一次或按规则借用。

| 范式 | 代表语言 | 释放时机 | 运行时开销 | 典型风险 |
|------|---------|---------|-----------|---------|
| 手动管理 | C | 程序员调用 `free` | 无 | 重复释放、内存泄漏、悬垂指针、UAF |
| 垃圾回收 | Java、Go、Python | GC 自动回收 | 有暂停和内存开销 | 暂停不可控、循环引用、Finalizer 不确定 |
| RAII + 智能指针 | C++ | 析构函数 | 通常无 GC，但依赖程序员正确使用 | 循环引用、误用裸指针、异常路径泄漏 |
| 所有权 + 借用检查 | Rust | 编译期决定，运行时至简释放 | 零运行时 GC 开销 | 初学时需适应编译器规则 |

## 3. 语法与参数

### 3.1 所有权三条规则

1. **每个值有且只有一个 owner**（变量、结构体字段、集合元素等）。
2. **owner 离开作用域时，值被丢弃（drop）**，内存自动释放。
3. **ownership 可以转移（move）**：赋值、传参、返回都会转移 ownership。

```rust
fn main() {
    let s = String::from("hello"); // s 是 owner
    let t = s;                    // ownership 移动到 t，s 失效
    println!("{}", t);            // 合法
    // println!("{}", s);         // 编译错误：value moved
}
```

### 3.2 移动 move 语义

Rust 中大多数“赋值”不是复制，而是 **move**。move 的底层实现通常只是**浅拷贝**（复制栈上的指针/长度/容量），同时**让编译器记住旧变量不再有效**。

```rust
fn take(s: String) {
    println!("take: {}", s);
}

fn main() {
    let a = String::from("data");
    take(a);          // a 的 ownership 移动到 take
    // println!("{}", a); // 错误：a 已移动
}
```
如果希望继续使用原变量，需要 **clone** 或改用 **借用**。

### 3.3 Copy 与 Clone

**Copy** 是 Rust 的 marker trait。实现 `Copy` 的类型在赋值时会被**按位复制**，原变量仍然可用。基本标量、只包含 Copy 字段的元组、不可变引用 `&T` 都自动实现 Copy。

```rust
fn main() {
    let x = 42;       // i32 实现 Copy
    let y = x;        // 按位复制，x 仍可用
    println!("x={} y={}", x, y);

    let p = (1, 2.0); // (i32, f64) 实现 Copy
    let q = p;
    println!("{:?} {:?}", p, q);
}
```
**Clone** 是显式的深拷贝，需要调用 `.clone()`，开销取决于类型：

```rust
fn main() {
    let s1 = String::from("hello");
    let s2 = s1.clone(); // 堆上数据复制，s1 仍可用
    println!("{} {}", s1, s2);
}
```
| 特性 | Copy | Clone |
|------|------|-------|
| 调用方式 | 隐式 | 显式 `.clone()` |
| 语义 | 按位浅拷贝 | 自定义深拷贝逻辑 |
| 适用类型 | 标量、小且固定大小的值 | 堆分配类型、自定义类型 |
| 原变量 | 仍可用 | 仍可用 |
| trait 类型 | marker trait | 普通 trait |

`String`、`Vec<T>`、自定义包含堆分配字段的结构体**不实现 Copy**，但可以实现 `Clone`。
### 3.4 借用 borrowing 与引用

**借用**允许函数在不获取 ownership 的情况下使用值。函数结束后，ownership 仍归原变量，值不会被 drop。

```rust
fn print_len(s: &str) {
    println!("length: {}", s.len());
}

fn main() {
    let text = String::from("rust");
    print_len(&text);  // 借用 text
    print_len(&text);  // 再次借用，text 仍可用
    println!("{}", text);
}
```

- `&T`：不可变引用，只读。
- `&mut T`：可变引用，可修改被引用的值，但同一作用域内只能有一个。

```rust
fn append_dot(s: &mut String) {
    s.push('.');
}

fn main() {
    let mut msg = String::from("hello");
    append_dot(&mut msg);
    println!("{}", msg); // hello.
}
```

### 3.5 不可变引用与可变引用的 xor 规则

Rust 对同一数据的引用施加 **XOR 规则**：

- **多个不可变引用**（`&T`）可以同时存在；
- **一个可变引用**（`&mut T`）可以存在；
- **不可变引用和可变引用不能同时活跃**。

这条规则在编译期消除了数据竞争：不可能出现一边读一边写的并发冲突（即使单线程，迭代时修改集合也会导致类似问题）。

```rust
fn main() {
    let mut s = String::from("hello");

    let r1 = &s;
    let r2 = &s;
    println!("{} {}", r1, r2); // 两个只读引用同时活跃，合法

    let r3 = &mut s;            // 此前只读引用最后一次使用已结束
    r3.push_str(" world");
    println!("{}", r3);         // 合法
}
```

### 3.6 引用作用域与 NLL

在 Rust 2018 之前，引用的作用域像 C++ 引用一样延伸到**定义所在词法块的末尾**。Rust 2018 引入 **NLL（Non-Lexical Lifetimes）**：引用的有效期只到**最后一次使用**为止，而不是到块末尾。

```rust
fn main() {
    let mut v = vec![1, 2, 3];

    let first = &v[0];
    println!("{}", first); // first 的最后一次使用

    v.push(4);             // NLL 下 first 已失效，可以修改 v
    println!("{:?}", v);
}
```

NLL 让大量自然写法通过编译，但核心规则不变：引用活跃期间不能违反 xor 规则。

### 3.7 String、&String、&str 与 slice

`String` 是**拥有的、可变长、堆分配**的 UTF-8 字符串，内部是三个字段：指针 `ptr`、长度 `len`、容量 `capacity`。

`&str` 是**字符串切片**，是一个“胖指针”：指向某处 UTF-8 字节的指针 + 长度。**它不拥有数据**，只是对连续字节序列的只读视图。

```rust
fn main() {
    let owned = String::from("hello world");

    let slice1: &str = &owned[0..5]; // 切片，指向 owned 的 "hello"
    let slice2: &str = &owned;        // &String 自动解引用为 &str

    println!("{} | {}", slice1, slice2);

    let lit: &str = "literal";        // 字符串字面量是 &'static str
    let back: String = lit.to_string(); // &str -> String
    let view: &str = back.as_str();     // String -> &str
    println!("{} {}", back, view);
}
```

| 类型 | 拥有数据 | 可变性 | 内存位置 | 典型用途 |
|------|---------|--------|---------|---------|
| `String` | 是 | `mut` 可变 | 堆 | 需要修改或长期保存字符串 |
| `&String` | 否 | 只读（除非 &mut String） | 指向堆 | 很少直接使用，常自动转成 &str |
| `&str` | 否 | 只读 | 可指向堆/String/静态区 | 函数参数首选，零拷贝视图 |
| `&[T]` | 否 | 只读 | 指向数组/Vec/切片 | 通用切片，避免集合 owning |

通用切片 `&[T]` 与 `&str` 是同一思想在任意类型上的推广：

```rust
fn sum_all(nums: &[i32]) -> i32 {
    let mut total = 0;
    for n in nums {
        total += *n;
    }
    total
}

fn main() {
    let arr = [10, 20, 30];
    let v = vec![1, 2, 3];
    println!("{}", sum_all(&arr)); // 数组转切片
    println!("{}", sum_all(&v));   // Vec 转切片
    println!("{}", sum_all(&v[1..])); // 子切片
}
```

## 4. 底层原理

### 4.1 Move 是浅拷贝 + 旧变量失效

对 `String`、`Vec<T>` 等带堆分配的类型，move 在机器层面只复制栈上的元数据（指针、长度、容量），**不会复制堆数据**。但 Rust 在编译期将旧变量标记为“未初始化”，禁止后续访问。

这与 C++ 的移动语义相似，但 Rust 的 move 由编译器保证旧变量不可再访问，无需像 C++ 那样把源指针置空。
### 4.2 Drop 与 RAII

Rust 中类型可以实现 `Drop` trait，定义值离开作用域时的清理逻辑。`String` 的 `Drop` 释放堆内存，`File` 的 `Drop` 关闭文件句柄，与 C++ RAII 理念一致，但不需要手动调用析构函数。

例如 `String` 在离开作用域时会自动释放其堆内存，无需手动调用 `free`。
### 4.3 借用检查如何避免悬垂引用

C/C++ 中常见的错误是让引用指向已经离开作用域的值，导致悬垂引用（dangling reference）。Rust 编译器会拒绝这种代码：

```rust
// 此代码无法通过编译
fn main() {
    let r;
    {
        let s = String::from("hello");
        r = &s; // 错误：s 在块结束时就被 drop
    }
    println!("{}", r);
}
```

修复方法是返回拥有值而不是引用：

```rust
fn owned() -> String {
    let s = String::from("hello");
    s // ownership 移出函数，调用方负责释放
}

fn main() {
    let result = owned();
    println!("{}", result);
}
```
### 4.4 编译错误示范

学会阅读借用检查错误是本章的核心能力。下面是两个最常见的错误。

**错误 1：use of moved value（E0382）**

```rust
// 此代码无法通过编译
fn main() {
    let s = String::from("hello");
    let _t = s;
    println!("{}", s);
}
```

真实编译器输出（rustc 1.92，--edition 2021）：

```text
error[E0382]: borrow of moved value: `s`
 --> e0382.rs:4:20
  |
2 |     let s = String::from("hello");
  |         - move occurs because `s` has type `String`, which does not implement the `Copy` trait
3 |     let _t = s;
  |             - value moved here
4 |     println!("{}", s);
  |                    ^ value borrowed here after move
  |
  = note: this error originates in the macro `$crate::format_args_nl` which comes from the expansion of the macro `println` (in Nightly builds, run with -Z macro-backtrace for more info)
help: consider cloning the value if the performance cost is acceptable
  |
3 |     let _t = s.clone();
  |               ++++++++
```

解读：第二行 `let _t = s;` 把 `s` 移动到了 `_t`；第四行又尝试使用 `s`，编译器指出 `String` 不实现 `Copy`。修复方法：改用 `let _t = s.clone();` 或函数参数改为 `&str`。

**错误 2：multiple mutable borrows（E0499）**

```rust
// 此代码无法通过编译
fn main() {
    let mut s = String::from("hello");
    let r1 = &mut s;
    let r2 = &mut s;
    println!("{} {}", r1, r2);
}
```

真实编译器输出（rustc 1.92，--edition 2021）：

```text
error[E0499]: cannot borrow `s` as mutable more than once at a time
 --> e0499.rs:5:18
  |
4 |     let r1 = &mut s;
  |             ------- first mutable borrow occurs here
5 |     let r2 = &mut s;
  |             ^^^^^^^ second mutable borrow occurs here
6 |     println!("{} {}", r1, r2);
  |                      -- first borrow later used here
```

解读：第 4 行已经借了 `s` 的可变引用；第 5 行在 `r1` 仍然活跃时再次申请可变引用，违反 xor 规则。修复方法：让 `r1` 在申请 `r2` 之前结束使用，或把两次修改合并到同一个可变引用里。
## 5. 使用场景

| 场景 | 推荐方式 | 原因 |
|------|---------|------|
| 只读访问字符串/切片 | `&str` / `&[T]` | 不转移 ownership，可多次借用 |
| 需要修改传入数据 | `&mut T` | 调用方保留 ownership，函数内可变访问 |
| 完全接管数据并可能返回 | `T`（传值） | ownership 明确转移 |
| 需要保留原变量且数据可克隆 | `.clone()` | 显式深拷贝，意图清晰 |
| 函数返回新构造的字符串 | `String` | 拥有值，无生命周期问题 |
| 遍历集合并只读统计 | `&[T]` / `&str` | 零拷贝，避免 move |

**不适合**此阶段深入的内容：
- 跨函数返回引用（需要生命周期标注，ph08）。
- 多个 owner 共享堆数据（需要 `Rc`/`Arc`，ph10）。
- 在不可变结构内部修改状态（需要内部可变性，ph10）。
- 复杂自引用结构（需要 `Pin` 等高级主题）。
## 6. 代码示例

### 示例 1：move、Copy 与 Clone 对比

```rust
fn main() {
    // move：String 不实现 Copy
    let s1 = String::from("hello");
    let s2 = s1;
    // println!("{}", s1); // 错误：value moved
    println!("s2 = {}", s2);

    // Copy：i32 按位复制
    let x = 7;
    let y = x;
    println!("x = {} still usable, y = {}", x, y);

    // Clone：显式深拷贝
    let a = String::from("data");
    let b = a.clone();
    println!("a = {}, b = {}", a, b);
}
```

### 示例 2：函数传参与借用选择

```rust
fn show(s: &str) {
    println!("show: {}", s);
}

fn grow(s: &mut String) {
    s.push_str(" world");
}

fn take_and_upper(s: String) -> String {
    s.to_uppercase()
}

fn main() {
    let mut msg = String::from("hello");

    show(&msg);            // 不可变借用
    grow(&mut msg);        // 可变借用
    show(&msg);            // 再次不可变借用，msg 仍拥有数据

    let loud = take_and_upper(msg); // ownership 转移
    println!("{}", loud);
    // msg 已不可用
}
```

### 示例 3：String、&str 与 slice 转换

```rust
fn pick_word(text: &str, idx: usize) -> Option<&str> {
    text.split_whitespace().nth(idx)
}

fn sum_range(nums: &[i32], start: usize, end: usize) -> i32 {
    if start > end || end > nums.len() {
        return 0;
    }
    nums[start..end].iter().sum()
}

fn main() {
    let sentence = String::from("rust ownership is powerful");
    let word = pick_word(&sentence, 1).unwrap_or("?");
    println!("second word: {}", word);

    let numbers = [10, 20, 30, 40, 50];
    println!("sum[1..4] = {}", sum_range(&numbers, 1, 4));

    let slice: &str = &sentence[5..14];
    println!("slice: {}", slice);
}
```

### 示例 4：可变借用与 NLL

```rust
fn double_first(nums: &mut [i32]) {
    if let Some(first) = nums.first_mut() {
        *first *= 2;
    }
}

fn main() {
    let mut values = vec![1, 2, 3, 4];

    let r = &values[0];
    println!("before: {}", r); // r 最后一次使用

    double_first(&mut values); // NLL 下 r 已失效，可变借用合法
    println!("after: {:?}", values);
}
```

### 示例 5：文本统计器（零 clone）

```rust
use std::io::{self, Read};

fn count_lines(text: &str) -> usize {
    text.lines().count()
}

fn count_words(text: &str) -> usize {
    text.split_whitespace().count()
}

fn longest_word(text: &str) -> Option<&str> {
    text.split_whitespace().max_by_key(|w| w.len())
}

fn main() {
    // 输入格式：多行文本，EOF 结束（Linux 按 Ctrl+D，Windows 按 Ctrl+Z 后回车）
    let mut input = String::new();
    io::stdin()
        .read_to_string(&mut input)
        .expect("读取标准输入失败");

    let text = input.trim();
    println!("lines: {}", count_lines(text));
    println!("words: {}", count_words(text));

    match longest_word(text) {
        Some(w) => println!("longest: {} (len={})", w, w.len()),
        None => println!("longest: N/A"),
    }
}
```

这个程序接收任意文本，统计行数、单词数和最长单词；所有统计函数都接受 `&str` 或返回 `&str`，全程没有调用 `.clone()`。
## 7. 总结

### 关键要点

1. **所有权三规则**：每个值一个 owner；owner 出作用域时 drop；ownership 可移动。
2. **move 不是深拷贝**：对 `String`/`Vec` 是浅拷贝 + 旧变量失效，堆数据不复制。
3. **Copy vs Clone**：Copy 隐式按位复制；Clone 显式深拷贝；堆分配类型通常只实现 Clone。
4. **借用不拥有资源**：`&T` 只读可共享，`&mut T` 独占可修改，二者不能同时活跃。
5. **NLL**：引用作用域到**最后一次使用**，而非块末尾，这让自然写法更容易通过编译。
6. **`&str` 是视图**：函数参数优先用 `&str`/`&[T]`，避免不必要的 move 和 clone。
7. **读编译错误**：E0382（move 后使用）和 E0499（多次可变借用）是最常见的所有权错误，报错信息会指出冲突位置。

### 跨语言对比：内存管理范式

| 范式 | 释放方式 | 运行时开销 | 悬垂引用保护 | 数据竞争保护 |
|------|---------|-----------|-------------|-------------|
| C 手动管理 | `free` | 无 | 无 | 无 |
| Java / Go / Python GC | 垃圾回收器 | 暂停、内存开销 | 有（无悬垂） | 依赖运行时/锁 |
| Rust 所有权 | 编译期决定 + Drop | 无 GC | 编译期禁止 | 编译期限制 |

### 阶段验收标准

- 能解释 `let t = s;` 后为什么 `s` 不可用（因为 move）。
- 能说明 `i32` 赋值后仍可用、`String` 赋值后不可用（因为 Copy 与 move 的区别）。
- 能在函数参数中选择传值 `T`、不可变借用 `&T` 或可变借用 `&mut T`。
- 能根据 E0382 / E0499 等错误提示定位冲突并修复，修复时优先缩短借用作用域而不是立刻 clone。
- 能把 `String` 转换为 `&str`，并理解 `&str`、`&[T]` 作为零拷贝视图的用法。

### 进入下一阶段前

完成以下练习：
- 把示例 2 中 `take_and_upper(msg)` 改成不转移 ownership 的版本（提示：返回新 `String`，参数用 `&str`）。
- 写一个函数 `fn truncate(s: &mut String)`，把字符串截断到只剩前 3 个字符。
- 练习 `String::from("...")`、`&str`、`&String`、`.as_str()`、`.to_string()` 之间的转换。
- 尝试制造并修复一个 E0502（不可变借用期间申请可变借用）错误。

### 推荐项目

- **文本统计器**：读取标准输入或文件，统计行数、单词数、最长单词，并尽量减少 clone。本阶段示例 5 已给出核心实现，可扩展为支持命令行参数和文件路径。

### 下一阶段

[基础数据结构阶段](../ph03-data-structure/03-data-structure.md) — 掌握 struct、enum、Vec、HashMap 与 impl 方法，继续用所有权规则组织真实数据。
