# Rust 智能指针阶段

> 面向数据基础设施、异步网络服务方向：本阶段掌握常见智能指针，能表达堆分配、共享所有权和内部可变性——让"数据放哪、谁拥有、能不能改"从编译期规则落到可组合的标准库类型上。

## 1. 概述

Rust 智能指针阶段的定位是：**能根据场景选择 `Box<T>`（堆分配）、`Rc<T>`/`Arc<T>`（共享所有权）、`RefCell<T>`/`Mutex<T>`（内部可变性），理解 `Deref`/`Drop` 两个 trait 如何塑造"用起来像引用、走时自动清理"的体验，并能用 `Weak<T>` 打破循环引用**。本阶段是 ph02 所有权阶段的进阶：所有权模型本身是"一个值一个 owner"，而真实程序里数据需要被多处共享、需要在只读接口下修改、需要跨线程传递——智能指针正是所有权模型在这些场景下的标准答案。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 堆分配 | `Box<T>`：把值放到堆上，离开作用域自动释放 |
| 递归类型与 trait 对象 | `Box` 打破递归类型的无限大小，`Box<dyn Trait>` 擦除具体类型 |
| 单线程共享所有权 | `Rc<T>`：非原子引用计数，`clone` 只增计数不复制数据 |
| 线程安全共享所有权 | `Arc<T>`：原子引用计数，配合 `Mutex<T>`/`RwLock` 做线程间可变共享 |
| 内部可变性 | `RefCell<T>`：借用检查从编译期挪到运行期，`borrow`/`borrow_mut` |
| 自定义析构与解引用 | `Drop`（自动清理）、`Deref`/`DerefMut`（像引用一样用） |
| 循环引用与 Weak | `Weak<T>`：弱引用不增加强引用计数，`upgrade()` 升级访问，避免泄漏 |
| 组合模式 | `Rc<RefCell<T>>`（单线程共享可变）、`Arc<Mutex<T>>`（多线程共享可变） |

**本阶段边界**：承接 ph09 集合与迭代器（迭代器链产出共享引用、`Box<dyn Iterator>` 装箱返回都会用到本阶段类型）；不深入错误处理工程化（ph11，`Mutex` 中毒与 `Result` 的工程化组合）、异步编程（ph12，共享状态跨 `.await` 的问题）、unsafe 与裸指针（ph14，`*const T`/`*mut T` 与 `Pin`）。

## 2. 来源与演变

智能指针的根源在 **RAII（Resource Acquisition Is Initialization）**：资源在构造时获取、在析构时释放。Rust 没有继承自 C++ 的类层次，而是用 trait 表达"指针行为"：**`Deref` 定义解引用**（让 `*boxed` 像 `*ref` 一样工作），**`Drop` 定义析构**（释放时机由编译器保证）。`Box<T>` 是最基础的智能指针——它回答所有权模型留下的第一个表达力缺口："递归类型怎么办？"（没有 `Box`，`enum List { Cons(i32, List) }` 的大小无限）以及"无法静态书写的类型怎么办？"（`Box<dyn Trait>`）。早期 Rust（2009-2013）就把 `Box` 作为核心类型，`Deref`/`Drop` 的接口设计随 1.0 前的 RFC 流程定型。

共享所有权的需求催生了**引用计数**设计：单线程的 `Rc<T>`（普通计数器，快）与多线程的 `Arc<T>`（原子计数器，稍慢但 `Send + Sync`）同时进入标准库。但引用计数引入一个经典缺陷——**循环引用**：两个 `Rc` 互相持有对方时计数永不归零，内存泄漏。标准库的答案是 `Weak<T>`：**弱引用不增加强引用计数**，用 `upgrade()` 尝试升级为强引用。`RefCell<T>` 则代表另一种思路：**内部可变性（interior mutability）**——在 `&self` 接口下修改内部状态，把借用检查推迟到运行时（`borrow`/`borrow_mut` + 运行时计数）。这是 Rust 有意保留的"安全逃生口"：单线程需要缓存、计数、观察者列表时不必引入锁。

| 时间 | 里程碑 | 影响 |
|------|--------|------|
| 2009-2013 | 早期设计把 `Box` 作为核心类型，`Deref`/`Drop` 接口雏形 | "堆分配 + 自动释放"成为语言基础，递归类型由此可行 |
| 2012-2014 | `Rc`/`Arc`/`RefCell` 进入 `std::rc`/`std::cell`/`std::sync` | 共享所有权与内部可变性获得官方实现 |
| 2014 | 解引用强制转换（deref coercion）稳定 | `&Rc<T>`/`&Box<T>` 自动变 `&T`，智能指针"用起来像引用" |
| 2015 | Rust 1.0：`Box`/`Rc`/`Arc`/`RefCell`/`Mutex` 全部稳定 | 智能指针成为标准库一等公民 |
| 2015-2016 | `Rc::downgrade`/`Weak` 稳定 | 循环引用问题有了官方解法 |
| 2021 | edition 2021：借用检查与闭包语义更宽松 | 智能指针 API 保持稳定，组合模式成为生态惯例 |

## 3. 语法与参数

### 3.1 Box\<T\>（堆分配 · 递归类型 · trait 对象）

**`Box<T>`** 把值分配在**堆**上，栈上只留一个指针；`Box` 离开作用域时自动 `free`（通过 `Drop`）。三个典型用途：堆分配、打破递归类型、装箱 trait 对象：

