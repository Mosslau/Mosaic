# Rust 智能指针阶段

> 面向数据基础设施、异步网络服务方向：本阶段掌握常见智能指针，能表达堆分配、共享所有权和内部可变性——让"数据放哪、谁拥有、能不能改"从编译期规则落到可组合的标准库类型上。

## 1. 概述

Rust 智能指针阶段的定位是：**能根据场景选择 `Box<T>`（堆分配）、`Rc<T>`/`Arc<T>`（共享所有权）、`RefCell<T>`/`Mutex<T>`（内部可变性），理解 `Deref`/`Drop` 两个 trait 如何塑造"用起来像引用、走时自动清理"的体验，并能用 `Weak<T>` 打破循环引用**。本阶段是 ph02 所有权阶段的进阶：所有权模型本身是"一个值一个 owner"，而真实程序里数据需要被多处共享、需要在只读接口下修改、需要跨线程传递——智能指针正是所有权模型在这些场景下的标准答案。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 堆分配 | `Box<T>`：把值放到堆上，离开作用域自动释放 |
| 递归类型与 trait 对象 | `Box` 打破递归类型的无限大小（E0072），`Box<dyn Trait>` 擦除具体类型 |
| 单线程共享所有权 | `Rc<T>`：非原子引用计数，`clone` 只增计数不复制数据 |
| 线程安全共享所有权 | `Arc<T>`：原子引用计数，配合 `Mutex<T>`/`RwLock` 做线程间可变共享 |
| 内部可变性 | `RefCell<T>`：借用检查从编译期挪到运行期，`borrow`/`borrow_mut` |
| 自定义析构与解引用 | `Drop`（自动清理）、`Deref`/`DerefMut`（像引用一样用） |
| 循环引用与 Weak | `Weak<T>`：弱引用不增加强引用计数，`upgrade()` 升级访问，避免泄漏 |
| 组合模式 | `Rc<RefCell<T>>`（单线程共享可变）、`Arc<Mutex<T>>`（多线程共享可变） |

这个阶段只涉及智能指针（`Box`/`Rc`/`Arc`/`RefCell`/`Mutex`/`Weak`/`Drop`）的堆分配、共享所有权、内部可变性与循环引用处理，**不涉及错误处理工程化（`Mutex` 中毒恢复、`Result` 与 `?` 在共享状态上的组合）、异步编程中的共享状态（`Arc` 跨 `.await`、`tokio::sync::Mutex` 与标准库 `Mutex` 的区别）和 unsafe 与裸指针（`*const T`/`*mut T`、`Pin`、`Box::into_raw` 手动管理）** — 那些是 ph11 错误处理与工程质量阶段、ph12 并发与异步阶段、ph14 Unsafe Rust 与安全抽象阶段的内容（ph12 目录已建；ph14 目录待建）。承接 ph09 集合与迭代器阶段：迭代器链产出共享引用、`Box<dyn Iterator>` 装箱返回都会用到本阶段类型。

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
| 2021 | edition 2021：闭包捕获更精确（RFC 2229） | 智能指针 API 保持稳定，组合模式成为生态惯例 |

本文示例以 **Rust 2021 edition（rustc 1.92.0）** 为基线（2021 edition 的闭包捕获规则（RFC 2229）影响 `Rc`/`Arc` 组合示例中 `move` 闭包的写法——按路径精确捕获、未用变量不捕获，且全仓库代码层统一用 `rustc --edition 2021` 单文件编译；注意 `rustc` 直接编译单文件默认仍是 edition 2015，cargo 新建项目自 1.56 起默认最新 edition）。智能指针核心 API（`Box`/`Rc`/`Arc`/`RefCell`/`Weak`/`Deref`/`Drop`）自 1.0 起即稳定，是本阶段语法中最稳定的部分——无论 edition 如何演进，这些类型的语义都不会变。

## 3. 语法与参数

### 3.1 Box\<T\>（堆分配 · 递归类型 · trait 对象）

**`Box<T>`** 把值分配在**堆**上，栈上只留一个指针；`Box` 离开作用域时自动 `free`（通过 `Drop`）。三个典型用途：堆分配、打破递归类型、装箱 trait 对象：

```rust
fn main() {
    let b = Box::new(42);      // 在堆上分配 i32，栈上存指针
    println!("{}", *b);

    // 递归类型：没有 Box 时 List 大小无限，编译不过（E0072，已实测）
    // #[allow(dead_code)]：教学示例，字段仅供 derive(Debug) 打印读取，rustc 仍报「字段未读」
    #[allow(dead_code)]
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
- **坑：递归类型忘加 `Box`（E0072）**——`enum List { Cons(i32, List) }` 报 "recursive type has infinite size"（已实测），编译器会提示"insert some indirection（如 `Box`）"。
- **坑：`Box` 移动后不可再用（E0382）**——`Box<T>` 是拥有型指针，`let x = b; let y = b;` 第二次移动报 "use of moved value"（已实测）；转移所有权后旧绑定失效，这与裸指针"复制地址"是本质区别。

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

**`Drop` trait** 定义值离开作用域时的清理逻辑（`fn drop(&mut self)`），`Box`/`Rc`/`MutexGuard` 都靠它自动释放资源。变量按**声明逆序** drop，结构体先跑 `impl Drop` 体、再按字段声明顺序 drop 字段；**不能显式调用 `drop` 方法**（只能用 `std::mem::drop(x)` 提前移交所有权触发）。以下顺序为实测输出（rustc 1.92.0，完整代码见示例 2）：

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
    // 实测输出顺序：Guard B 被释放 -> Guard A 被释放
}
```

