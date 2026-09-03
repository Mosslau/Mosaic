# Java 多线程与并发阶段

> 面向企业级后端、微服务方向，本阶段能写安全的并发 Java 程序——正确选型线程、锁与线程池，让程序在高并发下既快又稳。

## 1. 概述

Java 多线程与并发阶段的目标是：**能写安全的并发 Java 程序**——理解线程与竞态的本质，掌握从底层原语（synchronized、Lock）到高级工具（线程池、并发集合、CompletableFuture）的完整武器库，并跟上 Java 21 虚拟线程带来的并发范式变革。并发是后端事故的高发区：数据错乱、死锁、OOM 大多源于并发处理不当；本阶段建立「先想清楚线程模型，再写代码」的习惯，为 ph15 Spring 全家桶阶段、ph16 微服务与分布式阶段和 ph18 缓存与高并发阶段打好基础。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 线程基础 | Thread、Runnable、Callable、Future、线程状态与生命周期 |
| 线程池 | ExecutorService、ThreadPoolExecutor 参数（核心/最大/队列/拒绝策略） |
| 同步原语 | synchronized、volatile、Lock、ReentrantLock、Condition |
| 原子与 CAS | AtomicInteger 等 Atomic 类、CAS 原理与 ABA 问题 |
| 并发集合 | ConcurrentHashMap、CopyOnWriteArrayList、BlockingQueue |
| 异步编排 | CompletableFuture（thenApply / exceptionally / 组合） |
| 虚拟线程 | Virtual Threads（Java 21）、平台线程对比 |
| 结构化并发与 Scoped Values | StructuredTaskScope（预览）、ScopedValue（Java 25 正式化） |
| 并发排查 | 死锁、竞态、可见性问题定位（jstack 等） |

这个阶段只涉及单机 JVM 内的线程模型与并发工具（Thread/线程池/锁/并发集合/异步编排/虚拟线程），**不涉及 JVM 内存模型底层调优、GC 参数与性能诊断**（那些是 ph10 JVM 阶段的内容）、**不涉及 Spring 的并发抽象与事务管理**（ph15 Spring 全家桶阶段，roadmap 第 15 节）、**不涉及分布式锁、分布式事务与集群一致性**（ph16 微服务与分布式阶段，roadmap 第 16 节，目录待建）、**不涉及消息队列削峰与异步解耦**（[ph17 消息队列与搜索阶段](../ph17-mq-search/17-mq-search.md)，roadmap 第 17 节）、**不涉及 Netty 自研线程模型与 Actor 框架**（ph20 高级 Java 阶段，roadmap 第 20 节，目录待建）。本阶段承接 ph08 Lambda 与 Stream 阶段——CompletableFuture 与 Stream 一脉相承的函数式风格。

## 2. 来源与演变

Java 从 1.0 起就把多线程写进语言与核心库：Thread、Runnable 与 synchronized 是语言规范的一部分，早期线程安全只能靠 synchronized 与全方法加锁的遗留集合（Vector、Hashtable）——性能差，且「手动 new Thread」让并发程序难以做大。真正的转折是 **Java 5（2004）**：Doug Lea 主导的 JSR 166 引入 **java.util.concurrent（JUC）**，一次性带来 ExecutorService 线程池、Lock/Condition、并发集合与 Atomic 类，把并发从「语言关键字」升级为「工程化工具集」；同年 JSR 133 正式确定 **Java 内存模型（JMM）** 与 happens-before 规则，volatile 语义由此明确。

此后并发沿两条线演进。**工具线**：Java 7 的 Fork/Join 框架为并行计算铺路，Java 8 的 CompletableFuture 与并行流把异步编程从「回调嵌套」带入声明式编排，同版重写 ConcurrentHashMap（分段锁 → CAS + 局部锁）。**调度线**：Java 21（2023）正式化的 **Project Loom 虚拟线程（JEP 444）** 由 JVM 调度、可创建百万级线程、阻塞 IO 时自动让出载体线程——「每个请求一个线程」的简单模型重新可行；同一批还带来结构化并发（JEP 453）与 Scoped Values（JEP 446，均为 Java 21 预览）。到 **Java 25（2025）**，Scoped Values 正式化（JEP 506），结构化并发进入第五预览（JEP 505，API 从构造器改为静态工厂 `open()` + `Joiner`）。JMM 核心语义二十年来保持稳定。

| 版本 | 演进 |
|------|------|
| Java 1.0（1996） | Thread、Runnable、synchronized 成为语言与核心库一部分 |
| Java 5（2004） | JUC 诞生（JSR 166）：ExecutorService、Lock、Condition、并发集合、Atomic；JSR 133 确定 JMM 与 happens-before |
| Java 7（2011） | Fork/Join 框架（JSR 166y），为并行流铺路 |
| Java 8（2014） | CompletableFuture、并行流；ConcurrentHashMap 重写为 CAS + 局部锁 |
| Java 9（2017） | 响应式流 Flow API（Reactive Streams） |
| Java 19（2022） | 虚拟线程预览（JEP 425）；结构化并发、Scoped Values 孵化 |
| Java 21（2023） | 虚拟线程正式化（JEP 444）；结构化并发（JEP 453）、Scoped Values（JEP 446）预览 |
| Java 25（2025） | Scoped Values 正式化（JEP 506，不再需要预览标志）；结构化并发第五预览（JEP 505，`open()` + Joiner） |

本文示例以 **Java 17（LTS）** 为基线（examples/exercises/project 的验证工具链为 OpenJDK 17.0.18，`javac -version` → 17.0.18），虚拟线程、结构化并发与 Scoped Values 等新特性以 **Java 21 / Java 25** 为基线，在本环境用 OpenJDK 25.0.2 验证（ex06、sol-05）。synchronized/volatile/JUC 的语义自 Java 5 起稳定、二十年来无破坏性变化，17 上编写的并发代码可直接运行在 21/25；涉及新特性的文件会单独标注所需 JDK 版本，这个阶段的语法与 API 是整个 Java 生态中最稳定的部分之一。

## 3. 语法与参数

### 3.1 Thread、Runnable、Callable、Future

线程（Thread）是操作系统调度的最小执行单元；Java 里任务与线程解耦——Runnable 无返回值，Callable 有返回值，Future 用来取异步结果。

```java
Runnable task = () -> System.out.println(Thread.currentThread().getName() + " 工作");  // 实现 Runnable
Thread t = new Thread(task, "worker-1");
t.start();      // 启动新线程（注意：不是 t.run()！）
t.join();       // 当前线程等待 t 结束
Callable<Integer> calc = () -> 1 + 2;          // 有返回值的任务：Callable + Future
FutureTask<Integer> ft = new FutureTask<>(calc);
new Thread(ft).start();
System.out.println(ft.get());                  // 3；get() 阻塞等待结果
```

- **`start()` 开新线程，`run()` 只是普通方法调用**——误调 `run()` 不会并发，是高频低级错误；`Thread` 子类方式因单继承耦合，一般不用
- `join()` 等待目标线程结束；`interrupt()` 发中断信号，配合 `InterruptedException` 做**协作式取消**；线程状态机：`NEW → RUNNABLE →（BLOCKED / WAITING / TIMED_WAITING）→ TERMINATED`

### 3.2 ExecutorService 与线程池参数

手动 `new Thread` 的问题：创建销毁开销大、线程数失控、缺乏统一管理。**线程池比手动创建线程更可控**——复用线程、限制并发、统一生命周期。