```rust
fn main() {
    let b = Box::new(42);      // 在堆上分配 i32，栈上存指针
    println!("{}", *b);

    // 递归类型：没有 Box 时 List 大小无限，编译不过（E0072）
    #[derive(Debug)]
    enum List {
        Cons(i32, Box<List>),
        Nil,
    }
    let list = List::Cons(1, Box::new(List::Cons(2, Box::new(List::Nil))));
    println!("{list:?}");

    // trait 对象：具体类型被擦除，只能通过 &dyn 调用 trait 方法
    let objects: Vec<Box<dyn std::fmt::Debug>> =
        vec![Box::new(1), Box::new(String::from("hi"))];
    println!("{objects:?}");
}
```

要点与坑：
- **`Box` 不是性能银弹**：只是把分配从栈挪到堆，多一次堆分配/释放；它服务于"递归类型、动态大小、所有权传递"。
- **坑：递归类型忘加 `Box`（E0072）**——`enum List { Cons(i32, List) }` 报"recursive type has infinite size"，编译器会提示"insert some indirection（如 `Box`）"。

### 3.2 Deref 与 DerefMut（解引用与自动解引用转换）

**`Deref` trait** 定义 `*x` 的解引用行为（`fn deref(&self) -> &Self::Target`），`DerefMut` 定义可变解引用。更重要的是**自动解引用转换（deref coercion）**：需要 `&T` 处看到 `&U` 且 `U: Deref<Target = T>` 时自动插入解引用，因此 `&Rc<String>` 能直接传给 `&str` 参数：

```rust
use std::ops::Deref;

struct MyBox<T>(T);

impl<T> Deref for MyBox<T> {
    type Target = T;
    fn deref(&self) -> &T {
        &self.0
    }
}

fn hello(name: &str) {
    println!("Hello, {name}!");
}

fn main() {
    let m = MyBox(String::from("Rust"));
    hello(&m);          // &MyBox<String> 自动解引用 -> &String -> &str（deref coercion）
    hello(&(*m)[..]);   // 手动等价写法
    println!("{}", *m); // 显式解引用
}
```

要点与坑：
- **`String` 实现 `Deref<Target = str>`、`Vec<T>` 实现 `Deref<Target = [T]>`**：所以 `&String` 能当 `&str` 用、`&Vec<T>` 能当 `&[T]` 用。
- **坑：deref coercion 不适用于泛型函数**——只在"参数类型已知"（`&str`、`&[T]`）的场合生效。
- **坑：Deref 过度依赖**——实现 `Deref` 会让方法解析"穿透"到 `Target`（如 `mybox.len()`），掩盖真实 API；官方建议只在"行为上确实是它"时实现（智能指针、集合封装）。

### 3.3 Drop（自定义析构 · Drop 顺序）

**`Drop` trait** 定义值离开作用域时的清理逻辑（`fn drop(&mut self)`），`Box`/`Rc`/`MutexGuard` 都靠它自动释放资源。变量按**声明逆序** drop，结构体字段按声明顺序 drop；**不能显式调用 `drop` 方法**（只能用 `std::mem::drop(x)` 提前移交所有权触发）：

```rust
struct Guard {
    name: &'static str,
}

impl Drop for Guard {
    fn drop(&mut self) {
        println!("Guard {} 被释放", self.name);
    }
}

fn main() {
    let _a = Guard { name: "A" };
    {
        let _b = Guard { name: "B" };
    } // 内层块结束：B 先 drop
    // main 结束：A 后 drop（声明逆序）
    // 输出顺序：Guard B 被释放 -> Guard A 被释放
}
```

要点与坑：
- **坑：Drop 与移动语义冲突（E0509）**——实现 `Drop` 的类型不能把字段 move 出 `&mut self`（`drop` 后该类型仍可能被使用）；需要"拿回字段"先用 `Option::take`。
- `Drop` 与 `Copy` 互斥（位复制后谁负责析构？语义冲突）；依赖释放顺序时要显式缩小作用域。

### 3.4 Rc\<T\>（单线程引用计数 · clone 语义）

**`Rc<T>`（Reference Counted）** 让一个值被多个 owner 共享：每次 `Rc::clone(&x)` 只是**引用计数 +1**，不复制堆上数据；最后一个 `Rc` 离开作用域时计数归零才真正释放。计数是**非原子的**，因此 `Rc` **不是 `Send`**，只能单线程使用：

```rust
use std::rc::Rc;

fn main() {
    let a = Rc::new(String::from("config"));
    println!("strong = {}", Rc::strong_count(&a)); // 1

    let b = Rc::clone(&a); // 引用计数 +1，堆上字符串只存一份
    let c = a.clone();
    println!("strong = {}", Rc::strong_count(&a)); // 3
    println!("{} {} {}", a, b, c);
}
```

要点与坑：
- **`Rc::clone` 是浅的**：只增计数不拷贝数据，O(1)；对比 `String::clone` 深拷贝 O(n)——这是共享的收益来源。
- **坑：`Rc` 跨线程（E0277）**——`Rc` 没实现 `Send`，`thread::spawn` 里移动 `Rc` 报"`Rc<String>` cannot be sent between threads safely"，提示改用 `Arc`。
- `Rc` 默认不可变：想"多 owner 且能改"要配 `RefCell`（见 3.9）。