要点与坑：
- **坑：Drop 与移动语义冲突（E0507 / E0509，均已实测）**——实现 `Drop` 的类型不能把字段 move 出 `&mut self`（报 E0507：cannot move out of `self.x` which is behind a mutable reference），也不能把整个值解构 move（报 E0509：cannot move out of type which implements the `Drop` trait）；需要"拿回字段"先用 `Option::take`。
- `Drop` 与 `Copy` 互斥（位复制后谁负责析构？语义冲突）；依赖释放顺序时要显式缩小作用域或 `std::mem::drop` 提前触发。

### 3.4 Rc\<T\>（单线程引用计数 · clone 语义）

**`Rc<T>`（Reference Counted）** 让一个值被多个 owner 共享：每次 `Rc::clone(&x)` 只是**引用计数 +1**，不复制堆上数据；最后一个 `Rc` 离开作用域时计数归零才真正释放。计数是**非原子的**，因此 `Rc` **不是 `Send`**，只能单线程使用：

```rust
use std::rc::Rc;

fn main() {
    let a = Rc::new(String::from("config"));
    println!("strong = {}", Rc::strong_count(&a)); // 1（已实测）

    let b = Rc::clone(&a); // 引用计数 +1，堆上字符串只存一份
    let c = a.clone();
    println!("strong = {}", Rc::strong_count(&a)); // 3（已实测）
    println!("{} {} {}", a, b, c);
}
```

要点与坑：
- **`Rc::clone` 是浅的**：只增计数不拷贝数据，O(1)；对比 `String::clone` 深拷贝 O(n)——这是共享的收益来源。
- **坑：`Rc` 跨线程（E0277，已实测）**——`Rc` 没实现 `Send`，`thread::spawn` 里移动 `Rc` 报 "`Rc<String>` cannot be sent between threads safely"（rustc 1.92.0 的 help 仅为 "the trait `Send` is not implemented for `Rc<String>`"，并不提示换类型；改用 `Arc` 是工程上的解法，不是编译器输出）。演示时注意闭包内要**真正使用** `Rc` 变量（`let _ = r` 这种写法不捕获变量、闭包为空，会绕开报错）。
- `Rc` 默认不可变：`rc.value = 5` 直接改会报 E0594（cannot assign to data in an `Rc`，已实测）；想"多 owner 且能改"要配 `RefCell`（见 3.9）。

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
- **多线程下 `Arc` 的 drop 顺序由调度决定、顺序不定**：示例只断言确定性结果（计数），不打印依赖线程时序的 drop 顺序。

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
    // let r2 = cell.borrow_mut(); // 运行期 panic（见下方要点，消息已实测）
}
```

要点与坑：
- **坑：借用冲突在运行时 panic（消息已实测）**——`borrow_mut()` 时已有活跃借用，panic 消息为 `RefCell already borrowed`；`borrow()` 时已有可变借用，消息为 `RefCell already mutably borrowed`（panic payload 类型分别是 `BorrowMutError`/`BorrowError`）。guard 忘记 drop（如放进长生命周期结构体）会让后续借用一直失败，且 panic 发生在"受害者"而非"肇事者"处，难排查。
- **`RefCell` 不是 `Sync`**：单线程专用；多线程可变共享用 `Mutex`。
- 借用 guard（`Ref`/`RefMut`）实现 `Deref`，所以 `*w` 直接用；**不要跨函数返回 guard**，也不要让 guard 活过需要 drop 值的时刻（guard 持有借用会阻止 move，报 E0505，见练习 5 参考实现）。

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
- **`lock()` 返回 `Result`**：线程 panic 时 `Mutex` 进入**中毒（poisoned）**状态，`lock()` 返回 `Err`；`unwrap()` 是示例写法，工程化处理见 ph11 错误处理与工程质量阶段。
- **坑：guard 持有过久/跨 `.await`**——guard 不解锁就请求同一锁会死锁；ph12 并发与异步阶段中 guard 跨 `.await` 保持会卡死任务（编译器因 `Send` 要求报错）。
- 写多读少时 `RwLock` 反而比 `Mutex` 慢（读锁本身有原子开销）。

### 3.8 Weak\<T\> 与循环引用（升级 · 避免泄漏）

**循环引用**：两个 `Rc` 互相持有对方 → 引用计数互为支撑、永不归零 → 内存泄漏。**注意：循环引用不报编译错误——没有错误码，它是运行期"逻辑泄漏"**（`Rc` 的 drop 不触发，进程退出时由 OS 回收）。**`Weak<T>`** 是"不拥有"的引用：创建不增加**强引用计数**（只增 `weak_count`），`upgrade()` 返回 `Option<Rc<T>>`（目标已释放则 `None`）。用 `Weak` 打破环："父持子"用强引用、"子指父"用弱引用：

```rust
use std::cell::RefCell;
use std::rc::{Rc, Weak};