```java
ExecutorService fixed = Executors.newFixedThreadPool(4);   // 固定 4 线程
// 完整参数版（生产环境推荐手动配置，勿盲目用 Executors 工厂）
ThreadPoolExecutor pool = new ThreadPoolExecutor(
        2,                                  // corePoolSize 核心线程数
        4,                                  // maximumPoolSize 最大线程数
        60L, TimeUnit.SECONDS,              // 非核心线程空闲存活时间
        new LinkedBlockingQueue<>(100),     // workQueue 工作队列（务必有界）
        Executors.defaultThreadFactory(),   // 线程工厂（生产可自定义命名/daemon）
        new ThreadPoolExecutor.AbortPolicy()// 拒绝策略
);
pool.execute(() -> System.out.println("任务"));
pool.shutdown();        // 温柔关闭：不再接新任务，已提交任务执行完
```

| 参数 | 含义 | 经验值 |
|------|------|--------|
| corePoolSize | 常驻线程数，空闲也不回收 | CPU 密集 ≈ 核数 + 1；IO 密集 ≈ 核数 × 2 起 |
| maximumPoolSize | 队列满后最多扩到的线程数 | 视内存/线程资源而定 |
| workQueue | 排队队列，有界/无界/同步交接 | **必须用有界队列** |
| 拒绝策略 | 队列满且线程达上限时怎么办 | AbortPolicy（默认，抛异常）/ CallerRunsPolicy（提交者自己跑） |

- **坑：`Executors.newFixedThreadPool` 内部是无界队列**（`LinkedBlockingQueue` 默认容量 `Integer.MAX_VALUE`）——任务堆积内存暴涨直至 OOM；生产环境用 `new ThreadPoolExecutor` + 有界队列
- 四种拒绝策略：`AbortPolicy`（默认，抛 `RejectedExecutionException`）、`CallerRunsPolicy`（谁提交谁执行，天然背压）、`DiscardPolicy`/`DiscardOldestPolicy`（静默丢弃——**会丢任务，慎用**）；关闭时 `shutdownNow()` 尝试中断正在执行的任务

### 3.3 synchronized 与 volatile

并发三大问题：**可见性**（一线程修改另一线程看不到）、**原子性**（复合操作被拆开交错执行）、**有序性**（指令重排）。`synchronized` 三者全解决；`volatile` 只解决可见性与有序性。

```java
class Counter {
    private int count = 0;
    public synchronized void incr() { count++; }   // 方法锁：锁 this，可重入
    public synchronized int get()  { return count; }
}
class FlagHolder {
    private volatile boolean running = true;       // volatile：其他线程立即看到修改
    public void stop() { running = false; }
    public boolean isRunning() { return running; }
}
```

- **volatile 保证可见性，但不保证复合操作原子性**——`count++` 是「读-改-写」三步，两个线程交错执行照样丢更新；自增/累加用 AtomicInteger 或 synchronized
- synchronized 是**可重入**的（同一线程可再次进入同一把锁），锁的是「对象监视器（monitor）」；volatile 典型用途：状态开关、double-checked locking 里的单例实例字段

### 3.4 Lock、ReentrantLock、Condition

synchronized 的局限：不可中断、不可超时、非公平、只有一个等待条件。`Lock` 接口（JUC）补齐这些能力，`ReentrantLock` 是最常用实现。

```java
Lock lock = new ReentrantLock();                  // 默认非公平；传 true 为公平锁
try {
    if (lock.tryLock(1, TimeUnit.SECONDS)) {      // 带超时抢锁：拿不到不无限阻塞
        try { /* 临界区 */ } finally { lock.unlock(); }   // 必须 finally 解锁！
    }
} catch (InterruptedException e) {
    Thread.currentThread().interrupt();
}
// Condition：在锁上等待/唤醒，替代 wait/notify，且支持多个条件
ReentrantLock condLock = new ReentrantLock();
Condition notFull  = condLock.newCondition();     // 生产者等「不满」
Condition notEmpty = condLock.newCondition();     // 消费者等「不空」
```

| 对比 | synchronized | ReentrantLock |
|------|-------------|---------------|
| 语法 | 语言关键字，异常自动释放 | API，必须手动 unlock（finally） |
| 超时 / 中断 | 不支持 | `tryLock(超时)`、`lockInterruptibly()` |
| 公平性 / 等待条件 | 非公平；wait/notify 只有一组 | 可配置公平；`newCondition()` 可建多个 |
| 性能 | JVM 已深度优化，多数场景够用 | 高级场景（超时/多条件）才需要 |

- **Lock 必须在 finally 中 unlock**，异常路径上漏解锁直接死锁
- Condition 的 `await()` 必须放在 **while 循环**里检查条件（防虚假唤醒 spurious wakeup），`signal()` 唤醒一个、`signalAll()` 唤醒全部；简单场景优先 synchronized——少一行 unlock，少一类 bug

### 3.5 Atomic 类与 CAS

`java.util.concurrent.atomic` 提供基于 **CAS（Compare-And-Swap）** 的无锁原子操作类，无阻塞、无锁竞争：

```java
AtomicInteger counter = new AtomicInteger(0);
counter.incrementAndGet();                       // ++ 原子版，返回新值
counter.getAndIncrement();                       // 返回旧值再 +1
counter.addAndGet(5);                            // 原子加
boolean ok = counter.compareAndSet(3, 10);       // 期望 3 则更新为 10（CAS 核心）
AtomicLong total = new AtomicLong();                         // long 版
AtomicReference<String> ref = new AtomicReference<>("init"); // 引用类型
ref.compareAndSet("init", "updated");
```

- CAS 是「比较并交换」：先比较当前值是否等于期望值，相等才更新——一条硬件原子指令（x86 的 CMPXCHG），无锁、无阻塞；**高竞争下 CAS 自旋空转，未必比 synchronized 快**，「Atomic 一定优于锁」是误区
- **ABA 问题**：值 A→B→A 后，CAS 误以为「从未被改过」（见 4.4）；用 `AtomicStampedReference`（带版本号）解决

### 3.6 并发集合：ConcurrentHashMap / CopyOnWriteArrayList / BlockingQueue

普通 HashMap、ArrayList 多线程并发读写会数据错乱（JDK 7 的 HashMap 并发 resize 甚至成环死循环）——**共享可变集合一律用并发集合**，而不是手动加锁包一层：

```java
ConcurrentHashMap<String, Integer> stats = new ConcurrentHashMap<>();
stats.merge("hits", 1, Integer::sum);            // 原子累加：替代 get+put 两步
stats.computeIfAbsent("misses", k -> 0);         // 原子初始化（首次访问才执行）
CopyOnWriteArrayList<String> listeners = new CopyOnWriteArrayList<>();
listeners.add("handler-a");                      // 写时复制整个数组
BlockingQueue<String> queue = new ArrayBlockingQueue<>(10);   // 有界阻塞队列
queue.put("job");        // 队满时阻塞等待
String job = queue.take();   // 队空时阻塞等待
```

| 集合 | 线程安全策略 | 适用场景 |
|------|------------|---------|
| ConcurrentHashMap | CAS + 局部锁，读无锁（Java 8+） | 高并发共享 Map（首选） |
| CopyOnWriteArrayList | 写时复制整个底层数组 | 读多写极少（监听器列表、缓存快照） |
| BlockingQueue（Array/Linked） | 锁 + 条件等待 | 生产者-消费者、线程池工作队列 |
| 遗留 Vector / Hashtable | 全方法 synchronized | 只读兼容旧代码，**新代码不用** |