### 3.5 Arc\<T\>（线程安全引用计数 · 原子操作）

**`Arc<T>`（Atomically Reference Counted）** 与 `Rc` 语义相同，只是计数用**原子操作**（fetch_add/fetch_sub），可在多线程间共享（`Arc<T>: Send + Sync`，要求 `T: Send + Sync`）。代价是每次计数增减有原子指令开销，单线程用 `Rc` 更快：

```rust
use std::sync::Arc;
use std::thread;

fn main() {
    let data = Arc::new(vec![1, 2, 3]);
    let mut handles = vec![];

    for i in 0..3 {
        let d = Arc::clone(&data); // 每个线程一份 Arc，共享同一份 Vec
        handles.push(thread::spawn(move || {
            println!("线程 {i}: {:?}", d);
        }));
    }

    for h in handles {
        h.join().unwrap();
    }
}
```

要点与坑：
- **`Arc<T>` 只解决"共享"**：多线程可以**读**同一份数据；要**改**必须配合 `Mutex`/`RwLock`（3.7）——`Arc<Mutex<T>>` 是线程间可变共享的标准组合。
- **坑：单线程误用 `Arc`**——功能正确但白付原子操作开销，clippy 会提示 `Rc` 更合适；`Arc::downgrade` 同样能得到 `Weak`（见 3.8）。

### 3.6 RefCell\<T\> 与内部可变性（运行时借用检查 · BorrowError）

**内部可变性**：通过 `RefCell<T>`，可以在**只持 `&self`** 时修改内部值——借用规则从编译期挪到**运行期**。`borrow()` 返回 `Ref<T>`、`borrow_mut()` 返回 `RefMut<T>`，同一时刻仍是"多个只读 **或** 一个可变"的 xor 规则，只是违规时**运行时 panic** 而非编译报错：

```rust
use std::cell::RefCell;

fn main() {
    let cell = RefCell::new(5);

    {
        let r = cell.borrow(); // 不可变借用
        println!("{}", *r);
    } // r 离开作用域，借用归还

    {
        let mut w = cell.borrow_mut(); // 可变借用
        *w += 1;
    }
    println!("{}", cell.borrow()); // 6

    // 编译期完全合法（检查在运行时）：
    // let r1 = cell.borrow();
    // let r2 = cell.borrow_mut(); // 运行期 panic（BorrowMutError，借用冲突推迟到运行时）
}
```

要点与坑：
- **坑：借用冲突在运行时 panic**——`borrow_mut` 时已有活跃借用会 panic（`BorrowMutError`）；guard 忘记 drop（如放进长生命周期结构体）会让后续借用一直失败，且 panic 发生在"受害者"而非"肇事者"处，难排查。
- **`RefCell` 不是 `Sync`**：单线程专用；多线程可变共享用 `Mutex`。
- 借用 guard（`Ref`/`RefMut`）实现 `Deref`，所以 `*w` 直接用；**不要跨函数返回 guard**。

### 3.7 Mutex\<T\> 与 RwLock（线程间可变共享）

**`Mutex<T>`** 是线程安全的内部可变性：`lock()` 返回 `MutexGuard<T>`（`Deref` 到 `&T`/`&mut T`），离开作用域自动解锁；**`RwLock<T>`** 区分读锁（可并发）与写锁（独占），读多写少时吞吐更好：

```rust
use std::sync::{Arc, Mutex};
use std::thread;

fn main() {
    let counter = Arc::new(Mutex::new(0));
    let mut handles = vec![];

    for _ in 0..4 {
        let m = Arc::clone(&counter);
        handles.push(thread::spawn(move || {
            let mut num = m.lock().unwrap(); // 加锁，拿到 MutexGuard
            *num += 1;                       // 经 guard 修改（DerefMut）
        }));                                 // guard 离开作用域自动解锁
    }

    for h in handles { h.join().unwrap(); }
    println!("result = {}", *counter.lock().unwrap()); // 4
}
```

要点与坑：
- **`lock()` 返回 `Result`**：线程 panic 时 `Mutex` 进入**中毒（poisoned）**状态，`lock()` 返回 `Err`；`unwrap()` 是示例写法，工程化处理见 ph11。
- **坑：guard 持有过久/跨 `.await`**——guard 不解锁就请求同一锁会死锁；ph12 异步中 guard 跨 `.await` 保持会卡死任务（编译器因 `Send` 要求报错）。
- 写多读少时 `RwLock` 反而比 `Mutex` 慢（读锁本身有原子开销）。

### 3.8 Weak\<T\> 与循环引用（升级 · 避免泄漏）

**循环引用**：两个 `Rc` 互相持有对方 → 引用计数互为支撑、永不归零 → 内存泄漏（Rust 不报错，因为是"逻辑泄漏"）。**`Weak<T>`** 是"不拥有"的引用：创建不增加**强引用计数**（只增 `weak_count`），`upgrade()` 返回 `Option<Rc<T>>`（目标已释放则 `None`）。用 `Weak` 打破环："父持子"用强引用、"子指父"用弱引用：

