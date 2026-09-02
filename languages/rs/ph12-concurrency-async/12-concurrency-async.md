# Rust 并发与异步阶段

> 面向数据基础设施与异步网络服务方向：本阶段建立「并发与异步」两条主线的心智——OS 线程与通道/共享状态解决**多核并行**，async/await 与任务调度解决**单线程内的高并发等待**；Send/Sync 把「数据竞争」从运行时事故变成编译期错误。

## 1. 概述

Rust 并发与异步阶段对应 roadmap 第 12 节，目标是**能编写线程安全和异步 I/O 程序，理解 Send/Sync 边界**。具体定位是：**用 `thread::spawn` 起线程、用 mpsc 通道做消息传递、用 `Arc`/`Mutex`/`RwLock` 做共享可变状态，理解「数据竞争在编译期受限」的机制（Send/Sync）；再进入 async 世界——`async fn`/`.await`、自写极简 executor 看懂任务调度，最后用 tokio 落地任务、定时器、超时与网络 I/O**。本阶段承接 ph10 智能指针阶段（`Arc` 是 `Rc` 的多线程版、`Mutex` 已登场）与 ph11 错误处理阶段（`Mutex` 中毒恢复、错误跨线程传递）；并为 ph13 文件、网络与系统编程阶段（真实 TCP/UDP 程序）与 ph25 数据基础设施阶段（Axum/Tonic 异步服务）铺路。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 线程 | `thread::spawn`/`join`、move 闭包、命名线程、`thread::scope` 简介、输出顺序不定（3.1） |
| 消息传递 | `std::sync::mpsc`：无界/有界通道、多生产者、`drop(tx)` 关闭、背压（3.2） |
| 共享状态 | `Arc`、`Mutex`（中毒恢复承接 ph11）、`RwLock`、锁粒度取舍（3.3） |
| 类型安全 | `Send`/`Sync` marker trait、自动推导、E0277/E0373 实测（3.4） |
| 异步基础 | `async fn`/`.await`、`Future`/`poll`/`waker`、自写极简 executor、任务调度（3.5、3.6） |
| tokio | 任务（`tokio::spawn`）、定时器、超时与取消、异步网络 I/O、异步背压——**已验证 tokio 1.53.1**（3.7） |

这个阶段只涉及 OS 线程并发（`std::thread`）、通道与共享状态的同步并发，以及 async/await 基础与 tokio 的任务/定时器/网络 I/O 演示，**不涉及文件与网络系统编程的系统化（`std::fs` 全套、TCP/UDP 编程与重试策略）、unsafe 与裸指针（`*const T`/`*mut T`、`Pin` 手工管理）、宏与元编程（`macro_rules!`/过程宏）和性能剖析与优化（profiling、criterion 基准、原子操作深入）** — 那些是 ph13 文件、网络与系统编程阶段、[ph14 Unsafe Rust 与安全抽象阶段](../ph14-unsafe-safety-abstraction/14-unsafe-safety-abstraction.md)、[ph15 宏与元编程阶段](../ph15-macros-metaprogramming/15-macros-metaprogramming.md)和 ph22 性能优化与 Profiling 阶段的内容（ph13/ph14/ph15 目录已建；ph22 目录待建）。异步流式处理（`Stream`）与异步 trait（`async fn` in trait）只作提及，深入属后续生态阶段。承接 [ph10 智能指针阶段](../ph10-smart-pointers/10-smart-pointers.md)：`Arc` 的引用计数语义、`Mutex` 的 guard 与中毒机制；也承接 [ph11 错误处理与工程质量阶段](../ph11-error-handling/11-error-handling.md)：`?` 跨 `.await` 传播、`JoinError` 是新的错误来源。

## 2. 来源与演变

Rust 的并发故事从「两条腿走路」开始：**线程管并行，async 管并发**。2014 年（1.0 之前）Rust 曾内置 green threads（`libgreen`，M:N 调度），但设计者发现 M:N 调度与 C 生态互操作、调试体验的代价太高，最终移除，改走 **1:1 OS 线程**——「线程是操作系统的事，语言只负责把错误挡在编译期」。`std::sync::mpsc` 随 1.0 进入标准库，`Send`/`Sync` 两个 marker trait 从诞生起就是「数据竞争编译期受限」的落地手段。2016 年 Carl Lerche 启动 tokio，2018 年 async/await RFC 2394 被接受，2019 年 11 月 Rust 1.39 稳定 async/await——但注意 **async/await 只是语法，运行时（executor）由生态提供**，这与 Go（goroutine 内建）是根本区别。2020 年底 tokio 1.0 发布，从此「Rust 异步 = tokio」成为事实标准；标准库也不断补位：`thread::scope`（1.63）、`OnceLock`（1.70）、`LazyLock`（1.80）让「不引第三方也能写并发」的范围逐步扩大。

| 时间 | 里程碑 | 影响 |
|------|--------|------|
| 2014 | 移除 green threads（`libgreen`），确定 1:1 OS 线程 | 「线程是 OS 的事」；`Send`/`Sync` 成为跨线程安全的编译期判据 |
| 2015 | Rust 1.0：`std::thread`、`std::sync::mpsc` 进标准库 | 线程 + 通道成为 std 自带的两件套 |
| 2016 | tokio 项目启动（Carl Lerche） | 事件驱动异步运行时雏形（futures 0.1 同期出现） |
| 2018 | async/await RFC 2394 被接受 | 语言层语法定案：`async fn` 编译成状态机 |
| 2019 | Rust 1.39 稳定 async/await（2019-11-07） | 语法可用；executor 仍由生态提供（tokio/async-std） |
| 2020 | tokio 1.0 发布（2020-12-23） | 「Rust 异步 = tokio」成为事实标准，语义稳定承诺（1.x 不破坏兼容） |
| 2022 | `std::thread::scope` 稳定（Rust 1.63） | 借用非 `'static` 数据的线程诞生：scoped 线程 |
| 2023-2024 | `OnceLock`（1.70）、`LazyLock`（1.80）稳定 | 无第三方依赖的惰性单例/全局状态 |
| 2025 | 本环境工具链：rustc 1.92.0 + tokio 1.53.1 | 本文全部 std 示例与 tokio 示例均在此环境实测 |