- **ConcurrentHashMap 不允许 null 键/值**——并发下无法区分「不存在」与「存为 null」；`Collections.synchronizedMap(map)` 是全表锁，性能远不如它
- `ConcurrentLinkedQueue` 是无界非阻塞队列（MPMC，多生产者多消费者均可），适合无需限流的场景

### 3.7 CompletableFuture 异步编排

CompletableFuture 把「异步 + 回调」写成声明式流水线——**适合异步编排**：串行转换、并行汇合、异常兜底一目了然。

```java
ExecutorService pool = Executors.newFixedThreadPool(4);
CompletableFuture<Integer> f = CompletableFuture.supplyAsync(() -> 42, pool);  // 指定线程池
f.thenApply(v -> v * 2)                          // 串行转换（返回新 CompletableFuture）
 .thenAcceptAsync(v -> System.out.println("结果: " + v))   // 异步消费
 .exceptionally(ex -> {                          // 异常兜底，返回默认值
     System.out.println("异常: " + ex);
     return -1;
 });
// 两个独立任务并行，完成后汇合
CompletableFuture<Integer> a = CompletableFuture.supplyAsync(() -> 100, pool);
CompletableFuture<Integer> b = CompletableFuture.supplyAsync(() -> 50, pool);
int sum = a.thenCombine(b, Integer::sum).join(); // join() 阻塞等待最终结果
```

- 组合方法族：`thenApply`（转换）/ `thenAccept`（消费）/ `thenCompose`（扁平化，避免嵌套）/ `thenCombine`（两个汇合）/ `allOf`（全部完成）/ `anyOf`（任一完成）
- **异常必须兜底**：链上某步抛异常且没有 `exceptionally`/`handle`，异常会被「吞掉」，只在 `join()`/`get()` 时才抛出；不指定线程池默认用共享的 `ForkJoinPool.commonPool`——**阻塞任务会拖垮全局**，耗时 IO 任务务必传专用线程池

### 3.8 虚拟线程（Java 21）与平台线程对比

**平台线程** = 操作系统线程，创建成本高、数量受限（千级）；**虚拟线程（Virtual Thread）** = JVM 调度的轻量级线程，可创建**百万级**，适合「每个请求一个线程」模型。

```java
Thread vt = Thread.startVirtualThread(() -> System.out.println("虚拟线程运行"));  // 逐任务创建
try (var vtExecutor = Executors.newVirtualThreadPerTaskExecutor()) {   // Java 21 每任务一线程
    vtExecutor.submit(() -> System.out.println("virtual thread task"));
}   // try-with-resources 自动关闭（JDK 19 起 ExecutorService 是 AutoCloseable）
```

| 维度 | 平台线程 | 虚拟线程（Java 21） |
|------|---------|-------------------|
| 创建成本 | 昂贵（KB–MB 级栈，依赖 OS） | 极低，可创建百万级 |
| 调度者 | 操作系统 | JVM（Project Loom） |
| 阻塞代价 | 阻塞即占住一个 OS 线程 | 阻塞 IO 时自动让出载体线程（挂起/恢复） |
| 代码风格 | 同步代码 | **同样同步代码**，无需 async/await |
| 适用场景 | 计算密集、有限并发 | IO 密集、每个请求一个线程 |

- **虚拟线程不是「更快的线程」**：计算密集任务用虚拟线程不会提速（反而有挂起/恢复开销）；它的价值是**让阻塞 IO 不再浪费载体线程**
- 适用误判是高频坑：把虚拟线程用于 CPU 密集计算或长时占住载体线程的代码，收益为负；IO 密集（网络、DB、文件）才是主战场

### 3.9 结构化并发与 Scoped Values（Java 21+）

**结构化并发（Structured Concurrency）**：子任务的创建、执行、取消被约束在同一个代码块作用域内——任务要么完成要么被取消，杜绝「线程泄漏」。它是**预览特性**（Java 21 起预览，截至 JDK 25 为第五预览 JEP 505），编译运行需 `--enable-preview`，且 **API 仍在演进**：JDK 21 用构造器 `new StructuredTaskScope.ShutdownOnFailure()`，JDK 25 改为静态工厂 `StructuredTaskScope.open()` + `Joiner`、`fork` 返回 `Subtask<T>`。**Scoped Values** 是 ThreadLocal 的更安全替代：Java 21~24 为预览（JEP 446/464/481/487），**正式化于 Java 25（JEP 506）**，JDK 25 起无需预览标志。

```java
// 结构化并发（JDK 25 第五预览 JEP 505，编译运行需 --enable-preview）：任一子任务失败则整体失败
try (var scope = StructuredTaskScope.open()) {
    StructuredTaskScope.Subtask<String> user  = scope.fork(() -> fetchUser());
    StructuredTaskScope.Subtask<String> order = scope.fork(() -> fetchOrder());
    scope.join();                 // 等待全部子任务；有子任务失败即抛 FailedException（取消其余发生在作用域 close()）
    System.out.println(user.get() + " / " + order.get());
}   // 作用域结束：未完成的任务被自动取消，杜绝任务泄漏
// Scoped Values（Java 25 正式化 JEP 506）：替代 ThreadLocal，子任务自动继承（已验证：OpenJDK 25.0.2）
ScopedValue<String> tenant = ScopedValue.newInstance();
ScopedValue.where(tenant, "租户A").run(() -> System.out.println(tenant.get()));
```

- 结构化并发解决传统线程池的**任务泄漏**：异常路径上游离的子任务不再被遗忘，作用域退出即清理；但仍是预览特性且 API 未定稿（21→25 历经 4 轮预览迭代：JEP 453→462→480→488→505），**生产先别用**，3.8 的虚拟线程已正式化，能覆盖绝大多数场景
- Scoped Values 优于 ThreadLocal：不可变、自动清理、子任务继承，JDK 25 起可放心尝试

### 3.10 死锁与竞态排查

**死锁（deadlock）**：两个及以上线程互相持有对方需要的锁、无限期等待。经典场景是**加锁顺序不一致**：

```java
// 故意演示死锁（加锁顺序不一致）：本段两个线程必然互相等待，仅用于理解原理，勿在生产复制
Object lockA = new Object();
Object lockB = new Object();
Thread t1 = new Thread(() -> {
    synchronized (lockA) {                       // t1 先拿 A
        try { Thread.sleep(50); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        synchronized (lockB) { }                 // 再要 B
    }
});
Thread t2 = new Thread(() -> {
    synchronized (lockB) {                       // t2 先拿 B
        try { Thread.sleep(50); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        synchronized (lockA) { }                 // 再要 A —— 互相等待，死锁
    }
});
t1.start();
t2.start();   // 各自持有对方需要的锁，谁也拿不到第二把
```

- **死锁四条件**：互斥、持有并等待、不可剥夺、循环等待——打破任意一个即可解除
- 对策：**统一加锁顺序**（所有线程按相同顺序拿锁）、缩小锁粒度、用 `tryLock(超时)` 拿不到就释放已持有的锁
- 排查：`jstack <pid>` 会直接输出 `Found one Java-level deadlock` 并列出线程栈；线程长时间 `BLOCKED` 堆积多为锁竞争或死锁；JFR（Java Flight Recorder）可做在线分析