```rust
use std::cell::RefCell;
use std::rc::{Rc, Weak};

#[derive(Debug)]
struct Node {
    value: i32,
    parent: RefCell<Weak<Node>>,      // 弱引用：不增加强引用计数
    children: RefCell<Vec<Rc<Node>>>, // 强引用：持有子节点
}

fn main() {
    let leaf = Rc::new(Node {
        value: 3,
        parent: RefCell::new(Weak::new()),
        children: RefCell::new(vec![]),
    });

    let root = Rc::new(Node {
        value: 10,
        parent: RefCell::new(Weak::new()),
        children: RefCell::new(vec![Rc::clone(&leaf)]),
    });

    *leaf.parent.borrow_mut() = Rc::downgrade(&root); // 子指父：弱引用，不形成环

    println!("root strong = {}", Rc::strong_count(&root)); // 1（只有变量 root）
    println!("root weak   = {}", Rc::weak_count(&root));   // 1（leaf.parent）

    // 升级弱引用访问父节点（先绑定借用 guard，避免临时借用跨 if-let 存活）
    let parent_ref = leaf.parent.borrow();
    if let Some(parent) = parent_ref.upgrade() {
        println!("leaf 的父节点 value = {}", parent.value); // 10
    }
}
```

要点与坑：
- **`upgrade()` 返回 `Option`**：`Weak` 不保证目标还活着，取用必须处理 `None`——这是不增加计数"应有的代价"。
- **坑：漏掉 Weak 导致循环泄漏**——凡有"双向引用"的共享结构（树、图、缓存依赖）必须想清楚"谁强谁弱"；判据是**谁拥有谁**：父拥有子（强），子只是"认识"父（弱）；`strong_count`/`weak_count` 可观察计数验证环是否被打断。

### 3.9 智能指针组合模式（Rc\<RefCell\<T\>\> · Arc\<Mutex\<T\>\>）

单靠 `Rc` 不能改、单靠 `RefCell` 不能共享，组合起来就是"**多个 owner + 内部可变**"：`Rc<RefCell<T>>`（单线程）与 `Arc<Mutex<T>>`（多线程）是生态里最高频的两对组合——共享一份可变状态，任何持有者都能改，改完大家都能看到：

```rust
use std::cell::RefCell;
use std::rc::Rc;

#[derive(Debug, Default)]
struct Counter {
    value: i32,
}

fn main() {
    let counter = Rc::new(RefCell::new(Counter { value: 0 }));

    let view_a = Rc::clone(&counter);
    let view_b = Rc::clone(&counter);

    view_a.borrow_mut().value += 1;
    view_b.borrow_mut().value += 2;

    println!("counter = {:?}", counter.borrow()); // Counter { value: 3 }
    println!("strong  = {}", Rc::strong_count(&counter)); // 3
}
```

要点与坑：
- **借用路径与修改路径分离**：`counter.borrow_mut()` 里 `counter` 是 `&Rc<...>`，靠 deref coercion 一路解到 `RefCell`。
- **坑：组合层的借用冲突更隐蔽**——两个视图同时 `borrow_mut` 同样运行时 panic；排查时先确认"谁还握着 guard"。
- 多线程版只需把 `Rc<RefCell<T>>` 换成 `Arc<Mutex<T>>`，`lock()` 替代 `borrow_mut()`——结构同构，是"先单线程写对、再换并发"的迁移路径。

### 3.10 与裸指针对比

裸指针 `*const T`/`*mut T` 只是"内存地址"，**没有所有权、没有生命周期、没有自动释放**，使用必须 `unsafe`；智能指针则把"分配、释放、共享、借用"全部交给编译器/标准库追踪：

```rust
// C 风格（示意）：malloc/free 完全手动——忘记 free 就泄漏，重复 free 就 UB
// let p = libc::malloc(size_of::<i32>());
// ...使用 p...
// libc::free(p);

// Rust 智能指针：同样的堆分配，释放由 Box 的 Drop 自动完成
fn main() {
    let b = Box::new(7); // 等价于 malloc + 构造
    println!("{}", *b);  // 使用
}                        // 离开作用域自动 free：不可能忘记，也不可能重复释放
```

要点与坑：
- 裸指针是 `unsafe` 世界的入口（ph14 才深入）；本阶段**任何裸指针都不是必要工具**："想共享用 `Rc`/`Arc`，想可变共享用 `RefCell`/`Mutex`，想要非拥有引用用 `Weak`"。
- **坑：把 `Box` 当裸指针用**——`Box::into_raw` 取出裸指针后必须自己 `Box::from_raw` 回收，漏掉就是泄漏；无 `unsafe` 必要就别 `into_raw`。

## 4. 底层原理

### 4.1 Box 的堆分配与指针语义

`Box<T>` 在机器层面就是一个**单指针**（宽度 = `usize`），指向堆上一块 `size_of::<T>()` 的内存；`Box::new(x)` 等价于 `malloc` + 移动 `x` 进去，`Drop` 先 drop `T` 再释放内存。因为 `Box<T>` 大小固定为一个指针，递归类型 `List` 里的 `Box<List>` 让枚举总大小变成"标签 + 指针"，编译器才能算清布局；`Box<dyn Trait>` 是**胖指针**（数据指针 + 虚表指针），大小是两个 `usize`。`Box` 不引入任何共享语义，是最"纯粹"的所有权指针。

### 4.2 Rc/Arc 的控制块与引用计数（非原子 vs 原子）