本文示例以 **Rust 2021 edition（rustc 1.92.0）** 为基线（与 ph10/ph11 一致：全仓库代码层统一 `rustc --edition 2021` 单文件编译；并发与异步的核心 API——`thread`/`mpsc`/`Arc`/`Mutex`/`RwLock`/`Send`/`Sync`/`async`/`await`/`Future`——自 1.0~1.39 全部稳定，是本阶段语法中最稳定的部分）。**依赖策略**：std 部分（示例 1~6、练习、项目）只用标准库，`rustc` 单文件编译、零依赖、不依赖 cargo 联网；**tokio 部分（示例 7~10）为第三方 crate，本环境已通过 rsproxy 国内镜像成功拉取并完整编译运行——tokio 1.53.1，全部标注「已验证（tokio 1.53.1）」**（拉取失败环境则按「未在本环境验证」处理，见 examples/README）。编译错误码（E0277/E0373）与运行输出全部在本环境实测后写入；多线程输出顺序不定的部分已如实标注。

## 3. 语法与参数

### 3.1 线程：thread::spawn 与 join

`thread::spawn` 把闭包放到新线程执行，返回 `JoinHandle`；`handle.join()` 阻塞等待线程结束并取回返回值。闭包需要 `move` 把用到的数据移进线程（不 `move` 则借用检查器拒绝——借用可能比线程活得短，实测报 **E0373**）。**多线程输出顺序不定**：`spawn` 后主线程立即继续执行，「主线程/子线程」哪行先打印每次运行可能不同——这是并发的本质，不是 bug。

```rust
// examples/ex01-thread-spawn-join.rs —— 线程创建、等待与返回值（thread::spawn + join）
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex01-thread-spawn-join.rs -o /tmp/ex01
// 运行：/tmp/ex01
use std::thread;
use std::time::Duration;

fn main() {
    // ===== 1. 最简 spawn + join =====
    let handle = thread::spawn(|| {
        println!("子线程: 正在工作...");
        thread::sleep(Duration::from_millis(50));
        println!("子线程: 完成");
    });
    // 主线程不等 spawn 返回，立即继续执行——上面两行与下面这行的先后不定
    println!("主线程: 已 spawn，继续做自己的事");
    handle.join().expect("子线程 panic"); // 阻塞直到子线程结束

    // ===== 2. spawn 的返回值：闭包返回任意 Send 值，join 取回 =====
    let handle2 = thread::spawn(|| 40 + 2);
    let answer = handle2.join().expect("线程 panic");
    println!("子线程返回值: {answer}");
}
```

**三个线程入口的对比**

| 入口 | 返回 | 数据约束 | 用途 |
|------|------|---------|------|
| `thread::spawn(closure)` | `JoinHandle<T>` | 闭包捕获必须 `Send + 'static` | 通用：启动独立线程 |
| `thread::Builder::new().name(...).stack_size(...)` | `io::Result<JoinHandle<T>>` | 同上 | 需要线程名/自定义栈大小的场景 |
| `thread::scope(|s| ...)`（Rust 1.63+） | `Scope<'env>` | 可借用非 `'static` 数据 | 线程组 + 自动 join，安全借用局部变量 |

**坑（E0373 实测，rustc 1.92.0）**：`spawn` 闭包借用局部变量而不 `move`：

```text
error[E0373]: closure may outlive the current function, but it borrows `s`, which is owned by the current function
help: to force the closure to take ownership of `s` (and any other referenced variables), use the `move` keyword
    |  std::thread::spawn(move || { println!("{s}"); });
```

**坑（顺序不定）**：ex01 实测中 4 个 `spawn` 线程的打印顺序每次运行都可能不同——不要依赖线程输出顺序；需要确定性时排序或聚合（见练习 1 的思路）。

### 3.2 通道：mpsc 多生产者 → 单消费者

`std::sync::mpsc`（Multi-Producer Single-Consumer）：`Sender<T>` 可 `clone`（多生产者），`Receiver<T>` 只有一个（单消费者）；`tx.send(v)` 把值交给通道，`rx.recv()` 阻塞接收，`rx.try_recv()` 不阻塞，`rx.recv_timeout(d)` 限时接收，`rx.iter()` 迭代到通道关闭。**通道关闭 = 所有 `Sender` 被 drop**：之后 `recv` 返回 `Err(Disconnected)`、`iter` 结束——这是「多生产者收齐」的标准信号（练习 1 正是靠它汇总）。

```rust
// examples/ex02-mpsc-channel.rs —— 通道：多生产者 → 单消费者（std::sync::mpsc）
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex02-mpsc-channel.rs -o /tmp/ex02
// 运行：/tmp/ex02
use std::sync::mpsc;
use std::thread;
use std::time::{Duration, Instant};

fn main() {
    // ===== B. 多生产者：clone Sender，每个线程一个 =====
    let (tx, rx) = mpsc::channel();
    let mut handles = Vec::new();
    for id in 0..3 {
        let tx = tx.clone(); // Sender<T> 是 Clone + Send，可移入线程
        handles.push(thread::spawn(move || {
            for j in 0..2 {
                tx.send((id, j)).unwrap();
            }
        }));
    }
    drop(tx); // 主线程手里的原始 tx 也要 drop，否则通道永不关闭
}
```

**有界通道与背压**：`mpsc::sync_channel(n)` 容量为 n，**缓冲满时 `send` 阻塞**直到消费者取走——这就是背压（backpressure）：快生产者被慢消费者拖住，而不是无限堆积。ex02 场景 C 实测（缓冲 2、消费者晚 100ms 开工）：

```text
C. 生产 0 完成 @    0ms
C. 生产 1 完成 @    0ms
C. 消费 0 @  105ms
C. 消费 1 @  105ms
C. 消费 2 @  105ms
C. 生产 2 完成 @  105ms     ← 第 3 次 send 被阻塞，直到消费者取走一条
C. 生产 3 完成 @  105ms
C. 消费 3 @  105ms
```

要点与坑：

- **`Sender` 是 `Clone + Send`，`Receiver` 是 `Send` 但不是 `Sync`**：单消费者语义是编译期保证的——想「多消费者」必须自己包一层（如 `Arc<Mutex<Receiver<T>>>`，见 5 使用场景）。
- **通道 vs 共享状态**：通道传「值」、锁共享「内存」。「share memory by communicating」是 Go 的口号，Rust 两者都支持且类型安全。
- **无界通道没有背压**：生产远快于消费时消息无限堆积、内存膨胀——工程上优先有界通道或明确丢弃策略（见 4.4）。

