# exercises —— 并发与异步阶段练习

完成顺序建议：按 1~5 顺序完成，对应主文档第 6 章示例 1~5 与第 3 章 3.1~3.6 的主题。参考实现在 `sol-*` 文件中，**先自己做，做完再看**。每题标注难度（★~★★★）。全部为单文件、零第三方依赖（含练习 4 的自写调度器——异步基础不依赖 tokio；tokio 等价写法见 examples/tokio/），统一用 `rustc --edition 2021 -D warnings` 单文件编译。

## 练习 1：用 channel 汇总多个线程结果（★）

- **目标**：掌握 mpsc「多生产者 → 单消费者」模式——线程算结果、通道回传、主线程汇总（对应 roadmap 练习）
- **要求**：
  - 把 `1..=100` 分成 4 段，4 个 worker 线程各算一段部分和，经 `mpsc::channel` 发回主线程
  - 每个 worker `clone` 一个 `Sender`；主线程 `drop` 自己的 `Sender` 后 `rx.iter()` 收齐
  - 汇总打印每段部分和与总和；用 `assert_eq!` 断言总和 `5050`
  - **思考**：通道到达顺序不定——要让输出确定，应该怎么做？（提示：收集后排序）
- **验收**：`rustc --edition 2021 -D warnings sol-01-channel-sum.rs -o /tmp/sol01 && /tmp/sol01` 编译零警告；输出含 `worker 0 部分和 = 325`、`worker 1 部分和 = 950`、`worker 2 部分和 = 1575`、`worker 3 部分和 = 2200`、`总和 = 5050`、`断言通过`

## 练习 2：为共享状态增加锁并评估粒度（★★）

- **目标**：理解锁粒度取舍——临界区大小对性能的真实影响（对应 roadmap 练习）
- **要求**：
  - **场景 A**（纯 CPU 小临界区）：4 线程 × 20 万次自增，分别用「细粒度」（每轮 `lock`/`unlock`）与「粗粒度」（整个循环只 `lock` 一次）实现，打印两种耗时与计数
  - **场景 B**（锁外有真实等待）：4 线程 × 40 轮，每轮锁外 `sleep(2ms)` 模拟 I/O 取数、锁内自增——同样分细/粗粒度实现，打印耗时
  - 两种粒度计数都必须精确（`assert_eq!` 断言）；输出并解释「哪个场景哪种粒度更快、为什么」
  - **思考**：为什么场景 A 粗粒度更快而场景 B 细粒度更快？锁粒度的取舍原则是什么？
- **验收**：`rustc --edition 2021 -D warnings sol-02-arc-mutex-lock-granularity.rs -o /tmp/sol02 && /tmp/sol02` 编译零警告；输出含两个场景的细/粗耗时与计数、`结论：锁粒度取舍 = 临界区工作量 vs 锁外并行机会`（耗时数值随机器而异，量级结论稳定：A 粗快、B 细快）

## 练习 3：RwLock 读多写一缓存（★★）

- **目标**：掌握读写锁的语义——读并发、写独占，模拟「读多写一」的共享缓存
- **要求**：
  - `HashMap<String, u32>` 包在 `RwLock` 里，预置 key `"a"`
  - 4 个读者线程并发读 key `"a"` 各 1000 次，返回命中数；1 个写者线程写 key `"b"` 5 次
  - 断言：每个读者命中数都是 1000（读锁可并发，互不阻塞）；最终 `"b"` 的值是最后一次写入的 `4`（写锁独占）
  - **思考**：什么场景读锁「并发」是免费的？什么场景读锁也会阻塞？（提示：写者等待期间新读者排队，见主文档 3.3）
- **验收**：`rustc --edition 2021 -D warnings sol-03-rwlock-shared-cache.rs -o /tmp/sol03 && /tmp/sol03` 编译零警告；输出含 `读者命中数 = [1000, 1000, 1000, 1000]`、`最终缓存 = {"a": 1, "b": 4}`、`断言通过`

## 练习 4：极简 async 调度器（★★★）

- **目标**：亲手实现「任务调度」的最小形态——轮询多个 Future、谁 Ready 谁完成（对应 roadmap 练习「用 tokio 并发请求多个接口」的纯 std 版；tokio 等价写法 `tokio::spawn` + `JoinHandle.await` 或 `tokio::join!` 见 examples/tokio/ex07，已验证 tokio 1.53.1）
- **要求**：
  - 实现 `block_on_many`：接收 `Vec<F: Future>`，循环轮询全部任务，`Poll::Ready` 即收集输出，本轮无进展则 `thread::park()` 挂起（waker 用 `std::task::Wake` + `unpark` 实现）
  - 实现一个 `Timer` future（到点 `Ready`、未到点 `Pending` 并注册唤醒）；写 `async fn fake_request(name, latency_ms) -> String` 模拟请求
  - 用调度器并发跑 3 个不同延迟的「请求」（如 120/240/360ms），断言总耗时明显小于串行之和
  - **思考**：为什么单线程调度器能「并发」？async 任务与线程的根本区别是什么？（提示：非阻塞等待 vs 阻塞等待，见主文档 3.5/4.3）
- **验收**：`rustc --edition 2021 -D warnings sol-04-async-scheduler.rs -o /tmp/sol04 && /tmp/sol04` 编译零警告；输出含 3 个接口的返回与 `总耗时约 3xxms（串行需 720ms）`、`断言通过`（耗时数值随机器而异）

## 练习 5：Send/Sync 边界判断 + 背压（★★）

- **目标**：把 Send/Sync 的编译期判据用起来；用有界通道实测背压
- **要求**：
  - 用「证据函数」`fn assert_send<T: Send>() {}` / `fn assert_sync<T: Sync>() {}` 验证一组类型的属性：`i32`、`String`、`Vec<String>`、`Arc<Mutex<u32>>`、`Arc<RwLock<u32>>`、`mpsc::Sender<u32>`、`mpsc::Receiver<u32>`、`&'static str`——每个断言旁注释「为什么」
  - 在注释中列出反例（`Rc<u32>`、`Cell<u32>`(Sync)、`RefCell<u32>`(Sync)、`*const u32`）并写出会得到的 E0277 错误文本（对照主文档 3.4 实测文本）
  - 背压：`sync_channel(3)`，生产者发 6 条、消费者晚 100ms 才开始收——用 `Instant` 计时打印生产/消费时间点，验证「缓冲满后 send 阻塞直到消费者取走」
  - **思考**：`Rc` 与 `Arc` 的 Send/Sync 差异从何而来？背压在生产-消费系统中解决了什么问题？
- **验收**：`rustc --edition 2021 -D warnings sol-05-send-sync-boundary.rs -o /tmp/sol05 && /tmp/sol05` 编译零警告；输出含 `1. 全部 Send/Sync 断言编译通过`、`2. 生产 0/1/2 @ 0ms`、`2. 消费 0 @ 1xxms`、`2. 生产 3 @ 1xxms`（第 4 次生产阻塞到消费开始后）、`2. 背压演示完成`

> **提示**：练习 1~5 覆盖主文档第 6 章示例 1~5 的主题（示例是"看"，练习是"做"）。卡壳时先回读主文档 3.x 对应小节（3.1 线程、3.2 通道、3.3 共享状态与锁、3.4 Send/Sync、3.5 async/await、3.6 任务调度），最后再看 `sol-*`。