`Rc<T>` 的堆布局是"**控制块 + 数据**"：`Rc::new` 一次分配两块内存——控制块含 `strong_count: usize`、`weak_count: usize`，紧挨着放 `T` 本体。`Rc::clone` 执行一次**非原子** `strong_count += 1`；drop 时 `strong_count -= 1`，归零则 drop `T` 并释放内存，若 `weak_count` 也为零连控制块一起释放。`Arc<T>` 的计数是 `AtomicUsize`，用 `fetch_add`/`fetch_sub`（release/acquire 内存序）保证并发下计数一致——这是它 `Send + Sync` 的根基，也解释了单线程下 `Arc` 比 `Rc` 慢。**注意计数器语义差异**：`strong_count` 控制"数据何时释放"，`weak_count` 控制"控制块何时释放"；只要还有 `Weak` 存活，控制块就不回收（`upgrade()` 才能安全查询）。

### 4.3 RefCell 的借用标志与运行时检查（对比编译期借用检查）

`RefCell<T>` 内部只有一个 `Cell<BorrowFlag>`：`borrow()` 把标志加 1（要求当前不是"可变借用中"），`borrow_mut()` 把标志置为负数（要求当前无任何借用）。与编译期借用检查对比：

| 维度 | 编译期借用检查（普通 `&`/`&mut`） | 运行时借用检查（`RefCell`） |
|------|----------------------------------|------------------------------|
| 检查时机 | 编译期，违规无法编译 | 运行期，违规 panic（`BorrowMutError`） |
| 借用范围 | 词法/非词法作用域（NLL） | guard 存活期间 |
| 额外开销 | 零 | 每次 borrow 一次计数增减（极小） |
| 适用场景 | 静态可证明安全的默认选择 | 需要内部可变性（`&self` 下修改） |
| 线程安全 | 由 `Send`/`Sync` 保证 | 非 `Sync`，单线程专用 |

编译期检查是"证明制"：编译器全局推理，证明不了就拒绝；`RefCell` 是"记账制"：运行时数借用次数，**冲突发生时才爆炸**。理解这层对比，就知道 `RefCell` 是"把正确性负担从编译器转移到程序员"的显式选择——代码要保证借用不重叠，同时接受运行时 panic 的可能。

### 4.4 Weak 如何打破循环（weak count 与强引用升级）

循环引用的成因：两个强引用互相持有，各自"最后释放"都依赖对方先释放。`Weak` 的解法是把环上**至少一条边降级为非拥有引用**：创建 `Weak` 不增加 `strong_count`，所以环上强引用计数能正常归零；归零时 `T` 被 drop、内存被回收，`Weak` 变成"悬空"状态（`strong_count == 0`）。`upgrade()` 的语义是"**如果还活着，临时借一个强引用**"：它把 `strong_count` 原子加 1，成功返回 `Some(Rc)`，失败（已释放）返回 `None`。这条"先检查再升级"的路径让 `Weak` 无法复活已释放的数据，`Option` 返回值就是这层安全性的接口表达。设计准则：**有环的共享结构里至少一条边必须用 `Weak`**，且选在"从属方向"（子→父、观察者→主体）。

### 4.5 Deref 解引用在编译器中的展开

`*x` 在 `x: Box<T>` 时展开为 `*(x.deref())`；deref coercion 是编译器在"类型不匹配但可转换"时的**隐式插入**：把 `&U` 变成 `&T` 需要 `U: Deref<Target = T>`，可连续多跳（`&Rc<String>` → `&String` → `&str`）。`x.method()` 的方法解析同样走 deref 链：在 `x`、`*x`、`**x`……逐层查找方法直到找到。**不对称性值得注意**：不可变解引用可以多跳，可变解引用只跳一层（`&mut U` 转 `&mut T` 需 `U: DerefMut`，且不能跨过不可变层）——这是借用规则在类型层的投影：`&mut` 不能"穿过"只读层。deref coercion 不是运行时转换，**编译期就展开成普通方法调用**，零成本。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 递归数据结构（链表、树、表达式） | `Box<T>` 打破无限大小 + `Drop` 自动释放 |
| 只读配置/元数据被多处共享 | `Rc<T>`（单线程）克隆共享，零拷贝 |
| 多线程共享只读数据 | `Arc<T>` 原子引用计数 |
| 线程间计数器/共享可变状态 | `Arc<Mutex<T>>`、`Arc<RwLock<T>>` |
| `&self` 方法内修改缓存/计数/观察者 | `RefCell<T>` 内部可变性（单线程） |
| 单线程共享可变状态（UI 模型、图节点） | `Rc<RefCell<T>>` 组合模式 |
| 父子/双向引用结构（树、图、缓存） | `Weak<T>` 打破循环引用 |
| 返回无法静态书写的迭代器链/trait 对象 | `Box<dyn Iterator>`、`Box<dyn Trait>` |

**不适合**此阶段的事项：
- 错误处理工程化（ph11）：`Mutex` 中毒恢复、`Result` 与 `?` 在共享状态上的工程化组合、`thiserror`/`anyhow` 错误类型设计。
- 异步编程中的共享状态（ph12）：`Arc` 跨 `.await`、锁在异步任务中的持有策略、`tokio::sync::Mutex` 与标准库 `Mutex` 的区别。
- unsafe 与裸指针（ph14）：`*const T`/`*mut T`、`Pin`、`Box::into_raw` 的手动管理——本阶段全部用安全抽象完成。