> 本阶段只用同步通道（`std::sync::mpsc`）与 tokio 有界异步通道（`tokio::sync::mpsc`，示例 10）。**跨 `.await` 的异步通道深入（`tokio::sync::mpsc` 背压、`watch`/`broadcast`、`oneshot` 与取消传播）是 ph12 之后的生态内容**，这里只需理解「有界 = 背压，无界 = 堆积」这一条。

### 3.3 共享可变状态：Arc / Mutex / RwLock

**`Arc<T>`（原子引用计数）** 是 `Rc<T>` 的多线程版（ph10 讲过 `Rc`）：`Arc::clone` 计数 +1，最后一个克隆 drop 时释放内存——代价是计数的原子操作。`Arc` 只解决「共享所有权」，**不解决「可变」**：多线程写同一份数据必须过 `Mutex`/`RwLock`。

**`Mutex<T>`（互斥锁）**：`lock()` 返回 `LockResult<MutexGuard<T>>`——同一时刻只有一个线程能拿到 guard；guard 持有时独占可变访问，**guard drop 即解锁**（RAII，unwind 也保证解锁）。持锁线程 panic 会使锁**中毒（poisoned）**，后续 `lock()` 返回 `Err`——恢复手段（`PoisonError::into_inner`）承接 ph11。ex03 实测：8 线程 × 10 万次自增，`Arc<Mutex<u32>>` 计数精确等于 800000——**数据竞争被编译器挡在门外**（裸 `&mut` 无法跨线程，必须经 `Mutex`）。

**`RwLock<T>`（读写锁）**：`read()` 可多个读者同时持有（并发读），`write()` 独占；std 实现**写优先**——有写者在等时新读者排队，避免写者饿死。ex04 实测：4 个读者各持读锁 120ms，总耗时约 125ms（读并发，非 480ms）；写者持锁 100ms 期间新读者被阻塞约 104ms。

**锁粒度取舍（练习 2 实测结论）**：锁粒度不是越小越好——

- 纯 CPU 小临界区：细粒度每轮抢锁的锁开销占主导，**粗粒度更快**（本机实测：细 55ms vs 粗 2ms）；
- 临界区外有真实等待（模拟 I/O）：细粒度让等待并行、粗粒度把等待串行化，**细粒度更快**（本机实测：细 99ms vs 粗 400ms）。

统一原则：**临界区只放必要的共享变更**——放多了阻塞别人，放少了多付锁开销。

> **注意**（锁与异步的坑）：`std::sync::MutexGuard` 不能安全地跨 `.await` 保持（编译器会因 `Send` 要求报错——持有 guard 的任务可能在线程间迁移，而 guard 不是 `Send`）；异步任务内长时间持锁或用阻塞锁会卡死整个运行时线程。**tokio 场景用 `tokio::sync::Mutex`（`.lock().await`，锁不绑线程）**——区别属于 ph12 之后的生态内容，这里先记住「异步里别用阻塞锁、别让 guard 跨 `.await`」。

### 3.4 Send 与 Sync：数据竞争编译期受限

`Send` 与 `Sync` 是**自动推导的 marker trait**（无方法）：

- **`Send`**：类型可以把所有权**跨线程转移**（移进线程、经通道发送、作为 `spawn` 闭包捕获……）
- **`Sync`**：类型可以被多个线程**同时共享引用**（`&T` 安全地跨线程）

**判据速记**：`&T` 是 `Send` 当且仅当 `T: Sync`；组合类型由字段递归推导；`Mutex<T>` 是 `Sync` 当且仅当 `T: Send`（内部保证同一时刻只有一个可变访问）。判断思路写在练习 5；下面是一组实测断言（ex05，编译通过 = 满足约束）：

```rust
// examples/ex05-send-sync-bounds.rs —— Send / Sync 边界的编译期验证
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex05-send-sync-bounds.rs -o /tmp/ex05
// 运行：/tmp/ex05
use std::sync::{mpsc, Arc, Mutex, RwLock};

// 编译期"证据函数"：T: Send / T: Sync 才能实例化
fn assert_send<T: Send>() {}
fn assert_sync<T: Sync>() {}

fn main() {
    // ===== 1. 基础类型：Send + Sync =====
    assert_send::<i32>();
    assert_sync::<i32>();
    assert_send::<String>();
    assert_sync::<String>();
    assert_send::<Vec<u8>>();
    assert_sync::<Vec<u8>>();

    // ===== 2. 组合类型：Send/Sync 由字段递归推导 =====
    // Arc<Mutex<T>>（T: Send）既 Send 又 Sync：可跨线程共享且可变
    assert_send::<Arc<Mutex<u32>>>();
    assert_sync::<Arc<Mutex<u32>>>();
    assert_send::<Arc<RwLock<u32>>>();
    assert_sync::<Arc<RwLock<u32>>>();
    // 通道两端都 Send（可移入线程）；Receiver 不是 Sync（单消费者）
    assert_send::<mpsc::Sender<u32>>();
    assert_send::<mpsc::Receiver<u32>>();
    // 引用：&T 是 Send 当且仅当 T: Sync（只读共享靠 Sync 保证）
    assert_send::<&'static str>();
    assert_sync::<&'static str>();
}
```

**反例（编译失败，E0277 全部 rustc 1.92.0 实测）**：

| 代码 | 报错文本（E0277） |
|------|-------------------|
| `spawn(move \|\| ...Rc... )` | `` `Rc<i32>` cannot be sent between threads safely ``，help：`` within `{closure@...}`, the trait `Send` is not implemented for `Rc<i32>` `` |
| `assert_sync::<Rc<u32>>()` | `` `Rc<u32>` cannot be shared between threads safely `` |
| `assert_sync::<Cell<u32>>()` | `` `Cell<u32>` cannot be shared between threads safely ``，note 给出解药：`` use `std::sync::RwLock` or `std::sync::atomic::AtomicU32` instead `` |
| `assert_sync::<RefCell<u32>>()` | `` `RefCell<u32>` cannot be shared between threads safely ``，note：`` use `std::sync::RwLock` instead `` |
| `assert_sync::<mpsc::Receiver<u32>>()` | `` `std::sync::mpsc::Receiver<u32>` cannot be shared between threads safely `` |
| `assert_send::<*const u32>()` | `` `*const u32` cannot be sent between threads safely `` |