// #[allow(dead_code)]：教学示例，children 字段只写入未读取，rustc 报「字段未读」
#[allow(dead_code)]
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

    // 以下计数为实测输出：root strong=1 weak=1；leaf strong=2 weak=0
    println!("root strong = {}, weak = {}", Rc::strong_count(&root), Rc::weak_count(&root));
    println!("leaf strong = {}, weak = {}", Rc::strong_count(&leaf), Rc::weak_count(&leaf));

    // 升级弱引用访问父节点（先绑定借用 guard，避免临时借用跨 if-let 存活）
    let parent_ref = leaf.parent.borrow();
    if let Some(parent) = parent_ref.upgrade() {
        println!("leaf 的父节点 value = {}", parent.value); // 10
    }
}
```

要点与坑：
- **`upgrade()` 返回 `Option`**：`Weak` 不保证目标还活着，取用必须处理 `None`——这是不增加计数"应有的代价"。
- **坑：漏掉 Weak 导致循环泄漏**——凡有"双向引用"的共享结构（树、图、缓存依赖）必须想清楚"谁强谁弱"；判据是**谁拥有谁**：父拥有子（强），子只是"认识"父（弱）；`strong_count`/`weak_count` 可观察计数验证环是否被打断（实测：父先释放后，子的 `upgrade()` 返回 `None`，`Drop` 正常触发——见示例 6）。

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

    // 以下输出为实测：Counter { value: 3 }；strong = 3
    println!("counter = {:?}", counter.borrow());
    println!("strong  = {}", Rc::strong_count(&counter));
}
```

要点与坑：
- **借用路径与修改路径分离**：`counter.borrow_mut()` 里 `counter` 是 `&Rc<...>`，靠 deref coercion 一路解到 `RefCell`。
- **坑：组合层的借用冲突更隐蔽**——两个视图同时 `borrow_mut` 同样运行时 panic；排查时先确认"谁还握着 guard"。
- 多线程版只需把 `Rc<RefCell<T>>` 换成 `Arc<Mutex<T>>`，`lock()` 替代 `borrow_mut()`——结构同构，是"先单线程写对、再换并发"的迁移路径。
- **坑：`Arc<RefCell<T>>` 编译失败（E0277，已实测）**——`RefCell` 非 `Sync`，跨线程共享报 "`RefCell<i32>` cannot be shared between threads safely"；rustc 1.92.0 的实际 note 是 "required for `Arc<RefCell<i32>>` to implement `Send`"，并无 `Mutex` 建议——换 `Mutex` 是工程上的解法，不是编译器提示。

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
- 裸指针是 `unsafe` 世界的入口（ph14 Unsafe Rust 与安全抽象阶段才深入，ph14 目录待建）；本阶段**任何裸指针都不是必要工具**："想共享用 `Rc`/`Arc`，想可变共享用 `RefCell`/`Mutex`，想要非拥有引用用 `Weak`"。
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
| 检查时机 | 编译期，违规无法编译 | 运行期，违规 panic（`BorrowMutError`/`BorrowError`） |
| 借用范围 | 词法/非词法作用域（NLL） | guard 存活期间 |
| 额外开销 | 零 | 每次 borrow 一次计数增减（极小） |
| 适用场景 | 静态可证明安全的默认选择 | 需要内部可变性（`&self` 下修改） |
| 线程安全 | 由 `Send`/`Sync` 保证 | 非 `Sync`，单线程专用 |

编译期检查是"证明制"：编译器全局推理，证明不了就拒绝；`RefCell` 是"记账制"：运行时数借用次数，**冲突发生时才爆炸**（panic 消息已实测：`RefCell already borrowed` / `already mutably borrowed`）。理解这层对比，就知道 `RefCell` 是"把正确性负担从编译器转移到程序员"的显式选择——代码要保证借用不重叠，同时接受运行时 panic 的可能。

### 4.4 Weak 如何打破循环（weak count 与强引用升级）

循环引用的成因：两个强引用互相持有，各自"最后释放"都依赖对方先释放。`Weak` 的解法是把环上**至少一条边降级为非拥有引用**：创建 `Weak` 不增加 `strong_count`，所以环上强引用计数能正常归零；归零时 `T` 被 drop、内存被回收，`Weak` 变成"悬空"状态（`strong_count == 0`）。`upgrade()` 的语义是"**如果还活着，临时借一个强引用**"：它把 `strong_count` 加 1（Rc 的计数器是 `Cell<usize>`，非原子；仅 `Arc::upgrade` 才是原子 `fetch_add`），成功返回 `Some(Rc)`，失败（已释放）返回 `None`。这条"先检查再升级"的路径让 `Weak` 无法复活已释放的数据，`Option` 返回值就是这层安全性的接口表达。设计准则：**有环的共享结构里至少一条边必须用 `Weak`**，且选在"从属方向"（子→父、观察者→主体）。实测验证：父先释放后，子的 `upgrade()` 返回 `None`（示例 6 前半段）；不用 `Weak` 时两个 `Rc` 互指，句柄 drop 后 `Drop` 不触发、计数停留 1/1（示例 6 后半段，故意泄漏演示）。

### 4.5 Deref 解引用在编译器中的展开