## 6. 代码示例

### 示例 1：用 Box 构建递归链表（递归类型 + Drop 自动释放）

roadmap 练习"用 Box 构建递归链表"：`Box` 让 `enum` 递归合法，整条链的所有权清晰、释放自动：

```rust
// 递归链表：Box<List> 让 List 的大小有限（指针），递归因此合法
#[derive(Debug)]
enum List {
    Cons(i32, Box<List>),
    Nil,
}

impl List {
    fn len(&self) -> usize {
        match self {
            List::Cons(_, tail) => 1 + tail.len(),
            List::Nil => 0,
        }
    }

    fn sum(&self) -> i32 {
        match self {
            List::Cons(v, tail) => v + tail.sum(),
            List::Nil => 0,
        }
    }
}

fn main() {
    let list = List::Cons(
        1,
        Box::new(List::Cons(
            2,
            Box::new(List::Cons(3, Box::new(List::Nil))),
        )),
    );

    println!("{list:?}");             // Cons(1, Cons(2, Cons(3, Nil)))
    println!("len = {}, sum = {}", list.len(), list.sum()); // len = 3, sum = 6
}
```

要点与坑：
- **`Box` 是递归类型的必需**：没有它 `List` 大小无限（E0072）；有了它每个 `Cons` 只多一个指针宽度。
- Drop 顺序与递归一致：释放从尾部开始，递归链天然无泄漏——对比 C 手写链表"遍历 free + 断链"的样板。

### 示例 2：用 Rc 共享只读配置（Rc 克隆 + 借用）

roadmap 练习"用 Rc 共享只读配置"：多份"引用"指向同一份配置，任何修改对所有使用者可见；只读共享不涉及 `RefCell`：

```rust
use std::rc::Rc;

#[derive(Debug)]
struct Config {
    host: String,
    port: u16,
    pool_size: u32,
}

fn print_config(cfg: &Config) {
    println!("connect {}:{} pool={}", cfg.host, cfg.port, cfg.pool_size);
}

fn main() {
    let cfg = Rc::new(Config {
        host: String::from("127.0.0.1"),
        port: 5432,
        pool_size: 16,
    });

    // Rc::clone 只增引用计数，堆上的 Config 只有一份
    let cfg_a = Rc::clone(&cfg);
    let cfg_b = cfg.clone(); // 等价写法

    print_config(&cfg);    // deref coercion：&Rc<Config> -> &Config
    print_config(&cfg_a);
    print_config(&cfg_b);

    println!("strong = {}", Rc::strong_count(&cfg)); // 3
}
```

要点与坑：
- **共享 = 引用计数，不是拷贝**：三个名字指向同一份 `Config`，任一修改（若可变）所有引用都看得到——这是"配置热更新"类需求的起点。
- 函数签名用 `&Config` 而非 `&Rc<Config>`：调用方可以传 `Rc`、`Box` 或裸引用，接口更通用——deref coercion 的价值所在。

### 示例 3：用 Arc\<Mutex\<T\>\> 做线程间计数（多线程共享可变状态）

roadmap 练习"用 Arc\<Mutex\<_\>\> 做线程间计数"：`Arc` 解决"每线程一份共享句柄"，`Mutex` 解决"同时只有一个线程改"，两者缺一不可：

```rust
use std::sync::{Arc, Mutex};
use std::thread;

fn main() {
    let counter = Arc::new(Mutex::new(0u64));
    let mut handles = vec![];

    for _ in 0..8 {
        let c = Arc::clone(&counter); // 每线程一个 Arc（计数 +1）
        handles.push(thread::spawn(move || {
            for _ in 0..1000 {
                let mut guard = c.lock().unwrap(); // 加锁拿到 MutexGuard
                *guard += 1;
            }                                      // guard 离开循环体即解锁
        }));
    }

    for h in handles {
        h.join().unwrap(); // 等待所有线程结束
    }

    let final_value = *counter.lock().unwrap();
    println!("total = {final_value}"); // 8 线程 × 1000 次 = 8000
    assert_eq!(final_value, 8000);
}
```

要点与坑：
- **为什么不能只用一个**：只用 `Arc` 无法改（`&T` 只读）；只用 `Mutex` 无法跨线程传所有权（进不了多个线程）。`Arc<Mutex<T>>` 才是"共享 + 可变"的并发组合。
- **若把 `Mutex` 换成 `RefCell` 编译失败**（`RefCell` 非 `Sync`，`Arc<RefCell<T>>` 不满足 `Send`）——编译器在提醒"这是并发场景"。
- `lock().unwrap()`：线程 panic 时 `Mutex` 中毒，后续 `lock` 返回 `Err`；工程化处理见 ph11。

### 示例 4：RefCell 内部可变性（运行时借用 + 演示 BorrowError panic）

roadmap 必会概念"内部可变性 + 运行时借用检查"的验证题：`&self` 接口下写日志，并用 `catch_unwind` 捕获借用冲突 panic（否则程序会直接崩溃）：