要点与坑：

- **`Cell`/`RefCell` 是 `Send` 但不是 `Sync`**：能跨线程移动，但不能跨线程共享——「共享 + 可变」必须换 `Mutex`/`RwLock`/原子类型（编译器 note 直接给出建议）。
- **`thread::spawn` 的约束是 `Send + 'static`**：`'static` 意味着闭包不能借用局部数据（借用就得 `thread::scope`，见 3.1）；`Send` 意味着捕获的数据能安全搬家。
- **`unsafe impl Send/Sync` 是唯一的逃逸口**：它把「我保证这个类型跨线程安全」的证明责任转给开发者——属于 [ph14 Unsafe Rust 与安全抽象阶段](../ph14-unsafe-safety-abstraction/14-unsafe-safety-abstraction.md)的内容，本阶段绝不使用。
- **这就是「数据竞争在编译期受限」的完整机制**：共享可变状态必须包在同步原语（`Mutex`/`RwLock`/原子）里，否则编译器拒绝编译——详见 4.1。

### 3.5 async/await 与 Future：语法与非阻塞

`async fn` 不立即执行：它返回一个 **`Future`**（惰性）；`.await` 等待一个 Future 完成并解出结果。`Future` 的接口只有 `poll`：executor 反复调用 `poll`，返回 `Poll::Ready(v)` 表示完成、`Poll::Pending` 表示「还没好，先挂起」——**挂起期间线程是空闲的**（这就是非阻塞：等待不占线程）。谁在「合适的时候」再调一次 `poll`？**waker**：Future 通过 `cx.waker()` 注册唤醒令牌，条件满足时 `waker.wake()` 通知 executor。

```rust
// examples/ex06-async-std-executor.rs —— 纯 std 的 async/await：自写极简 executor
// 说明：不用任何第三方 crate，用 std 亲手实现「async fn → Future → 轮询 → 唤醒」链路：
//       1) async fn 被编译成状态机 Future；2) executor 反复 poll，Pending 就挂起；
//       3) waker 在"可以继续了"时唤醒 executor 再 poll。这就是任务调度的最小形态。
// ===== 3. block_on：轮询单个 Future 直到 Ready =====
fn block_on<F: Future>(fut: F) -> F::Output {
    let mut fut = Box::pin(fut); // 固定到堆上（Pin 的堆版本，避免 unsafe）
    let waker = Waker::from(Arc::new(SpinWaker(thread::current())));
    let mut cx = Context::from_waker(&waker);
    loop {
        match fut.as_mut().poll(&mut cx) {
            Poll::Ready(v) => return v,
            Poll::Pending => thread::park(), // 挂起当前线程，等 waker 唤醒
        }
    }
}
// ===== 5. async fn：.await 挂起/恢复，编译成状态机 =====
async fn countdown(label: &str, steps: u32) -> u32 {
    let mut total = 0u32;
    for i in 0..steps {
        Timer::new(80).await; // 等待 80ms：挂起并让出调度（非阻塞等待）
        total += 1;
        println!("{label}: tick {i}（累计 {total}）");
    }
    total
}
```

**阻塞 vs 非阻塞**（必会概念）：

| | 阻塞（线程） | 非阻塞（async 任务） |
|---|---|---|
| 等待时占资源 | 占着整个线程（OS 线程栈 + 调度） | 只占一个状态机结构，几乎为零 |
| 换出成本 | OS 上下文切换（微秒级） | 函数调用级（纳秒级） |
| 并发规模 | 线程数受 OS 限制（万级封顶） | 任务数只受内存限制（十万/百万级） |
| 适用 | 纯 CPU 并行、阻塞型代码 | I/O 密集、高连接数服务 |

> 本阶段用自写极简 executor 讲透 `Future`/`poll`/`waker` 机制；**生产级 executor（多线程、任务窃取、I/O 事件循环）是 tokio 的内容（3.7）**，这里只需理解「async 是协作式调度：任务自己让出（`.await`），不是被抢占」。

### 3.6 任务调度：谁 Ready 谁完成

「并发」在单线程上也能发生：executor 轮询多个任务，每个任务 `Pending` 就让出，其他任务继续推进——**谁先 Ready 谁先完成**。ex06 的 `block_on_many` 用 3 个不同步数的 countdown 实测（单线程调度器，输出确定）：

```text
B-task-1: tick 0（累计 1）   ← 同一轮次：三个任务都推进到第一个 tick
B-task-2: tick 0（累计 1）
B-task-3: tick 0（累计 1）
B-task-1: tick 1（累计 2）   ← 160ms：task-1 先完成
B-task-2: tick 1（累计 2）
B-task-3: tick 1（累计 2）
B-task-2: tick 2（累计 3）   ← 240ms：task-2 完成
B-task-3: tick 2（累计 3）
B-task-3: tick 3（累计 4）   ← 320ms：task-3 完成
B. 总耗时约 331ms，输出 = [2, 3, 4]
```

**任务调度**（必会概念）就是 executor 的这份轮询职责：什么时候 poll 谁、Pending 了挂到哪、waker 来了唤醒谁。三种调度模型对照：

| 模型 | 代表 | 调度单位 | 抢占？ |
|------|------|---------|--------|
| 1:1 OS 线程 | `std::thread` | 线程 | 抢占式（OS 决定） |
| M:N 协程/任务 | tokio 任务、Go goroutine | 任务（栈式/状态机） | 协作式（`.await` 让出）/ 混合 |
| 状态机任务 | 纯 std `Future` | Future 状态机 | 协作式 |

练习 4 要求亲手实现一个最小调度器（`block_on_many` + waker）——做完就对「tokio 的 `spawn` 在干什么」有了实感。

### 3.7 Tokio：任务、定时器、超时与网络 I/O（已验证 tokio 1.53.1）