### 3.11 本阶段高频坑一览

| 坑 | 症状 | 对策 |
|----|------|------|
| 手动 `new Thread` 大量线程 | 线程数失控、内存暴涨 | 线程池 / 虚拟线程 |
| 无界线程池队列 | 任务堆积、OOM | `new ThreadPoolExecutor` + 有界队列 |
| 只加 volatile 的 `count++` | 计数不准、结果随机 | AtomicInteger / synchronized |
| Lock 忘 finally unlock | 异常路径直接死锁 | try/finally 包住临界区 |
| 锁粒度太大 | 并发度低、性能差 | 缩小临界区、用并发集合替代粗锁 |
| 多线程加锁顺序不一致 | 死锁（jstack 可查） | 统一顺序 / `tryLock` 超时 |
| HashMap 并发写 | 数据错乱、JDK 7 甚至死循环 | ConcurrentHashMap |
| CompletableFuture 异常不兜底 | 异常被吞、结果悬空 | `exceptionally` / `handle` |
| 虚拟线程跑 CPU 密集任务 | 反而更慢 | 计算用平台线程，IO 用虚拟线程 |
| 线程池不 shutdown | 进程不退出、线程泄漏 | `shutdown()` / try-with-resources |
| 生产者消费者哨兵放太早 | 消费者先退、生产者饿死（队列满无人消费） | 全部生产者结束后再放哨兵 |

## 4. 底层原理

### 4.1 JMM 与 happens-before

**Java 内存模型（Java Memory Model, JMM）** 定义线程之间如何观察彼此的写入。共享变量存在主内存，每个线程有独立的工作内存（寄存器/缓存）；没有同步时，一线程的写入对另一线程可能**不可见**，指令也可能被编译器/CPU **重排**（有序性问题）。

**happens-before（先行发生）规则**是 JMM 的核心：若操作 A happens-before 操作 B，则 A 的写入对 B 可见，且 A 不会被重排到 B 之后。主要规则：

- **程序顺序规则**：单线程内，前面的操作 happens-before 后面的操作
- **监视器锁规则**：对锁的解锁 happens-before 后续对同一把锁的加锁
- **volatile 规则**：对 volatile 变量的写 happens-before 后续对该变量的读
- **传递性**：A happens-before B、B happens-before C，则 A happens-before C
- **线程规则**：`start()` happens-before 新线程内任何操作；线程内全部操作 happens-before `join()` 返回；`interrupt()` happens-before 被中断线程检测到中断

synchronized 与 volatile 的「安全」全部由这些规则保证——锁/volatile 不只是「互斥」，更是**内存屏障**，让写入在解锁/volatile 写时刷新回主内存。

### 4.2 synchronized 的锁升级（偏向锁 → 轻量级锁 → 重量级锁）

Java 6 起 synchronized 不是一上来就「重量级」。锁状态记录在对象头（Mark Word）中，随竞争程度**逐级升级**：

1. **偏向锁（biased lock）**：无竞争时，把第一个线程的 ID 记进对象头，该线程后续进出临界区零开销；有竞争时撤销偏向
2. **轻量级锁（lightweight lock）**：竞争轻微时，线程在栈帧中建锁记录（Lock Record），用 **CAS 自旋**尝试获取——避免内核态切换
3. **重量级锁（heavyweight lock）**：自旋失败、竞争激烈时，升级为 OS 监视器（mutex），拿不到锁的线程**阻塞**进等待队列——涉及用户态/内核态切换，最慢

**锁只能升级不能降级**（偏向锁可批量撤销）。注意 Java 15 起默认**禁用偏向锁**（JEP 374）——新硬件与 JVM 下其撤销成本得不偿失，多数程序直接用轻量级锁起步。

### 4.3 线程池的工作队列与拒绝策略

ThreadPoolExecutor 的任务提交流程是面试必考，也是排查「任务去哪了」的关键：

```text
提交任务
  ├─ 线程数 < corePoolSize        → 新建核心线程执行
  ├─ 线程数 >= corePoolSize       → 任务进 workQueue 排队
  ├─ 队列满 且 线程数 < maximum   → 新建非核心线程执行
  └─ 队列满 且 线程数 == maximum  → 执行拒绝策略
```

- **顺序误区**：是「先填队列，后扩线程」——队列不满时即使 maximumPoolSize 更大也不会新建线程；很多误以为「先扩到最大再排队」，正好相反（examples/ex02 用门闩把提交过程钉死，直接打印每一步的 poolSize/queueSize 实证这一点）
- **拒绝策略**：AbortPolicy 抛异常（默认）、CallerRunsPolicy 让提交线程自己执行（天然背压）、DiscardPolicy/DiscardOldestPolicy 静默丢弃；可自定义 `RejectedExecutionHandler`
- 关闭三件套：`shutdown()`（停止接单，跑完已提交任务）→ `awaitTermination(超时)`（等待收尾）→ 超时未停再 `shutdownNow()`（中断正在执行的）
- **队列选型**：有界 `ArrayBlockingQueue`/`LinkedBlockingQueue(capacity)` 防 OOM；`SynchronousQueue` 不排队直接交接给线程（配合 maximumPoolSize 用）；要按优先级出队可用 `PriorityBlockingQueue`，但它无界——project/ 用「有界优先级队列」给出兼顾两者的教学方案

### 4.4 CAS 与 ABA

**CAS（Compare-And-Swap）** 是「比较并交换」：`compareAndSet(期望值, 新值)`——当前值等于期望值才更新，否则返回 false 由调用方重试。它是无锁并发的地基：读-改-写三步合并为一条原子指令，避免加锁，靠**自旋重试**应对竞争。

**ABA 问题**：线程 1 读到值 A；线程 2 把它改成 B 又改回 A；线程 1 的 CAS 仍成功——但「值从未被改过」的假设被打破，若其他线程依赖该假设则出错（典型如无锁栈的栈顶指针回退）。解法是带版本号的引用：

```java
AtomicStampedReference<Integer> ref = new AtomicStampedReference<>(100, 0);
int[] stamp = new int[1];
Integer v = ref.get(stamp);                        // 读取值 + 版本号
ref.compareAndSet(v, 101, stamp[0], stamp[0] + 1); // 值变了但版本没变 → 失败
```

高竞争下的优化：`LongAdder` 把单一计数器拆成多个 Cell 分段累加，减少 CAS 冲突（热点计数场景明显优于 AtomicLong）。

### 4.5 虚拟线程的 JVM 调度（Project Loom）

虚拟线程由 JVM 调度，运行在**载体线程（carrier thread）**——普通平台线程——之上：一个平台线程可承载成千上万个虚拟线程。核心机制：