```rust
use std::cell::RefCell;
use std::panic;

// 内部可变性：log(&self) 不改签名也能往内部缓冲区写入
struct Logger {
    entries: RefCell<Vec<String>>,
}

impl Logger {
    fn new() -> Self {
        Logger { entries: RefCell::new(Vec::new()) }
    }

    fn log(&self, msg: &str) {
        self.entries.borrow_mut().push(msg.to_string());
    }

    fn snapshot(&self) -> Vec<String> {
        self.entries.borrow().clone()
    }
}

fn main() {
    let logger = Logger::new();
    logger.log("start");
    logger.log("query db");
    logger.log("done");
    println!("{:?}", logger.snapshot()); // ["start", "query db", "done"]

    // 演示 BorrowError：同时持有两个可变借用 -> 运行时 panic（编译期不报错）
    let result = panic::catch_unwind(|| {
        let cell = RefCell::new(42);
        let _b1 = cell.borrow_mut(); // 第一次可变借用
        let _b2 = cell.borrow_mut(); // 第二次可变借用：运行期 panic！
    });

    match result {
        Ok(_) => println!("未 panic"),
        Err(_) => println!("catch 到 BorrowMutError panic：RefCell 把借用冲突推迟到了运行时"),
    }
}
```

要点与坑：
- **同一份借用规则，两个检查时机**：上面 `catch_unwind` 内代码编译完全合法，只在运行期爆炸——这就是"运行时借用检查"与编译期检查的本质差异。
- **坑：panic 发生在"后到者"**——第二个 `borrow_mut` 是受害者，"肇事者"是仍活着的第一个 guard；排查时找"谁还握着 guard 没释放"。
- `snapshot` 里 `borrow().clone()`：借用只活在临时值里，clone 出拥有数据后借用即归还。

### 示例 5：规则树执行器（roadmap 推荐项目：Box 表达递归规则 + Rc 共享规则元数据）

roadmap 推荐项目"**规则树执行器**"：用 `Box` 表达递归规则（And/Or/Leaf 无限嵌套），用 `Rc` 共享规则元数据（同一份规则说明被多个节点复用）：

```rust
use std::rc::Rc;

// 规则元数据：Rc 共享——多个规则节点可以指向同一份元数据
#[derive(Debug)]
struct RuleMeta {
    name: &'static str,
    weight: u32,
}

// 递归规则树：Box 让 enum 无限嵌套合法
#[derive(Debug)]
enum RuleNode {
    Leaf(Rc<RuleMeta>),
    And(Vec<Box<RuleNode>>),
    Or(Vec<Box<RuleNode>>),
}

impl RuleNode {
    // 执行器指标：节点总数（递归遍历）
    fn node_count(&self) -> usize {
        match self {
            RuleNode::Leaf(_) => 1,
            RuleNode::And(children) | RuleNode::Or(children) => {
                1 + children.iter().map(|c| c.node_count()).sum::<usize>()
            }
        }
    }

    // 执行器指标：权重总和（递归求和）
    fn weight(&self) -> u32 {
        match self {
            RuleNode::Leaf(meta) => meta.weight,
            RuleNode::And(children) | RuleNode::Or(children) => {
                children.iter().map(|c| c.weight()).sum()
            }
        }
    }
}

fn main() {
    // 共享元数据：同一份规则说明在树中复用
    let auth_meta = Rc::new(RuleMeta { name: "auth_check", weight: 10 });
    let rate_meta = Rc::new(RuleMeta { name: "rate_limit", weight: 5 });

    let tree = RuleNode::And(vec![
        Box::new(RuleNode::Leaf(Rc::clone(&auth_meta))),
        Box::new(RuleNode::Or(vec![
            Box::new(RuleNode::Leaf(Rc::clone(&rate_meta))),
            Box::new(RuleNode::Leaf(Rc::clone(&auth_meta))), // 同一份元数据被两处引用
        ])),
    ]);

    println!("{tree:#?}");
    println!("节点数 = {}, 总权重 = {}", tree.node_count(), tree.weight());
    println!("auth_meta strong = {}", Rc::strong_count(&auth_meta)); // 2
}
```

要点与坑：
- **项目与知识点的对应**：`Box<RuleNode>` = 递归类型表达规则嵌套；`Rc<RuleMeta>` = 共享元数据（多节点复用同一份说明）；递归 `match` = 执行器的求值骨架。
- 扩展方向：给 `RuleNode` 加 `eval(&self, ctx) -> bool` 做真实规则求值（And 全真、Or 任一真、Leaf 查表）；元数据加 `description` 供日志输出——`Rc` 共享在此体现"一处修改、处处生效"。

## 7. 总结

### 关键要点

1. **`Box<T>` 是最基础的智能指针**：堆分配、单指针宽度、`Drop` 自动释放；三大用途是堆上大对象、递归类型（E0072 的解法）、trait 对象 `Box<dyn Trait>`。
2. **`Deref`/`DerefMut` 决定"像引用一样用"**：`*x` 展开为 `x.deref()`，deref coercion 让 `&Rc<T>`/`&Box<T>` 自动变 `&T`；可变解引用只跳一层，不可变可多跳。
3. **`Drop` 保证"走时必清"**：声明逆序 drop、字段声明顺序 drop；实现 `Drop` 的类型不能把字段 move 出 `&mut self`（E0509），也不能实现 `Copy`。
4. **`Rc` 是单线程引用计数**：`clone` O(1) 只增计数不拷贝数据，`strong_count` 归零才释放；非原子计数导致非 `Send`，跨线程编译报 E0277。
5. **`Arc` 是线程安全引用计数**：原子计数（`fetch_add`/`fetch_sub`）使其 `Send + Sync`；只解决共享，可变要配 `Mutex`/`RwLock`。
6. **`RefCell` 把借用检查挪到运行时**：`borrow`/`borrow_mut` + 运行时计数，违规 panic（`BorrowMutError`）；单线程专用（非 `Sync`），是"正确性负担显式交给程序员"的选择。
7. **`Weak` 打破循环引用**：不增加强引用计数，`upgrade()` 返回 `Option`；双向引用结构中"从属方向"必须用 `Weak`，否则计数永不归零、内存泄漏。
8. **组合模式是生态惯例**：`Rc<RefCell<T>>`（单线程共享可变）、`Arc<Mutex<T>>`（多线程共享可变），结构同构、迁移只需换类型。
9. **裸指针不是本阶段的工具**：`*const T`/`*mut T` 无所有权、无自动释放、需 `unsafe`；安全场景全部用智能指针表达。