tokio 是 Rust 异步的事实标准运行时：多线程 executor + I/O 事件循环（epoll/kqueue）。三个核心用法对应 roadmap 学习内容「Tokio 任务、定时器、网络 I/O」，全部实测（**已验证：tokio 1.53.1，经 rsproxy 镜像拉取**，示例与命令见 `examples/tokio/`）。

**任务 + 定时器**（ex07，`#[tokio::main]` 宏把 `main` 变成 async 并由运行时驱动；`tokio::spawn` 把任务交给线程池；`tokio::time::sleep` 是非阻塞定时器）：

```rust
// examples/tokio/src/bin/ex07-tokio-tasks.rs —— tokio 任务与定时器
// 验证环境：rustc 1.92.0 + tokio 1.53.1（macOS arm64），已通过 rsproxy 镜像拉取
// 编译：cargo build --release（见 examples/tokio/Cargo.toml 头注释）
// 运行：cargo run --release --bin ex07-tokio-tasks
#[tokio::main] // 宏：把 main 变成 async fn，并自动创建并驱动 tokio 运行时
async fn main() {
    let start = std::time::Instant::now();

    // tokio::spawn：返回 JoinHandle<T>（T 是任务返回值）
    let handles: Vec<_> = (0..3u64)
        .map(|i| {
            tokio::spawn(async move {
                sleep(Duration::from_millis(100 * i + 50)).await; // 非阻塞等待
                println!("任务 {i} 完成 @ {}ms", start.elapsed().as_millis());
                i * 10
            })
        })
        .collect();

    // JoinHandle 本身是 Future：.await 等待任务结束并取回返回值
    let mut sum = 0u64;
    for h in handles {
        sum += h.await.expect("任务 panic"); // 任务 panic 时返回 Err(JoinError)
    }
    println!("全部任务完成 @ {}ms，返回值之和 = {sum}", start.elapsed().as_millis());
}
```

实测输出：`任务 0/1/2 完成 @ 52/152/252ms`，`全部任务完成 @ 252ms，返回值之和 = 30`（完成顺序确定）。

**超时与任务失败**（ex08，`tokio::time::timeout(时限, future)` 到点取消 future 并返回 `Err(Elapsed)`——「任务取消」的实现就是 drop 未完成的 future；任务 panic 被 `JoinHandle.await` 收容为 `Err(JoinError)`，`is_panic()` 可判断）：

```text
1) 超时: Err(Elapsed)——任务在 await 点被取消（drop 未完成的 future）   ← 实测
2) 时限内完成: Ok(42)                                                  ← 实测
3) 任务失败: task 15 panicked with message "任务内部出错"（is_panic=true） ← 实测
进程正常结束——任务级失败不会带崩运行时
```

**异步网络 I/O**（ex09，`TcpListener`/`TcpStream` 的异步版——连接、读、写都是 Future，`.await` 挂起而不占线程；单线程可服务成千上万连接）：

```text
服务端: 接受连接 127.0.0.1:54041   ← 实测（端口每次运行不同）
客户端: 收到回显 "hello tokio"
```

**异步背压**（ex10，`tokio::sync::mpsc::channel(2)` 有界通道——缓冲满时 `send().await` **挂起任务而非线程**；实测容量 2 满后生产 3/4 各挂起约 100ms 直到消费者取走，总耗时约 500ms）。

**async 中的红线（必会概念「能避免在 async 中长时间阻塞」）**：**禁止在 async 任务里用 `std::thread::sleep` 或阻塞锁**——它阻塞的是整个 worker 线程（其他任务被拖住）。要用 `tokio::time::sleep(...).await`；锁用 `tokio::sync::Mutex`。这是 async 编程最容易犯的错误，也是「阻塞 vs 非阻塞」的实操落点。

## 4. 底层原理

### 4.1 数据竞争为何编译期受限：Send/Sync + 借用检查

「数据竞争」= 多线程同时访问同一内存且至少一个在写。Rust 的编译期防线有两层：

```text
跨线程访问共享数据的编译期路径（不满足即拒绝编译）：
            ┌──────────────────────────────────────────────┐
 想要：      │  1. 共享所有权（多线程都持有）                  │
 线程 A ──▶  │     Rc<T>  ❌ 非 Send/Sync（计数非原子）        │
 线程 B ──▶  │     Arc<T> ✅ 原子计数                         │
            │  2. 可变访问                                  │
            │     &mut T 跨线程 ❌ 借用检查拒绝（只能有一个可变借用）│
            │     Cell/RefCell ❌ 非 Sync（内部可变性不跨线程）  │
            │     Mutex/RwLock/原子 ✅ 运行时互斥/原子操作       │
            └──────────────────────────────────────────────┘
  结论：共享 + 可变，只有「过同步原语」这一条路——其余全部编译错误
```

`Send` 拦截「值带着共享的 `Rc` 等非线程安全内容搬家」，`Sync` 拦截「`&T` 被多个线程同时共享」；`Mutex<T>: Sync`（`T: Send`）把「共享引用」与「运行时互斥」绑定——**类型系统把正确性变成编译期的选择**。这正是 roadmap 必会概念「数据竞争在编译期受限」的机制：不是靠程序员自觉，而是「非法路径不存在」。

### 4.2 Mutex 与 RwLock 内部：futex、中毒、写优先

- **`Mutex`**：Linux 上基于 **futex**（fast userspace mutex）——无竞争时就是一次原子 compare-and-swap（纳秒级），有竞争才进内核睡眠；guard 的 `Drop` 负责解锁，panic 时由 `Drop` 把锁标记为**中毒**（ph11 已讲恢复），保证「锁不会因 panic 永远锁死」。
- **`RwLock`**：std 实现**写优先**（写者等待队列优先于新读者），防止读者持续涌入饿死写者；代价是读者在写者等待期间也要排队——读多写一但写者稀少频繁的场景收益最大。
- **锁粒度**是「临界区大小」的工程决策（3.3 实测）：本质是**锁的持有时间 × 争用频率**的成本权衡——临界区短则并行度高但锁开销大，临界区长则互斥久。练习 2 的双场景是教科书式的对照实验。

### 4.3 Future 状态机与 executor：每个 await 点一个状态

`async fn` 不是「魔法」，是**编译期状态机**：每个 `.await` 点把函数拆成一个状态，`poll` 从当前状态继续执行：