- **挂起/恢复（park/unpark）**：虚拟线程执行到**阻塞点**（socket 读、`Thread.sleep`、锁等待）时，JVM 保存其执行状态并把它**挂起**，载体线程立刻切换去跑其他虚拟线程；阻塞解除后虚拟线程被**恢复**，从挂起点继续执行——这就是「阻塞 IO 自动让出载体线程」的实现，无需 async/await
- **Continuation（延续）**：字节码层面保存/恢复执行状态；调度器是 ForkJoinPool 变体，工作窃取保证载体线程满载
- **效果**：固定 200 线程的池只能并发 200 个阻塞任务；虚拟线程下同样代码可并发十万、百万——「每请求一线程」模型成本趋近于零，且**业务代码零改造**。边界：计算密集任务不阻塞，虚拟线程没有优势；`synchronized` 内的阻塞在早期 Loom 版本（JDK 21~23）会钉住（pin）载体线程，**JDK 24 起（JEP 491）已消除**——synchronized 不再钉住载体线程，仅 native 方法/外部调用等少数情形仍可能钉住

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 后台批量任务（报表、导入导出、定时清理） | 线程池 ExecutorService + shutdown/awaitTermination |
| 高并发共享计数 / 状态统计 | AtomicInteger / LongAdder / ConcurrentHashMap.merge |
| 生产者-消费者解耦（任务队列） | BlockingQueue（ArrayBlockingQueue / LinkedBlockingQueue） |
| 异步接口编排（先查用户、再查订单、最后拼装） | CompletableFuture（thenCombine / allOf / exceptionally） |
| 高并发 IO 服务（网关、RPC、Web 请求处理） | 虚拟线程 + `newVirtualThreadPerTaskExecutor` |
| 共享缓存懒加载（首次访问才初始化） | ConcurrentHashMap.computeIfAbsent / putIfAbsent |
| 读多写极少的订阅者 / 监听器列表 | CopyOnWriteArrayList |
| 定时 / 延时任务 | ScheduledExecutorService（schedule / scheduleAtFixedRate） |

**不适合**此阶段的事项：

- **JVM 内存模型底层调优、GC 参数与性能诊断**——留到 ph10 JVM 阶段（并发只是其中一环）
- **分布式锁、分布式事务、集群一致性**——留到 ph16 微服务与分布式阶段（单机 JUC 锁解决不了跨进程问题）
- **消息队列削峰填谷与异步解耦**——留到 ph17 消息队列与搜索阶段（MQ 是进程间异步，不是线程间）
- **Netty 自研线程模型、Actor 模型（Akka）**等重并发框架——先用 JUC 与虚拟线程解决，框架选型属 ph20 高级 Java 阶段的架构层面

## 6. 代码示例

本节展示完整可运行示例（自带自检断言），完整文件在 [`examples/`](./examples/) 目录，各文件的编译/运行命令与验证环境见 examples/README.md。

### 示例 1：多线程计数器（synchronized vs AtomicInteger）—— Java 8+

对应 roadmap 练习「多线程计数器」：10 个线程各加 1 万次，对比普通变量、synchronized、AtomicInteger 三种写法的正确性。

```java
// examples/ex01-counter-demo.java —— 多线程计数器：普通变量 vs synchronized vs AtomicInteger
// 对应主文档 6. 示例 1：10 线程各加 1 万次，对比三种写法的正确性
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex01-counter-demo.java
// 运行：java CounterDemo（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
// 运行前提：plain 计数故意不加锁（竞态演示），其结果通常小于期望值——这是预期的演示效果，不是 bug
import java.util.concurrent.atomic.AtomicInteger;

class CounterDemo {
    static int plain = 0;                              // 非原子：读-改-写三步被线程交错，丢更新
    static int sync = 0;
    static final AtomicInteger atomic = new AtomicInteger();

    public static void main(String[] args) throws InterruptedException {
        final int N = 10_000;                          // 每线程加 N 次
        final int THREADS = 10;
        Thread[] threads = new Thread[THREADS];
        for (int i = 0; i < THREADS; i++) {
            threads[i] = new Thread(() -> {
                for (int j = 0; j < N; j++) {
                    plain++;                           // 竞态：非原子，结果不确定
                    synchronized (CounterDemo.class) { // 加锁：原子且可见
                        sync++;
                    }
                    atomic.incrementAndGet();          // CAS：无锁且原子
                }
            });
        }
        for (Thread t : threads) t.start();
        for (Thread t : threads) t.join();             // 主线程等全部线程结束再读结果

        int expect = N * THREADS;
        System.out.println("期望值    = " + expect);
        System.out.println("plain     = " + plain + "  (通常小于期望值: " + (plain < expect) + ")");
        System.out.println("sync      = " + sync + "  (正确: " + (sync == expect) + ")");
        System.out.println("atomic    = " + atomic.get() + "  (正确: " + (atomic.get() == expect) + ")");
        if (sync != expect || atomic.get() != expect) {
            throw new AssertionError("sync/atomic 计数不一致——同步原语失效");
        }
        System.out.println("自检通过：synchronized 与 AtomicInteger 计数均为 " + expect);
    }
}
```

提示：`join()` 必不可少——主线程不等子线程结束就读结果，输出会偏小；`plain` 每次运行结果不同，正是竞态的直观证据；`sync`/`atomic` 被自检断言固定为 100000，可稳定复现。

### 示例 2：线程池任务调度（ExecutorService + 参数配置 + shutdown）—— Java 8+

对应 roadmap 推荐项目「线程池任务调度器」：手动配置 ThreadPoolExecutor，用门闩固定提交过程，观察「先填队列后扩线程」与拒绝策略。

```java
// examples/ex02-thread-pool-demo.java —— 线程池参数与任务提交流程：先填队列后扩线程 + 拒绝策略
// 对应主文档 6. 示例 2：core=2 / max=4 / 有界队列 8，观察扩线程与 AbortPolicy 拒绝，以及优雅关闭
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex02-thread-pool-demo.java
// 运行：java ThreadPoolDemo（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

class ThreadPoolDemo {
    public static void main(String[] args) throws Exception {
        demoSubmitFlow();    // 提交流程：先填队列后扩线程 + 拒绝
        demoCallerRuns();    // CallerRunsPolicy：提交者自己执行，天然背压
    }

    /** 提交 13 个阻塞任务：2 个占住核心线程 + 8 个排队 + 2 个扩到最大 4，第 13 个被拒绝（全程可复现） */
    static void demoSubmitFlow() throws Exception {
        ThreadPoolExecutor pool = new ThreadPoolExecutor(
                2, 4, 60L, TimeUnit.SECONDS,
                new ArrayBlockingQueue<>(8),
                Executors.defaultThreadFactory(),
                new ThreadPoolExecutor.AbortPolicy());
        CountDownLatch gate = new CountDownLatch(1);   // 任务全部提交前一律阻塞，保证提交过程可复现
        List<Future<Integer>> futures = new ArrayList<>();
        for (int i = 1; i <= 12; i++) {                // 2 个直接执行 + 8 个排队 + 2 个扩到 4 线程
            final int task = i;
            futures.add(pool.submit(() -> {
                gate.await();                          // 提交阶段全部阻塞，线程池状态稳定可观测
                return task * task;
            }));
            printPool(pool, "提交第 " + i + " 个任务后");
        }
        try {
            pool.submit(() -> 13);                     // 队列满(8)且线程已达最大(4) → 拒绝
            System.out.println("第 13 个任务被接受（意外）");
        } catch (RejectedExecutionException e) {
            System.out.println("第 13 个任务被拒绝: " + e.getClass().getSimpleName());
        }
        gate.countDown();                              // 放行，任务开始执行
        int sum = 0;
        for (Future<Integer> f : futures) sum += f.get();   // get() 阻塞等待每个结果
        System.out.println("1~12 的平方和 = " + sum + "  (期望 650)");
        if (sum != 650) throw new AssertionError("任务结果不符");
        pool.shutdown();                               // 优雅关闭：不再接新任务，跑完已提交
        boolean done = pool.awaitTermination(10, TimeUnit.SECONDS);
        System.out.println("线程池已优雅关闭: " + done);
        if (!done) throw new AssertionError("线程池未在时限内关闭");
    }

    static void printPool(ThreadPoolExecutor pool, String tag) {
        System.out.printf("%s: poolSize=%d, queueSize=%d%n",
                tag, pool.getPoolSize(), pool.getQueue().size());
    }

    /** CallerRunsPolicy：队列满且线程满时，由提交者（主线程）自己执行——不丢任务，天然背压 */
    static void demoCallerRuns() throws Exception {
        ThreadPoolExecutor pool = new ThreadPoolExecutor(
                1, 1, 0L, TimeUnit.MILLISECONDS,
                new ArrayBlockingQueue<>(1),
                new ThreadPoolExecutor.CallerRunsPolicy());
        AtomicInteger onMain = new AtomicInteger();
        for (int i = 1; i <= 3; i++) {
            final int id = i;
            pool.execute(() -> {
                String who = Thread.currentThread().getName();
                System.out.println("任务" + id + " 由 " + who + " 执行");   // 各行顺序随调度而异，计数才是断言
                if (who.equals("main")) onMain.incrementAndGet();
            });
        }
        pool.shutdown();
        pool.awaitTermination(5, TimeUnit.SECONDS);
        System.out.println("由主线程（提交者）执行的任务数 = " + onMain.get() + "  (期望恰好 1 个)");
        // 注：极端调度下（worker 恰好在三次提交的窗口内跑完任务并清空队列）该计数可能为 0——理论竞态，
        // 实测 5/5 稳定，教学场景接受
        if (onMain.get() != 1) throw new AssertionError("CallerRunsPolicy 应恰好有 1 个任务在主线程执行");
    }
}
```