`*x` 在 `x: Box<T>` 时展开为 `*(x.deref())`；deref coercion 是编译器在"类型不匹配但可转换"时的**隐式插入**：把 `&U` 变成 `&T` 需要 `U: Deref<Target = T>`，可连续多跳（`&Rc<String>` → `&String` → `&str`）。`x.method()` 的方法解析同样走 deref 链：在 `x`、`*x`、`**x`……逐层查找方法直到找到。**不对称性值得注意**：可变解引用同样可以多跳——链上每一层都实现 `DerefMut` 即可（实测 `&mut Box<Box<i32>>` → `&mut i32` 编译通过）；但不能穿过只实现 `Deref` 的层（如 `Rc`），`&mut Rc<T>` 无法解到 `&mut T`——这是借用规则在类型层的投影：`&mut` 不能"穿过"只读层。deref coercion 不是运行时转换，**编译期就展开成普通方法调用**，零成本。

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

**不适合**此阶段的事项（属于后续阶段，这里不展开）：
- 错误处理工程化（ph11 错误处理与工程质量阶段）：`Mutex` 中毒恢复、`Result` 与 `?` 在共享状态上的工程化组合、`thiserror`/`anyhow` 错误类型设计。
- 异步编程中的共享状态（[ph12 并发与异步阶段](../ph12-concurrency-async/12-concurrency-async.md)）：`Arc` 跨 `.await`、锁在异步任务中的持有策略、`tokio::sync::Mutex` 与标准库 `Mutex` 的区别。
- unsafe 与裸指针（ph14 Unsafe Rust 与安全抽象阶段，目录待建）：`*const T`/`*mut T`、`Pin`、`Box::into_raw` 的手动管理——本阶段全部用安全抽象完成。

## 6. 代码示例

本节展示完整可运行示例，完整文件在 [`examples/`](./examples/) 目录，全部为零第三方依赖的单文件（智能指针全在 `std`），可用 `rustc --edition 2021` 直接编译运行（已验证：rustc 1.92.0，编译零警告）。

### 示例 1：用 Box 构建递归链表（堆分配 + 递归类型）

roadmap 练习"用 Box 构建递归链表"：`Box` 让 `enum` 递归合法，整条链的所有权清晰、释放自动：

```rust
// examples/ex01-box-recursive-list.rs —— Box 堆分配与递归类型：不用 Box 报 E0072（已验证：rustc 1.92.0，rustc --edition 2021 单文件编译）
#[derive(Debug)]
enum List {
    Cons(i32, Box<List>), // Box 打破递归：List 的大小变为「标签 + 指针」，有限
    Nil,
}

impl List {
    /// 链表长度：递归求值（Cons = 1 + 尾部长度）
    fn len(&self) -> usize {
        match self {
            List::Cons(_, tail) => 1 + tail.len(),
            List::Nil => 0,
        }
    }

    /// 链表元素和：递归求和
    fn sum(&self) -> i32 {
        match self {
            List::Cons(v, tail) => v + tail.sum(),
            List::Nil => 0,
        }
    }
}

fn main() {
    // 堆上分配一串：1 -> 2 -> 3 -> Nil，每个 Box 指向堆上下一节
    let list = List::Cons(
        1,
        Box::new(List::Cons(2, Box::new(List::Cons(3, Box::new(List::Nil))))),
    );

    println!("{list:?}");                      // Cons(1, Cons(2, Cons(3, Nil)))
    println!("len = {}, sum = {}", list.len(), list.sum()); // len = 3, sum = 6

    // 整条链的所有权归 list 一人所有，main 结束时 Box 从尾部开始递归释放，无需手写 free
    // 对比 C 手写链表「遍历 free + 断链」的样板——这是 Drop（RAII）带来的差异
}
```

要点与坑：
- **`Box` 是递归类型的必需**：没有它 `List` 大小无限（E0072，已实测）；有了它每个 `Cons` 只多一个指针宽度。
- Drop 顺序与递归一致：释放从尾部开始，递归链天然无泄漏——对比 C 手写链表"遍历 free + 断链"的样板。

### 示例 2：Drop 析构顺序（变量逆序 · 结构体字段顺序 · 提前释放）

演示 `Drop` 的三条顺序规则，输出顺序为实测结果：

```rust
// examples/ex02-drop-order.rs —— Drop 析构顺序三条规则，输出顺序已实测（已验证：rustc 1.92.0）
struct Guard {
    name: &'static str,
    tag: u32,
}

impl Drop for Guard {
    fn drop(&mut self) {
        println!("drop Guard {} (tag {})", self.name, self.tag);
    }
}

struct Outer {
    f1: Guard,
    f2: Guard,
}

impl Drop for Outer {
    fn drop(&mut self) {
        // impl Drop 体先于字段析构执行
        println!("drop Outer（impl Drop 体先执行，然后字段按声明顺序析构）");
    }
}

fn main() {
    // 规则 ①：变量按声明逆序 drop——A 先声明，最后释放
    let _a = Guard { name: "A", tag: 1 };
    {
        let _b = Guard { name: "B", tag: 2 };
    } // 内层块结束：B 先 drop（声明逆序的第一层体现）

    // 规则 ③：std::mem::drop 提前移交所有权触发析构，C 不再等到 main 结束
    let c = Guard { name: "C", tag: 3 };
    std::mem::drop(c); // 等价于「立即释放」，与 drop(c) 不能是方法调用（会触发二次 drop，编译错）

    // 规则 ②：结构体的 Drop 体先执行，再按字段声明顺序 f1 -> f2 析构
    let o = Outer {
        f1: Guard { name: "f1", tag: 4 },
        f2: Guard { name: "f2", tag: 5 },
    };
    println!("o 的字段: f1={}, f2={}", o.f1.tag, o.f2.tag);

    // main 结束时的实际输出顺序（实测）：
    // drop Outer（impl Drop 体）-> drop Guard f1 -> drop Guard f2 -> drop Guard A
}
```