```text
async fn fetch() {                编译器生成的状态机（示意）：
    let a = req(1).await;   ──▶   enum FetchState {
    let b = req(2).await;             Start,                    // 初始
    a + b                             Await1 { a: i32 },        // 已拿到 a，等 b
                                      Done,                     // 完成
                                  }
                                  每个状态保存「暂停点之前」的局部变量；
                                  poll = 从当前状态继续，到下一个 await 返回 Pending。
```

所以 **Future 不占线程、没有自己的栈**——「暂停」就是把局部变量存进状态机，「恢复」就是接着状态继续跑。executor 的角色（3.6）：持有任务集合，`poll` 推进、`Pending` 挂起、waker 唤醒再 poll；tokio 在此基础上加多线程工作窃取与 epoll/kqueue 事件循环，把「定时器、网络事件」也变成 waker 的来源（对比 ex06 的「每个 Timer 各起一个计时线程」教学简化）。**成本对比**：OS 线程切换走内核（微秒级），`poll` 是纯用户态函数调用（纳秒级）——这是高连接数服务必须 async 的底层原因。

### 4.4 背压：有界队列的流量控制

背压 = **生产者不被无界缓冲纵容，被慢消费者限速**。机制图：

```text
生产者 ──send──▶ [缓冲槽 0|1|2] ──recv──▶ 消费者
                    │
     缓冲满时 send 阻塞（同步）/ 挂起任务（异步）
     —— 快者被慢者拖住，而不是无限堆积内存
```

- 无界通道：生产 100 万条、消费 1 条/秒 → 内存堆积到爆；
- 有界通道：满则阻塞/挂起 → 内存上限 = 容量 × 消息大小，**系统的「速率适配」显式化**。

背压的工程意义：日志采集、消息队列、HTTP 服务限流——「消费者慢时怎么办」的答案从「祈祷」变成「排队（有界）+ 阻塞/丢弃/降级」的显式选择。std 的 `sync_channel`（示例 2 C、练习 5）与 tokio 的 `mpsc::channel`（示例 10）是两个层面的同一机制。

## 5. 使用场景

- **线程 vs async 怎么选**：纯 CPU 并行（计算密集）用线程/`rayon`（每核一个线程最划算）；I/O 密集高并发（数据库驱动、HTTP 服务、消息网关）用 async/tokio（等待不占线程，单机扛万级连接）；两者可混用——tokio 有 `spawn_blocking` 把阻塞工作丢给专用线程池（属后续生态内容，先记住这个名）。
- **channel vs 共享状态（Arc\<Mutex\>）**：消息传递适合「流水线/扇出汇聚」——worker 算完发结果，主线程汇总（练习 1、项目）；共享状态适合「多点读写同一份数据」——计数器、缓存表（练习 2、3）。经验法则：**能用 channel 表达的数据流用 channel**（无锁、语义清晰），共享状态留给「真的共享」；Go 社区推崇「share memory by communicating」，Rust 两条路都类型安全，选型看数据流形态而不是意识形态。
- **Mutex vs RwLock vs 原子类型**：读多写一（配置表、缓存）用 `RwLock`；写多或临界区小用 `Mutex`（锁开销更低）；单计数器/标志位用原子类型（`AtomicU32` 等，无锁无阻塞）——原子操作深入（内存序）属 ph22 性能优化阶段，本阶段只需知道「有更轻的选择」。
- **背压的应用**：慢消费者（日志落盘、外部 API 限速）场景必须有界队列；「丢弃旧事件」「降级」是背压的配套策略（项目 README 扩展方向里有「部分成功/降级」）。
- **多消费者模式**：`Receiver` 非 `Sync`（3.4 实测），想「多线程消费同一通道」用 `Arc<Mutex<Receiver<T>>>` 包一层——锁只保护「取消息」这个动作，消费逻辑仍并行（练习 1 可扩展为 2 个消费者线程）。
- **与同类语言对比**（为 analysis/ 与 Tenet 合成积累素材）：Go 的 goroutine 是运行时内建 M:N 调度（语言级 `go` 关键字 + channel 一等公民）；Java 线程池/虚拟线程（Loom）与 `CompletableFuture`；C++ `std::thread`/`std::async` 无语言级 async/await 的运行时；Rust 的特色是 **Send/Sync 把并发正确性前置到编译期**——别的语言靠 review/测试抓数据竞争，Rust 靠类型系统。

## 6. 代码示例

本节展示完整可运行示例的关键片段，完整文件与运行命令在 [`examples/`](./examples/)（std 六个：`rustc --edition 2021 -D warnings` 单文件；tokio 四个：cargo 工程 `tokio/`，已验证 tokio 1.53.1）。全部片段为 examples 文件逐字摘录（省略处用 `...` 表示）。

### 示例 1：线程创建与等待（ex01-thread-spawn-join.rs）

```rust
// examples/ex01-thread-spawn-join.rs —— 线程创建、等待与返回值（thread::spawn + join）
// 说明：thread::spawn 启动新线程（1:1 映射到 OS 线程），返回 JoinHandle；
//       handle.join() 阻塞等待线程结束并取回返回值。move 闭包把数据移进线程。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex01-thread-spawn-join.rs -o /tmp/ex01
// 运行：/tmp/ex01
let handle = thread::spawn(|| {
    println!("子线程: 正在工作...");
    thread::sleep(Duration::from_millis(50));
    println!("子线程: 完成");
});
// 主线程不等 spawn 返回，立即继续执行——上面两行与下面这行的先后不定
println!("主线程: 已 spawn，继续做自己的事");
handle.join().expect("子线程 panic"); // 阻塞直到子线程结束

let handle2 = thread::spawn(|| 40 + 2);
let answer = handle2.join().expect("线程 panic");
println!("子线程返回值: {answer}");
```

实测要点：`子线程返回值: 42`；「主线程/子线程」打印先后每次运行可能不同（已如实标注）。

### 示例 2：多生产者通道与背压（ex02-mpsc-channel.rs）