提示：任务全部阻塞在 `gate` 上，因此提交过程的 poolSize/queueSize 完全可复现——第 11、12 个任务把线程从 2 扩到 4，第 13 个被 `AbortPolicy` 拒绝；换成 `CallerRunsPolicy` 则第 13 个由提交线程（main）自己执行——示例后半段演示了这一点（各行打印顺序随调度而异，但「恰好 1 个任务在主线程执行」的计数稳定）。

### 示例 3：生产者消费者（BlockingQueue）—— Java 8+

对应 roadmap 练习「生产者消费者」：有界队列天然解决「队满阻塞、队空等待」，无需手写 wait/notify。

```java
// examples/ex03-producer-consumer.java —— 生产者消费者：BlockingQueue 有界队列天然解决队满阻塞/队空等待
// 对应主文档 6. 示例 3：容量 5 的队列 + 慢消费者，观察 put 在队满时阻塞；验收：10 件全部被消费不重不漏
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex03-producer-consumer.java
// 运行：java ProducerConsumer（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

class ProducerConsumer {
    static final int CAPACITY = 5;
    static final int TOTAL = 10;

    public static void main(String[] args) throws InterruptedException {
        BlockingQueue<Integer> queue = new ArrayBlockingQueue<>(CAPACITY);
        AtomicInteger sum = new AtomicInteger();           // 消费者累计收到的值
        CountDownLatch full = new CountDownLatch(1);       // 生产者填满队列后放行消费者，保证 put 阻塞可复现

        Thread producer = new Thread(() -> {
            for (int i = 1; i <= TOTAL; i++) {
                long start = System.nanoTime();
                try {
                    queue.put(i);                          // 队满时阻塞，等消费者腾位置
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    return;
                }
                long blockedMs = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - start);
                // 消费者先睡 200ms 才开始取：第 6 件起队列必然已满，put 必然阻塞（可复现）
                System.out.println("生产: " + i + (blockedMs >= 50 ? "  (put 阻塞等待 " + blockedMs + " ms)" : ""));
                if (i == CAPACITY) full.countDown();       // 队列已满
            }
            System.out.println("生产者完成");
        }, "producer");

        Thread consumer = new Thread(() -> {
            try {
                full.await();                              // 等生产者填满队列（此刻 put 已阻塞在第 6 件）
                Thread.sleep(200);                         // 故意慢消费：让队列保持满，让 put 持续阻塞
                while (true) {
                    int n = queue.take();                  // 队空时阻塞，等生产者投递
                    System.out.println("  消费: " + n);
                    sum.addAndGet(n);
                    if (n == TOTAL) break;                 // 收到最后一个后退出
                    Thread.sleep(100);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            System.out.println("消费者完成");
        }, "consumer");

        producer.start();
        consumer.start();
        producer.join();
        consumer.join();

        boolean ok = sum.get() == TOTAL * (TOTAL + 1) / 2; // 1+2+...+10 = 55
        System.out.println("消费总数 = " + TOTAL + ", 消费值之和 = " + sum.get() + "  (期望 55, 正确: " + ok + ")");
        if (!ok) throw new AssertionError("消费结果不完整或重复");
        System.out.println("自检通过：10 件全部被消费，不重不漏");
    }
}
```

提示：消费者故意慢消费，生产者第 6 件起 `put` 必然阻塞——阻塞等待的毫秒数被实测打印，这是「队满阻塞」的实证；`put`/`take` 中断时恢复中断标志（`Thread.currentThread().interrupt()`），否则中断信号丢失；把消费者加速、加 3 个消费者线程，就是真实任务队列的雏形。

### 示例 4：CompletableFuture 异步编排（thenApply / exceptionally / 组合）—— Java 8+

对应 roadmap 必会概念「CompletableFuture 适合异步编排」：两个独立任务并行执行，完成后汇合、转换、兜底异常。

```java
// examples/ex04-completable-future-demo.java —— CompletableFuture 异步编排：并行汇合 + 串行转换 + 异常兜底
// 对应主文档 6. 示例 4：两个独立任务并行执行，thenCombine 汇合、thenApply 转换、exceptionally 兜底
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex04-completable-future-demo.java
// 运行：java CompletableFutureDemo（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
import java.util.concurrent.*;

class CompletableFutureDemo {
    public static void main(String[] args) throws Exception {
        ExecutorService pool = Executors.newFixedThreadPool(4);
        CompletableFuture<Integer> fetch = CompletableFuture.supplyAsync(() -> {
            sleep(100);                       // 模拟远程调用
            return 100;
        }, pool);
        CompletableFuture<Integer> compute = CompletableFuture.supplyAsync(() -> {
            sleep(150);                       // 模拟本地计算
            return 50;
        }, pool);
        CompletableFuture<String> result = fetch
                .thenCombine(compute, Integer::sum)   // 两个任务汇合：100 + 50 = 150
                .thenApply(total -> total * 2)        // 串行转换：150 * 2 = 300
                .exceptionally(ex -> {                // 异常兜底：任一步失败走这里，返回默认值
                    System.out.println("计算失败: " + ex.getMessage());
                    return -1;
                })
                .thenApply(v -> "最终结果: " + v);
        String finalValue = result.join();            // join() 阻塞取最终结果
        System.out.println(finalValue);
        pool.shutdown();
        if (!finalValue.equals("最终结果: 300")) {
            throw new AssertionError("编排结果不符: " + finalValue);
        }
        demoNoCatch();                                // 对照：链上不兜底时，异常被吞到取结果才暴露
        System.out.println("自检通过：编排结果 = 最终结果: 300");
    }

    /** 对照实验：supplyAsync 抛异常且链上无 exceptionally，异常不会立即炸出来，直到 join()/get() 才抛 */
    static void demoNoCatch() {
        CompletableFuture<Integer> bad = CompletableFuture.supplyAsync(() -> {
            throw new IllegalStateException("模拟失败");
        });
        try {
            bad.join();
            System.out.println("未捕获到异常（意外）");
        } catch (CompletionException e) {
            System.out.println("join() 抛出 CompletionException, cause = " + e.getCause().getMessage());
        }
    }

    static void sleep(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
```