要点与坑：
- **三条规则的先后**：作用域结束触发析构；同作用域内变量按声明**逆序**；结构体先跑 `impl Drop` 体、再按字段声明**顺序**析构；`std::mem::drop` 可在任意时刻提前触发。
- `std::mem::drop` 是普通函数（接管所有权后立即析构），`x.drop()` 方法调用是**不存在的**——`Drop` 的 `drop` 不允许显式调用。

### 示例 3：用 Rc 共享只读配置（引用计数 · deref coercion）

roadmap 练习"用 Rc 共享只读配置"：多份"引用"指向同一份配置，任何修改对所有使用者可见；只读共享不涉及 `RefCell`：

```rust
// examples/ex03-rc-shared-config.rs —— Rc 引用计数共享只读配置，strong 计数已实测 1 -> 3 -> 2（已验证：rustc 1.92.0）
use std::rc::Rc;

#[derive(Debug)]
struct Config {
    host: String,
    port: u16,
    pool_size: u32,
}

// 参数写 &Config 而非 &Rc<Config>：调用方可传 Rc、Box 或裸引用——deref coercion 的价值
fn print_config(cfg: &Config) {
    println!("connect {}:{} pool={}", cfg.host, cfg.port, cfg.pool_size);
}

fn main() {
    let cfg = Rc::new(Config {
        host: String::from("127.0.0.1"),
        port: 5432,
        pool_size: 16,
    });
    println!("strong = {}", Rc::strong_count(&cfg)); // 1（只有变量 cfg 一个强引用）

    // Rc::clone 只增引用计数，堆上的 Config 始终只有一份（对比 String::clone 深拷贝）
    let cfg_a = Rc::clone(&cfg);
    let cfg_b = cfg.clone(); // 等价写法
    println!("strong = {}", Rc::strong_count(&cfg)); // 3

    // deref coercion：&Rc<Config> 自动解引用成 &Config
    print_config(&cfg);
    print_config(&cfg_a);
    print_config(&cfg_b);

    // drop 掉一个引用：计数回落，数据仍在（还有两个强引用）
    drop(cfg_a);
    println!("strong = {}", Rc::strong_count(&cfg)); // 2
}
```

要点与坑：
- **共享 = 引用计数，不是拷贝**：三个名字指向同一份 `Config`，任一修改（若可变）所有引用都看得到——这是"配置热更新"类需求的起点。
- 函数签名用 `&Config` 而非 `&Rc<Config>`：调用方可以传 `Rc`、`Box` 或裸引用，接口更通用——deref coercion 的价值所在。

### 示例 4：RefCell 内部可变性 + Rc\<RefCell\<T\>\> 组合（运行时借用 · BorrowMutError）

roadmap 必会概念"内部可变性 + 运行时借用检查"的验证题：`&self` 接口下写日志，用 `catch_unwind` 捕获借用冲突 panic（否则程序会直接崩溃），最后给出 `Rc<RefCell<T>>` 组合：

```rust
// examples/ex04-refcell-combo.rs —— RefCell 内部可变性 + Rc<RefCell<T>> 组合；panic 消息与计数已实测（已验证：rustc 1.92.0）
use std::cell::RefCell;
use std::panic;
use std::rc::Rc;

// ===== 内部可变性：&self 接口下修改内部状态 =====

struct Logger {
    entries: RefCell<Vec<String>>,
}

impl Logger {
    fn new() -> Self {
        Logger { entries: RefCell::new(Vec::new()) }
    }

    // 签名只有 &self，却能写入 entries——RefCell 把借用检查从编译期挪到运行期
    fn log(&self, msg: &str) {
        self.entries.borrow_mut().push(msg.to_string());
    }

    fn snapshot(&self) -> Vec<String> {
        self.entries.borrow().clone()
    }
}

// ===== Rc<RefCell<T>> 组合：多个 owner 共享一份可变状态 =====

#[derive(Debug, Default)]
struct Counter {
    value: i32,
}

fn main() {
    // --- 内部可变性 ---
    let logger = Logger::new();
    logger.log("start");
    logger.log("query db");
    logger.log("done");
    println!("日志 = {:?}", logger.snapshot()); // ["start", "query db", "done"]

    // --- BorrowMutError：编译期完全合法，运行期 panic ---
    // 两个 borrow_mut 同时存活 -> 运行期 panic。用 catch_unwind 捕获，避免程序崩溃。
    let result = panic::catch_unwind(|| {
        let cell = RefCell::new(42);
        let _b1 = cell.borrow_mut(); // 第一次可变借用，guard 存活
        let _b2 = cell.borrow_mut(); // 第二次可变借用：运行期 panic！
    });
    match result {
        Ok(_) => println!("未 panic"),
        Err(_) => println!(
            "catch 到 BorrowMutError panic（panic 消息为 \"RefCell already borrowed\"，payload 类型是 BorrowMutError）"
        ),
    }

    // ===== 故意运行会 panic（RefCell already borrowed），请勿取消注释 =====
    // let cell = RefCell::new(42);
    // let _b1 = cell.borrow_mut();
    // let _b2 = cell.borrow_mut(); // 运行期 panic: "RefCell already borrowed"

    // --- Rc<RefCell<T>> 组合：两个视图共享同一个 Counter，都能改、都看得到 ---
    let counter = Rc::new(RefCell::new(Counter { value: 0 }));
    let view_a = Rc::clone(&counter);
    let view_b = Rc::clone(&counter);

    view_a.borrow_mut().value += 1; // 经 RefMut 修改（DerefMut 解引用到 Counter）
    view_b.borrow_mut().value += 2;

    println!("counter = {:?}", counter.borrow()); // Counter { value: 3 }
    println!("strong  = {}", Rc::strong_count(&counter)); // 3（counter + view_a + view_b）
}
```