```rust
// examples/ex02-mpsc-channel.rs —— 通道：多生产者 → 单消费者（std::sync::mpsc）
// 说明：mpsc = Multi-Producer Single-Consumer。Sender 可 clone（多生产者），
//       Receiver 只能有一个（单消费者）。drop 掉全部 Sender 后通道关闭，
//       rx.iter() / rx.recv() 返回 Err(Disconnected)。有界版 sync_channel 演示背压。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex02-mpsc-channel.rs -o /tmp/ex02
// 运行：/tmp/ex02
// ===== C. 背压：sync_channel(2) 有界通道，缓冲满时 send 阻塞 =====
let (tx, rx) = mpsc::sync_channel(2); // 容量 2 的有界通道
let start = Instant::now();
let producer = thread::spawn(move || {
    for i in 0..4 {
        tx.send(i).unwrap(); // 第 3 个 send（i=2）在缓冲满时阻塞
        println!("C. 生产 {i} 完成 @ {:>4}ms", start.elapsed().as_millis());
    }
});
thread::sleep(Duration::from_millis(100)); // 消费者晚 100ms 才开始收
```

实测输出（节选）：`C. 生产 0/1 完成 @ 0ms` → `C. 消费 0 @ 105ms` → `C. 生产 2 完成 @ 105ms`（第 3 次 send 被阻塞直到消费者取走）。

### 示例 3：Arc\<Mutex\> 计数器（ex03-arc-mutex-counter.rs）

```rust
// examples/ex03-arc-mutex-counter.rs —— 共享可变状态：Arc<Mutex<T>> 计数器
// 说明：Arc = 原子引用计数（多线程共享所有权），Mutex = 互斥锁（同一时刻一个线程
//       能拿到可变访问）。数据竞争在编译期被排除：裸 &mut 无法跨线程，必须经 Mutex。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex03-arc-mutex-counter.rs -o /tmp/ex03
// 运行：/tmp/ex03
let counter = Arc::new(Mutex::new(0u32)); // 共享：Arc 让每个线程持有同一份计数
for _ in 0..THREADS {
    let counter = Arc::clone(&counter); // 引用计数 +1，代价是原子操作
    handles.push(thread::spawn(move || {
        for _ in 0..INCREMENTS {
            let mut guard = counter.lock().expect("锁中毒"); // 抢锁，拿 MutexGuard
            *guard += 1;
            // guard 在本行结束处 drop：立即解锁，下一轮再抢（细粒度临界区）
        }
    }));
}
```

实测输出：`最终计数 = 800000（期望 800000 = 8 × 100000）`、`断言通过：无数据竞争，计数精确`。

### 示例 4：RwLock 读并发写独占（ex04-rwlock-cache.rs）

实测输出（本机）：`4 个读者总耗时约 125ms（≈120ms 说明读真的并发；串行会要 480ms）`；`读者在写者持锁期间被阻塞，105ms 后才读到 101`——读并发与写独占均为实测。

### 示例 5：Send/Sync 编译期断言（ex05-send-sync-bounds.rs）

```rust
// examples/ex05-send-sync-bounds.rs —— Send / Sync 边界的编译期验证
// 说明：Send = 可以把所有权跨线程转移；Sync = 可以被多个线程同时共享引用。
//       二者都是 marker trait（自动推导，无方法）。下方 assert_* 是"证据函数"：
//       编译通过即证明该类型满足约束；编译失败报 E0277。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex05-send-sync-bounds.rs -o /tmp/ex05
// 运行：/tmp/ex05
// ===== 2. 组合类型：Send/Sync 由字段递归推导 =====
// Arc<Mutex<T>>（T: Send）既 Send 又 Sync：可跨线程共享且可变
assert_send::<Arc<Mutex<u32>>>();
assert_sync::<Arc<Mutex<u32>>>();
assert_send::<Arc<RwLock<u32>>>();
assert_sync::<Arc<RwLock<u32>>>();
// 通道两端都 Send（可移入线程）；Receiver 不是 Sync（单消费者）
assert_send::<mpsc::Sender<u32>>();
assert_send::<mpsc::Receiver<u32>>();
```

反例的完整 E0277 错误文本见 3.4 表格（rustc 1.92.0 实测）；文件内注释保留可复现的反例代码。

### 示例 6：纯 std 的 async/await 与极简 executor（ex06-async-std-executor.rs）

```rust
// examples/ex06-async-std-executor.rs —— 纯 std 的 async/await：自写极简 executor
// 说明：不用任何第三方 crate，用 std 亲手实现「async fn → Future → 轮询 → 唤醒」链路：
//       1) async fn 被编译成状态机 Future；2) executor 反复 poll，Pending 就挂起；
//       3) waker 在"可以继续了"时唤醒 executor 再 poll。这就是任务调度的最小形态。
// ===== 4. block_on_many：极简多任务调度器（轮询全部任务，谁 Ready 谁完成）=====
fn block_on_many<F: Future>(tasks: Vec<F>) -> Vec<F::Output> {
    let mut tasks: Vec<Pin<Box<F>>> = tasks.into_iter().map(Box::pin).collect();
    let mut done = vec![false; tasks.len()];
    let mut outputs = Vec::new();
    let waker = Waker::from(Arc::new(SpinWaker(thread::current())));
    let mut cx = Context::from_waker(&waker);

    while outputs.len() < tasks.len() {
        let mut progressed = false;
        for (i, task) in tasks.iter_mut().enumerate() {
            if done[i] {
                continue; // 已完成的任务不再 poll
            }
            if let Poll::Ready(v) = task.as_mut().poll(&mut cx) {
                done[i] = true;
                outputs.push(v);
                progressed = true;
            }
        }
        if !progressed {
            thread::park(); // 本轮没有一个任务完成：挂起，等任一 Timer 唤醒
        }
    }
    outputs
}
```

实测输出（节选）：3 个 countdown 任务并发推进，总耗时约 331ms，输出 `[2, 3, 4]`（单线程调度器，顺序确定）。

### 示例 7~10：tokio（已验证 tokio 1.53.1）