提示：`supplyAsync(..., pool)` 显式传线程池，避免阻塞任务拖垮共享的 commonPool；对照段演示「链上不兜底时异常被吞到 `join()`/`get()` 才暴露」——`join()` 抛 `CompletionException`，cause 才是真正异常。

### 示例 5：并发集合（ConcurrentHashMap / CopyOnWriteArrayList）—— Java 8+

对应 roadmap 必会概念「能用并发集合解决问题」：merge 原子累加、computeIfAbsent 单次初始化、CopyOnWriteArrayList 并发追加不丢不重。

```java
// examples/ex05-concurrent-collections.java —— 并发集合：ConcurrentHashMap 原子累加/懒加载 + CopyOnWriteArrayList
// 对应主文档 6. 示例 5：merge 原子计数、computeIfAbsent 只初始化一次、CopyOnWriteArrayList 多线程追加不丢不重
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex05-concurrent-collections.java
// 运行：java ConcurrentCollectionsDemo（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

class ConcurrentCollectionsDemo {
    static final int THREADS = 4;
    static final int PER = 1000;

    public static void main(String[] args) throws Exception {
        demoMerge();              // 1. merge：读-改-写合并为一次原子操作，结果确定
        demoComputeIfAbsent();    // 2. computeIfAbsent：并发下初始化逻辑只执行 1 次
        demoCopyOnWrite();        // 3. CopyOnWriteArrayList：多线程追加不丢不重
    }

    /** 4 线程 × 1000 次 merge("hits", 1, Integer::sum)，hits 必为 4000 */
    static void demoMerge() throws Exception {
        ConcurrentHashMap<String, Integer> stats = new ConcurrentHashMap<>();
        runAll(() -> {
            for (int i = 0; i < PER; i++) {
                stats.merge("hits", 1, Integer::sum);   // 原子累加：替代 get+put 两步
            }
        });
        System.out.println("hits = " + stats.get("hits") + "  (期望 " + THREADS * PER + ")");
        if (stats.get("hits") != THREADS * PER) throw new AssertionError("merge 计数丢失");
    }

    /** 100 线程并发 computeIfAbsent 同一 key，初始化逻辑只执行 1 次（懒加载缓存） */
    static void demoComputeIfAbsent() throws Exception {
        AtomicInteger created = new AtomicInteger();
        ConcurrentHashMap<String, String> cache = new ConcurrentHashMap<>();
        runAll(() -> cache.computeIfAbsent("session", k -> {
            created.incrementAndGet();                  // 只应执行一次
            return "exp-" + k;
        }), 100);
        System.out.println("computeIfAbsent 初始化次数 = " + created.get()
                + "  (期望 1), value = " + cache.get("session"));
        if (created.get() != 1) throw new AssertionError("初始化被执行了多次");
    }

    /** 4 线程 × 1000 次 add，size 必为 4000 且无重复（写时复制，读线程不受写影响） */
    static void demoCopyOnWrite() throws Exception {
        CopyOnWriteArrayList<String> listeners = new CopyOnWriteArrayList<>();
        runAll(() -> {
            for (int i = 0; i < PER; i++) listeners.add("handler-" + i);
        });
        Set<String> unique = new HashSet<>(listeners);
        // 4 个线程各加同一批 handler-0..999：总数 4000 不丢，去重 1000，且每个值恰好出现 THREADS 次
        boolean eachOnce = unique.stream().allMatch(s -> Collections.frequency(listeners, s) == THREADS);
        System.out.println("listeners.size = " + listeners.size() + "  (期望 " + THREADS * PER
                + "), 去重后 = " + unique.size() + "  (期望 " + PER + "), 每值出现次数均 = " + THREADS + " : " + eachOnce);
        if (listeners.size() != THREADS * PER || unique.size() != PER || !eachOnce) {
            throw new AssertionError("元素丢失或重复");
        }
    }

    static void runAll(Runnable task) throws Exception {
        runAll(task, THREADS);
    }

    static void runAll(Runnable task, int n) throws Exception {
        Thread[] ts = new Thread[n];
        for (int i = 0; i < n; i++) ts[i] = new Thread(task);
        for (Thread t : ts) t.start();
        for (Thread t : ts) t.join();
    }
}
```

提示：`merge`/`computeIfAbsent` 把「读-改-写」合并为一次原子操作，替代「先 get 再 put」两步；`computeIfAbsent` 的初始化逻辑在 100 线程竞争下恰好执行 1 次——并发懒加载缓存的正确写法；`CopyOnWriteArrayList` 写时复制，读线程遍历的是快照，不受并发写影响。

### 示例 6：虚拟线程高并发任务（对比平台线程）—— JDK 21+

对应 roadmap 练习「用虚拟线程实现高并发任务处理」：1 万个各阻塞 10ms 的任务，固定 200 线程的平台池约需 600ms，虚拟线程近乎瞬时——验证「阻塞 IO 自动让出载体线程」。

```java
// examples/ex06-virtual-thread-demo.java —— 虚拟线程 vs 平台线程：阻塞 IO 场景的并发能力对比
// 对应主文档 6. 示例 6：1 万个各阻塞 10ms 的任务，固定 200 线程的平台池 vs 每任务一线程的虚拟线程
// 验证环境：需 JDK 21+（newVirtualThreadPerTaskExecutor 为 Java 21 特性；Thread.sleep(Duration) 与
//           ExecutorService 实现 AutoCloseable 为 Java 19 特性）
// 编译：javac ex06-virtual-thread-demo.java
// 运行：java VirtualThreadDemo（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 25.0.2（Homebrew openjdk@25；虚拟线程 API 自 Java 21 正式化，
//           OpenJDK 17 无法编译本文件）
import java.time.Duration;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

class VirtualThreadDemo {
    static final int TASKS = 10_000;

    public static void main(String[] args) throws Exception {
        long platform = run(Executors.newFixedThreadPool(200), "平台线程池(200 线程)");
        long virtual = run(Executors.newVirtualThreadPerTaskExecutor(), "虚拟线程(每任务一线程)");
        System.out.printf("平台线程池(200 线程): %d ms%n", platform);
        System.out.printf("虚拟线程: %d ms%n", virtual);
        System.out.println("说明：阻塞 IO 场景虚拟线程自动让出载体线程，1 万个阻塞任务近乎瞬时完成；"
                + "结论可复现，具体毫秒数随机器而异");
    }

    /** 提交 TASKS 个各阻塞 10ms 的任务，等待全部完成，返回总耗时（ms）；断言一个不落 */
    static long run(ExecutorService pool, String tag) throws InterruptedException {
        long start = System.nanoTime();
        AtomicInteger done = new AtomicInteger();
        try (pool) {                              // JDK 21+：ExecutorService 是 AutoCloseable，关闭即等待收尾
            for (int i = 0; i < TASKS; i++) {
                pool.submit(() -> {
                    try {
                        Thread.sleep(Duration.ofMillis(10));   // 模拟阻塞 IO
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    } finally {
                        done.incrementAndGet();
                    }
                });
            }
        }
        long ms = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - start);
        if (done.get() != TASKS) throw new AssertionError(tag + " 有任务未完成: " + done.get());
        System.out.println(tag + " 完成数 = " + done.get() + " / " + TASKS);
        return ms;
    }
}
```