要点与坑：
- **同一份借用规则，两个检查时机**：上面 `catch_unwind` 内代码编译完全合法，只在运行期爆炸——这就是"运行时借用检查"与编译期检查的本质差异。
- **坑：panic 发生在"后到者"**——第二个 `borrow_mut` 是受害者，"肇事者"是仍活着的第一个 guard；排查时找"谁还握着 guard 没释放"。运行本文件时 stderr 会打印一行 `RefCell already borrowed`，这是被 `catch_unwind` 捕获的 panic 消息（程序退出码 0，正常继续）。
- `snapshot` 里 `borrow().clone()`：借用只活在临时值里，clone 出拥有数据后借用即归还。

### 示例 5：用 Arc\<Mutex\<T\>\> 做线程间计数（多线程共享可变状态）

roadmap 练习"用 Arc\<Mutex\<_\>\> 做线程间计数"：`Arc` 解决"每线程一份共享句柄"，`Mutex` 解决"同时只有一个线程改"，两者缺一不可：

```rust
// examples/ex05-arc-mutex-counter.rs —— Arc<Mutex<u64>> 线程间计数：8 线程 × 1000 次 = 8000，已实测（已验证：rustc 1.92.0）
use std::sync::{Arc, Mutex};
use std::thread;

fn main() {
    let counter = Arc::new(Mutex::new(0u64));
    let mut handles = vec![];

    for _ in 0..8 {
        let c = Arc::clone(&counter); // 每线程一份 Arc（引用计数 +1，数据仍是一份）
        handles.push(thread::spawn(move || {
            for _ in 0..1000 {
                let mut guard = c.lock().unwrap(); // 加锁拿到 MutexGuard（DerefMut 到 &mut u64）
                *guard += 1;
            } // guard 离开循环体即解锁——锁的持有范围由 guard 作用域决定
        }));
    }

    for h in handles {
        h.join().unwrap(); // 等待所有线程结束，保证计数全部完成
    }

    let final_value = *counter.lock().unwrap();
    println!("total = {final_value}"); // 8 线程 × 1000 次 = 8000
    assert_eq!(final_value, 8000);
}
```

要点与坑：
- **为什么不能只用一个**：只用 `Arc` 无法改（`&T` 只读）；只用 `Mutex` 无法跨线程传所有权（进不了多个线程）。`Arc<Mutex<T>>` 才是"共享 + 可变"的并发组合。
- **若把 `Mutex` 换成 `RefCell` 编译失败**（`RefCell` 非 `Sync`，`Arc<RefCell<T>>` 不满足 `Send`，E0277 已实测）——编译器在提醒"这是并发场景"。
- `lock().unwrap()`：线程 panic 时 `Mutex` 中毒，后续 `lock` 返回 `Err`；工程化处理见 ph11 错误处理与工程质量阶段。多线程下 `Arc` 的 drop 顺序不定，本示例只断言确定性计数 8000。

### 示例 6：用 Weak 打破循环引用（计数实测 · 循环泄漏对照）

roadmap 必会概念"循环引用与 Weak"的验证题：树结构"父持子强引用、子指父弱引用"，实测强/弱计数并验证释放；后半段**故意演示**不用 `Weak` 的循环泄漏：