### 跨语言对比：所有权与共享

| 维度 | Rust 智能指针 | C++ 智能指针 | Java 引用 | Go GC | C 手动 |
|------|--------------|--------------|-----------|-------|--------|
| 释放方式 | 编译期 + `Drop`（RAII） | 析构函数（RAII） | GC 不可控 | GC 并发回收 | `free()` 手动 |
| 共享所有权 | `Rc`/`Arc` 引用计数 | `shared_ptr` 引用计数 | 所有引用天然共享 | 所有变量天然共享 | 无（裸指针） |
| 循环引用处理 | `Weak` 显式打破 | `weak_ptr` 显式打破 | GC 自动回收环 | GC 自动回收环 | 无（靠自觉） |
| 线程安全 | 编译期 `Send`/`Sync` 检查 | 无编译期检查 | JMM + 锁 | goroutine 共享 + 锁 | 无 |
| 内部可变性 | `RefCell`/`Mutex` 显式声明 | `mutable` 关键字 | 默认可变 | 默认可变 | 默认可变 |
| 悬垂/野指针 | 编译期禁止 | 裸指针可悬垂 | 不可能 | 不可能 | 常见事故源 |

### 阶段验收标准

- 能区分 `Box`、`Rc`、`Arc` 的场景：单 owner 堆分配用 `Box`，单线程多 owner 用 `Rc`，多线程共享用 `Arc`（需要可变再叠加 `RefCell`/`Mutex`）。
- 能说明 `RefCell` 的风险：借用冲突从编译期推迟到运行期，违规时 panic（`BorrowMutError`）；guard 存活期间持续占用借用是隐蔽的失败模式。
- 能避免循环引用泄漏：识别双向引用结构，用 `Weak` 打断"从属方向"的强引用边，用 `strong_count`/`weak_count` 验证。
- 能说出 `Deref`/`Drop` 的作用：deref coercion 让智能指针像引用一样用（零成本），`Drop` 保证资源自动释放（RAII）。
- 能区分 `Rc` 与 `Arc` 的适用边界，并解释"为什么 `Arc<RefCell<T>>` 编译失败、`Arc<Mutex<T>>` 才行"。

### 进入下一阶段前

确保能完成以下练习：

- 用 `Box` 构建递归链表（提示：`enum List { Cons(i32, Box<List>), Nil }`，实现 `len`/`sum` 递归方法；对照示例 1）。
- 用 `Rc` 共享只读配置（提示：`Rc::new` 一次、`Rc::clone` 多次，函数参数写 `&Config` 靠 deref coercion 收 `&Rc<Config>`；对照示例 2）。
- 用 `Arc<Mutex<_>>` 做线程间计数（提示：每线程 `Arc::clone` + `move` 闭包，循环内 `lock().unwrap()` 修改，`join` 汇总；对照示例 3）。
- 制造一次 `RefCell` 的 `BorrowMutError`（提示：`let b1 = cell.borrow_mut(); let b2 = cell.borrow_mut();` 观察运行期 panic；对照示例 4）。
- 构造一个带 `parent` 的树并用 `Weak` 消除循环泄漏（提示：父持子强引用、子指父弱引用，`upgrade()` 处理 `None`；对照 3.8）。
- 口述 `Rc<RefCell<T>>` 与 `Arc<Mutex<T>>` 的异同（提示：前者单线程、`borrow_mut`，后者多线程、`lock`；报错时机分别为 panic 与 `Result`）。

### 推荐项目

- **规则树执行器**（roadmap 推荐项目）：用 `Box` 表达递归规则（And/Or/Leaf 无限嵌套），用 `Rc` 共享规则元数据。示例 5 已给出核心骨架。扩展方向：实现 `eval(&self, ctx) -> bool` 做真实规则求值、给元数据加 `description` 支持日志输出、把 `Rc` 换成 `Arc` 让规则树跨线程共享（配合 `Mutex` 共享求值上下文）。

### 下一阶段

[错误处理与工程质量阶段](../ph11-error-handling/11-error-handling.md) —— thiserror/anyhow、错误类型设计、panic 策略、测试与 CI。智能指针阶段学会了"数据如何被共享与可变"，错误处理阶段则回答"共享状态下出错怎么办"：`Mutex` 中毒的恢复策略、`Result` 与 `?` 在组合类型上的传播、为库定义精确的错误类型——两个阶段的知识将在真实工程的错误路径上汇合。