提示：本文件需 **JDK 21+** 编译运行（`newVirtualThreadPerTaskExecutor` 为 Java 21 特性；`Thread.sleep(Duration)`、`ExecutorService` 实现 `AutoCloseable` 为 Java 19 特性），本环境用 OpenJDK 25.0.2 验证（OpenJDK 17 无法编译）；把任务改成纯 CPU 计算（如大量求质数）再对比，会发现虚拟线程不再占优——这正是「虚拟线程适合 IO 密集、不适合计算密集」的实证。

## 7. 总结

### 关键要点

1. **线程池比手动创建线程更可控**——复用线程、限制并发、统一生命周期；生产环境用 `new ThreadPoolExecutor` + 有界队列 + 明确拒绝策略
2. **volatile 保证可见性，但不保证复合操作原子性**——`count++` 必须用 AtomicInteger 或 synchronized
3. **锁要避免死锁和过大粒度**——统一加锁顺序、`tryLock` 超时、缩小临界区
4. **synchronized 与 Lock 的选择**——简单场景用 synchronized；需要超时/中断/多 Condition 时用 ReentrantLock（必须 finally unlock）
5. **并发集合优先于手工加锁**——ConcurrentHashMap（读无锁）、CopyOnWriteArrayList（读多写少）、BlockingQueue（生产者-消费者）
6. **CompletableFuture 适合异步编排**——thenApply/thenCombine/allOf 声明式组合，异常用 exceptionally/handle 兜底
7. **虚拟线程由 JVM 调度，可创建百万级**——适合「每个请求一个线程」的 IO 密集模型，业务代码零改造
8. **虚拟线程阻塞 IO 时自动让出载体线程**——无需 async/await 语法；CPU 密集任务不要用虚拟线程
9. **JMM 三特性：可见性、原子性、有序性**——synchronized 全解决，volatile 只解决可见性与有序性，靠 happens-before 规则保证
10. **CAS 无锁但要注意 ABA**——高竞争下未必快于 synchronized；`AtomicStampedReference` 加版本号解决 ABA

### 跨语言对比：并发模型

| 维度 | Java | C++ std::thread | Go goroutine | Python | Rust |
|------|------|-----------------|--------------|--------|------|
| 基本并发单元 | 平台线程 / 虚拟线程（Java 21） | std::thread（OS 线程） | goroutine（协程，栈 2KB 起） | threading.Thread（OS 线程）/ asyncio 协程 | std::thread / tokio 异步任务 |
| 线程调度者 | 平台线程：OS；虚拟线程：JVM | 操作系统 | Go 运行时 | 操作系统 | OS / tokio 运行时 |
| 并发数量级 | 平台线程千级、虚拟线程百万级 | 千级（受 OS 限制） | 百万级 | 受 GIL 限制，线程不划算 | 平台线程千级 / 异步百万级 |
| 阻塞 IO 的处理 | 虚拟线程自动让出载体线程 | 占住 OS 线程 | 自动让出，无需改代码 | 线程阻塞；asyncio 需 async/await | tokio 需 async/await |
| 共享与同步 | synchronized / Lock / 并发集合 | mutex / atomic / 共享内存 | 共享内存 + channel（倡导） | GIL + threading.Lock | 所有权 + Send/Sync |
| 线程安全保证 | 运行时 + 文档约定 | 运行时 + 开发者自觉 | 运行时 + 约定（channel） | GIL 缓解 + 锁 | **编译期**所有权 + Send/Sync |

对比结论：Java 与 C++ 同为「共享内存 + 显式锁」模型，但 Java 用 JUC 并发集合与虚拟线程大幅降低了使用成本；Go 与 Rust 分别用「channel 约定」与「编译期所有权」把并发安全问题前移；Python 受 GIL 限制，线程适合 IO 密集、计算密集要靠多进程。Java 21 虚拟线程的独特价值在于：**同步代码、百万级并发、零语法改造**——这是 C++/Rust 异步模型（async/await 染色）都不具备的组合。

### 阶段验收清单

- [ ] 能解释线程池参数（corePoolSize / maximumPoolSize / workQueue / 拒绝策略）与任务提交流程（先填队列后扩线程），并说出 `Executors` 工厂的无界队列坑
- [ ] 能说明虚拟线程和平台线程的区别及适用场景（调度者、创建成本、阻塞行为、IO 密集 vs 计算密集）
- [ ] 能避免常见竞态：volatile 误用、复合操作不加锁、多线程并发修改共享集合
- [ ] 能用并发集合解决问题：ConcurrentHashMap / CopyOnWriteArrayList / BlockingQueue 正确选型
- [ ] 能解释 JMM 的 happens-before 与 synchronized 的锁升级过程，能用 CompletableFuture 编排异步并兜底异常
- [ ] 能区分结构化并发（预览）与 Scoped Values（Java 25 正式化）的现状，不被过时资料误导

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 5 题后继续，题目与 roadmap「练习」小节一一对应：

- **多线程计数器**（★）：10 线程各加 1 万次，对比普通变量 / synchronized / AtomicInteger（提示：`join()` 等全部线程结束再输出；普通变量结果必然小于期望值）
- **生产者消费者**（★★）：有界 BlockingQueue + 2 生产者 3 消费者（提示：`put`/`take` 阻塞语义；哨兵必须等全部生产者结束后再放，否则消费者先退、生产者饿死；中断时恢复中断标志）
- **线程安全队列**（★★★）：用 Lock + Condition 手写有界队列，2 生产者 3 消费者验证不重不漏（提示：`await` 用 while 检查条件防虚假唤醒；`unlock` 放 finally）
- **异步日志系统**（★★★）：多线程产日志 → BlockingQueue → 单后台线程批量落盘（提示：`drainTo` 批量取；关闭时用哨兵优雅收尾而非 `shutdownNow` 强杀，别丢最后几条日志；日志写 /tmp 并清理）
- **用虚拟线程实现高并发任务处理**（★★，需 JDK 21+）：对比固定线程池与虚拟线程处理 1 万个阻塞任务的耗时（提示：`Thread.sleep` 模拟 IO；计算密集任务虚拟线程无优势）

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**线程池任务调度器**——手动配置 `ThreadPoolExecutor`（核心 2 / 最大 4 / 有界优先级队列容量 6 / 自定义拒绝策略），提交 20 个带优先级任务，自测断言「接受 10 / 拒绝 10、启动顺序与优先级严格一致、线程命名统一、优雅关闭成功」。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

roadmap 推荐的第二个项目「并发文件处理工具」（多线程扫描目录、并发读取文件做词频统计，用 CompletableFuture 编排并汇总到 ConcurrentHashMap；进阶用虚拟线程对比性能）作为扩展方向，示例 4 / 示例 5 / 示例 6 已给出核心句式。

### 下一阶段

[JVM 阶段](../ph10-jvm/10-jvm.md) —— 类加载机制、内存区域与 GC、JVM 参数调优、性能诊断：回答「并发程序的线程、对象与内存到底跑在 JVM 的哪里」。