```rust
// examples/ex06-weak-break-cycle.rs —— Weak 打破循环引用 + 循环泄漏对照；计数与 drop 打印已实测（已验证：rustc 1.92.0）
use std::cell::RefCell;
use std::rc::{Rc, Weak};

#[derive(Debug)]
struct Node {
    name: &'static str,
    value: i32,
    parent: RefCell<Weak<Node>>,      // 弱引用：不增加强引用计数——「子认识父」
    children: RefCell<Vec<Rc<Node>>>, // 强引用：父拥有子
}

impl Node {
    fn new(name: &'static str, value: i32) -> Self {
        Node {
            name,
            value,
            parent: RefCell::new(Weak::new()),
            children: RefCell::new(Vec::new()),
        }
    }
}

impl Drop for Node {
    fn drop(&mut self) {
        println!("drop Node {}", self.name);
    }
}

fn main() {
    // ===== 前半段：Weak 打破循环，释放正常 =====
    let root = Rc::new(Node::new("root", 10));
    let leaf = Rc::new(Node::new("leaf", 3));

    root.children.borrow_mut().push(Rc::clone(&leaf)); // 父持子：强引用
    *leaf.parent.borrow_mut() = Rc::downgrade(&root);  // 子指父：弱引用，不构成环

    println!("root strong = {} weak = {}", Rc::strong_count(&root), Rc::weak_count(&root)); // 1 / 1
    println!("leaf strong = {} weak = {}", Rc::strong_count(&leaf), Rc::weak_count(&leaf)); // 2 / 0

    // 升级弱引用访问父节点：先绑定借用 guard，避免临时借用跨 if-let 存活
    let parent_ref = leaf.parent.borrow();
    if let Some(parent) = parent_ref.upgrade() {
        println!("leaf 的父节点 {} value = {}", parent.name, parent.value); // root 10
    }

    // 先释放 root：root 的 Drop 触发（强计数 1 -> 0），children 里的 leaf 引用随之减少
    drop(root);

    // leaf 还活着，但它对父的弱引用已悬空
    match leaf.parent.borrow().upgrade() {
        Some(_) => println!("父还活着"),
        None => println!("父已释放：upgrade() 返回 None（弱引用不阻止目标释放）"),
    }
    println!("leaf strong = {}", Rc::strong_count(&leaf)); // 1（只剩变量 leaf）
    // main 结束时 leaf 释放，打印 drop Node leaf——两条边都有正确释放，无泄漏

    // ===== 后半段：不用 Weak 的循环引用泄漏（故意演示，进程退出时由 OS 回收） =====
    println!("\n--- 循环引用泄漏演示（故意，进程退出时由 OS 回收） ---");
    let a = Rc::new(Node::new("a", 1));
    let b = Rc::new(Node::new("b", 2));
    println!("成环前: a strong={} b strong={}", Rc::strong_count(&a), Rc::strong_count(&b)); // 1 / 1
    *a.children.borrow_mut() = vec![Rc::clone(&b)]; // a -> b
    *b.children.borrow_mut() = vec![Rc::clone(&a)]; // b -> a，形成环
    println!("成环后: a strong={} b strong={}", Rc::strong_count(&a), Rc::strong_count(&b)); // 2 / 2

    drop(a);
    drop(b);
    // 两个句柄都已 drop，但「drop Node a/b」没有打印：环上的强计数互相支撑、永不归零，
    // 堆数据成为孤儿泄漏——Rust 不报编译错（这是逻辑泄漏，不是 UB），只能靠 Weak 或设计避免。
    println!("两个句柄已 drop，但 Node 的 drop 没有触发 —— 循环引用泄漏（计数停留 1/1）");
}
```

要点与坑：
- **实测输出**：root `strong=1 weak=1`、leaf `strong=2 weak=0`；父先释放后 `upgrade()` 返回 `None`；drop 打印显示所有节点正常释放。
- **循环泄漏是"逻辑泄漏"**：两个 `Rc` 互指时**不报编译错误（没有 E 码）**，句柄 drop 后 `Drop` 不触发、计数停留 1/1——只能靠 `Weak` 打断环或设计上避免，用 `strong_count`/`weak_count` 或 `Drop` 打印验证（示例 6 后半段为故意演示，进程退出时由 OS 回收，无实际危害）。

## 7. 总结

### 关键要点

1. **`Box<T>` 是最基础的智能指针**：堆分配、单指针宽度、`Drop` 自动释放；三大用途是堆上大对象、递归类型（E0072 的解法）、trait 对象 `Box<dyn Trait>`；移动后旧绑定失效（E0382）。
2. **`Deref`/`DerefMut` 决定"像引用一样用"**：`*x` 展开为 `x.deref()`，deref coercion 让 `&Rc<T>`/`&Box<T>` 自动变 `&T`；可变解引用同样可多跳（每层需 `DerefMut`），但不能穿过只实现 `Deref` 的层（如 `Rc`）。
3. **`Drop` 保证"走时必清"**：声明逆序 drop、结构体先 `impl Drop` 体再按字段声明顺序 drop；实现 `Drop` 的类型不能把字段 move 出 `&mut self`（E0507，已实测），也不能解构整个值（E0509，已实测），还不能实现 `Copy`。
4. **`Rc` 是单线程引用计数**：`clone` O(1) 只增计数不拷贝数据，`strong_count` 归零才释放；非原子计数导致非 `Send`，跨线程编译报 E0277（已实测）。
5. **`Arc` 是线程安全引用计数**：原子计数（`fetch_add`/`fetch_sub`）使其 `Send + Sync`；只解决共享，可变要配 `Mutex`/`RwLock`；多线程 drop 顺序不定，只断言确定性结果。
6. **`RefCell` 把借用检查挪到运行时**：`borrow`/`borrow_mut` + 运行时计数，违规 panic——消息已实测为 `RefCell already borrowed`（`borrow_mut` 撞借用）或 `RefCell already mutably borrowed`（`borrow` 撞可变借用）；单线程专用（非 `Sync`，`Arc<RefCell<T>>` 跨线程报 E0277）。
7. **`Weak` 打破循环引用**：不增加强引用计数，`upgrade()` 返回 `Option`；双向引用结构中"从属方向"必须用 `Weak`，否则计数永不归零、内存泄漏——注意这是**运行期逻辑泄漏，没有编译错误码**。
8. **组合模式是生态惯例**：`Rc<RefCell<T>>`（单线程共享可变）、`Arc<Mutex<T>>`（多线程共享可变），结构同构、迁移只需换类型。
9. **裸指针不是本阶段的工具**：`*const T`/`*mut T` 无所有权、无自动释放、需 `unsafe`（ph14，目录待建）；安全场景全部用智能指针表达。