| 示例 | 文件 | 一句话 | 实测输出要点 |
|------|------|--------|-------------|
| 7 任务/定时器 | `tokio/src/bin/ex07-tokio-tasks.rs` | `tokio::spawn` + `tokio::time::sleep` | `任务 0/1/2 完成 @ 52/152/252ms`，返回值之和 `30` |
| 8 超时/失败 | `tokio/src/bin/ex08-tokio-timeout.rs` | `timeout` 取消 + `JoinError` 收容 panic | `1) 超时: Err(Elapsed)`；`3) 任务失败: task 15 panicked with message "任务内部出错"（is_panic=true）` |
| 9 网络 I/O | `tokio/src/bin/ex09-tokio-tcp-echo.rs` | `TcpListener`/`TcpStream` 异步回环 echo | `客户端: 收到回显 "hello tokio"` |
| 10 异步背压 | `tokio/src/bin/ex10-tokio-mpsc-backpressure.rs` | `tokio::sync::mpsc` 有界通道，`send().await` 挂起任务 | 容量 2 满后生产 3/4 各挂起约 100ms，总耗时约 500ms |

> 运行 tokio 示例需要拉取 tokio（国内环境用 rsproxy 镜像，配置方法见 [`examples/README.md`](./examples/README.md)）。本环境已验证（tokio 1.53.1）；拉取失败的环境请按「未在本环境验证」如实标注，不虚构结果。

## 7. 总结

### 关键要点

1. **并发的两条主线**：线程（`std::thread`）管多核并行，async（`Future`/executor/tokio）管单线程内的高并发等待；「线程 = 抢占式、占 OS 资源」「任务 = 协作式、占内存」。
2. **共享 + 可变只有一条编译期合法的路**：`Arc<T>`（共享所有权）＋ `Mutex`/`RwLock`（运行时互斥）——`Send`/`Sync` 自动推导，不满足的路径（`Rc`/`Cell`/`RefCell`/裸指针）直接 E0277 拒绝编译，**数据竞争在编译期受限**（机制见 4.1）。
3. **通道是消息传递的骨架**：`Sender` clone = 多生产者，全部 `Sender` drop = 通道关闭（`recv`/`iter` 结束的信号）；有界通道 = 背压（满则阻塞/挂起），无界通道 = 堆积风险。
4. **锁粒度不是越小越好**（练习 2 实测）：纯 CPU 小临界区粗粒度更快（锁开销主导），锁外有等待时细粒度更快（并行机会）——临界区只放必要的共享变更。
5. **async 的本质是状态机**：`async fn` 编译成每个 `.await` 一个状态的 Future；`poll` 推进、`Pending` 挂起、waker 唤醒——不占线程、无栈、纳秒级切换。阻塞等待（`sleep`）与挂起等待（`.await`）的区别就是「占不占线程」。
6. **任务调度** = executor 的轮询职责（谁 Ready 谁完成）；tokio 在其上加多线程工作窃取与 I/O 事件循环。
7. **tokio 三件套**（已验证 1.53.1）：`tokio::spawn`（任务）、`tokio::time::sleep`/`timeout`（定时器与超时取消）、异步 `TcpListener`/`TcpStream`（网络 I/O）；**async 里禁止阻塞**（`std::thread::sleep` 会卡死 worker 线程，用 `tokio::time::sleep`；锁用 `tokio::sync::Mutex`）。
8. **背压** = 有界缓冲 + 快者被慢者限速，是生产-消费系统内存安全的工程红线。

### 阶段验收清单

- [ ] 能解释线程与 async task 的区别（抢占 vs 协作、占线程 vs 占内存、万级 vs 百万级），并说出各自适用场景
- [ ] 能写出 `thread::spawn` + `join` + 通道汇总多线程结果的程序，并解释「全部 Sender drop 通道才关闭」
- [ ] 能说清 `Send`/`Sync` 的定义与推导规则，能预测 `Rc`/`Arc`/`Cell`/`Mutex`/`Receiver` 的属性，能读懂 E0277/E0373 并修复
- [ ] 能用 `Arc<Mutex<T>>`/`RwLock<T>` 实现共享计数器/缓存并评估锁粒度（能解释练习 2 双场景的耗时差异）
- [ ] 能解释「数据竞争在编译期受限」的机制（Send/Sync + 借用检查 + 同步原语）
- [ ] 能讲清 `Future` 的 `poll`/`Pending`/`Ready`/waker 机制，能自写极简 `block_on`/调度器
- [ ] 能避免在 async 中长时间阻塞（不用 `std::thread::sleep`/阻塞锁），能处理任务取消与超时（tokio `timeout`、`JoinError`）
- [ ] 能解释背压并演示有界通道的限速效果（std `sync_channel` / tokio `mpsc`）
- [ ] 能跑通 examples/tokio 四个示例并说明各自演示了什么（已验证 tokio 1.53.1）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看），共 5 题，覆盖本章 3.1~3.6 的主题：

- 练习 1（★）：用 channel 汇总多个线程结果（roadmap 练习，对照示例 2）
- 练习 2（★★）：为共享状态增加锁并评估粒度（roadmap 练习，对照示例 3）
- 练习 3（★★）：RwLock 读多写一缓存（对照示例 4）
- 练习 4（★★★）：极简 async 调度器——自写 `block_on_many` 并发跑多个「请求」（roadmap 练习「用 tokio 并发请求多个接口」的纯 std 版，对照示例 6）
- 练习 5（★★）：Send/Sync 边界判断 + 有界通道背压演示（对照示例 5、示例 2 C）

完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**异步采集器（std 版）**——并发采集 5 个模拟数据源的「状态」，每源最多重试 3 次，主线程按全局超时 380ms 收集并汇总为 成功 / 重试耗尽失败 / 超时未返回（roadmap 推荐项目；纯 std 单文件，含 6 个单元测试；真实网络版属 ph13，tokio 异步网络见 examples/tokio/ex09，已验证）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（编译零警告、6 个测试通过、成功 3 + 超时 2 的运行输出实测）

### 下一阶段

[文件、网络与系统编程阶段](../ph13-file-network-sys/13-file-network-sys.md) — 本阶段打下的并发与异步地基将延伸到真实系统编程：`std::fs`/`std::io` 的缓冲 I/O、`Path`/`PathBuf` 跨平台路径、TCP/UDP 连接管理与断连重试（示例 9 的异步 TCP 只是序幕，真实的连接管理、断连重试、超时策略落在 ph13）、serde 序列化与 clap 命令行；ph12 的「背压 + 超时 + 重试」骨架会原样搬到 ph13 的网络程序与 ph25 的 Axum/Tonic 数据服务里。在此之前可先按推荐学习顺序巩固 ph10~ph12 的练习与项目。