### 跨语言对比：所有权与共享

| 维度 | Rust 智能指针 | C++ 智能指针 | Java 引用 | Go GC | C 手动 |
|------|--------------|--------------|-----------|-------|--------|
| 释放方式 | 编译期 + `Drop`（RAII） | 析构函数（RAII） | GC 不可控 | GC 并发回收 | `free()` 手动 |
| 共享所有权 | `Rc`/`Arc` 引用计数 | `shared_ptr` 引用计数 | 所有引用天然共享 | 所有变量天然共享 | 无（裸指针） |
| 循环引用处理 | `Weak` 显式打破 | `weak_ptr` 显式打破 | GC 自动回收环 | GC 自动回收环 | 无（靠自觉） |
| 线程安全 | 编译期 `Send`/`Sync` 检查 | 无编译期检查 | JMM + 锁 | goroutine 共享 + 锁 | 无 |
| 内部可变性 | `RefCell`/`Mutex` 显式声明 | `mutable` 关键字 | 默认可变 | 默认可变 | 默认可变 |
| 悬垂/野指针 | 编译期禁止 | 裸指针可悬垂 | 不可能 | 不可能 | 常见事故源 |

### 阶段验收清单

- [ ] 能区分 `Box`、`Rc`、`Arc` 的场景：单 owner 堆分配用 `Box`，单线程多 owner 用 `Rc`，多线程共享用 `Arc`（需要可变再叠加 `RefCell`/`Mutex`）。
- [ ] 能说明 `RefCell` 的风险：借用冲突从编译期推迟到运行期，违规时 panic（消息 `RefCell already borrowed`/`already mutably borrowed`）；guard 存活期间持续占用借用是隐蔽的失败模式。
- [ ] 能避免循环引用泄漏：识别双向引用结构，用 `Weak` 打断"从属方向"的强引用边，用 `strong_count`/`weak_count` 或 `Drop` 打印验证（知道循环泄漏没有编译错误码）。
- [ ] 能说出 `Deref`/`Drop` 的作用：deref coercion 让智能指针像引用一样用（零成本），`Drop` 保证资源自动释放（RAII）。
- [ ] 能区分 `Rc` 与 `Arc` 的适用边界，并解释"为什么 `Arc<RefCell<T>>` 编译失败（E0277）、`Arc<Mutex<T>>` 才行"。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看），共 5 题，覆盖本章示例 1~6 的主题：

- 用 Box 构建递归链表（提示：`enum List { Cons(i32, Box<List>), Nil }` 实现 `len`/`sum`，去掉 `Box` 会报 E0072；对照示例 1）
- 用 Rc 共享只读配置（提示：`Rc::new` 一次、`Rc::clone` 多次，函数参数写 `&Config` 靠 deref coercion 收 `&Rc<Config>`；对照示例 3）
- RefCell 内部可变性：惰性缓存 + 借用冲突（提示：`RefCell<Option<i32>>` 缓存 + `catch_unwind` 捕获 BorrowMutError，panic 消息是 `RefCell already borrowed`；对照示例 4）
- 用 `Arc<Mutex<_>>` 做线程间计数（提示：每线程 `Arc::clone` + `move` 闭包，循环内 `lock().unwrap()` 修改，`join` 汇总，期望值动态计算；对照示例 5）
- 构造带 parent 的树并用 `Weak` 消除循环泄漏（提示：父持子强引用、子指父弱引用，`upgrade()` 处理 `None`，guard 用块作用域及时释放；对照示例 6）

完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**规则树执行器**——用 `Box` 表达递归规则（And/Or/Leaf 无限嵌套），用 `Rc` 共享规则元数据，`eval` 在事实集下求值、递归统计节点数与权重、带缩进渲染，含 11 个单元测试（roadmap 推荐项目；零第三方依赖，单文件）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

扩展方向（可选）：给 `RuleNode` 加 `Not` 节点与短路求值；把 `Rc` 换成 `Arc` 配合 `Mutex` 共享求值上下文做并发求值（衔接 [ph12 并发与异步阶段](../ph12-concurrency-async/12-concurrency-async.md)）；`eval` 结果 `Option` 化区分"事实缺失"与"事实为假"（衔接 ph11 错误处理与工程质量阶段）。

### 下一阶段

[错误处理与工程质量阶段](../ph11-error-handling/11-error-handling.md) —— thiserror/anyhow、错误类型设计、panic 策略、测试与 CI。智能指针阶段学会了"数据如何被共享与可变"，错误处理阶段则回答"共享状态下出错怎么办"：`Mutex` 中毒的恢复策略、`Result` 与 `?` 在组合类型上的传播、为库定义精确的错误类型——两个阶段的知识将在真实工程的错误路径上汇合。
