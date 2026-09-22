# ph09 多线程与并发示例

> 每个示例是主文档「6. 代码示例」对应示例的完整可运行版，自带自检断言（失败抛 `AssertionError`）。验证环境：ex01~ex05 用 OpenJDK 17.0.18（`javac -version` → 17.0.18）；ex06 需 JDK 21+，本环境用 OpenJDK 25.0.2 验证。

## 类名与文件名说明

为保持 `ex0X-` 编号命名，文件名（`ex01-counter-demo.java`）与类名（`CounterDemo`）不一致。因此这些示例**刻意不声明为 `public` 类**（Java 规定 public 类必须与文件名同名，非 public 类无此限制）。编译时用**文件名**，运行时用**类名**：

```bash
# 1. 编译
javac ex01-counter-demo.java
# 2. 运行（注意是类名不是文件名）
java CounterDemo
```

## 示例列表

| 文件 | 类名 | 说明 | 编译 | 运行 |
|------|------|------|------|------|
| ex01-counter-demo.java | CounterDemo | 多线程计数器：10 线程各加 1 万次，对比普通变量（竞态）/ synchronized / AtomicInteger | `javac ex01-counter-demo.java` | `java CounterDemo` |
| ex02-thread-pool-demo.java | ThreadPoolDemo | 线程池提交流程：先填队列后扩线程、AbortPolicy 拒绝、CallerRunsPolicy 背压、优雅关闭 | `javac ex02-thread-pool-demo.java` | `java ThreadPoolDemo` |
| ex03-producer-consumer.java | ProducerConsumer | 生产者消费者：容量 5 有界队列 + 慢消费者，观察 put 队满阻塞；10 件消费不重不漏 | `javac ex03-producer-consumer.java` | `java ProducerConsumer` |
| ex04-completable-future-demo.java | CompletableFutureDemo | CompletableFuture 异步编排：thenCombine 汇合 + thenApply 转换 + exceptionally 兜底 + 异常暴露时机对照 | `javac ex04-completable-future-demo.java` | `java CompletableFutureDemo` |
| ex05-concurrent-collections.java | ConcurrentCollectionsDemo | 并发集合：ConcurrentHashMap.merge 原子累加、computeIfAbsent 单次初始化、CopyOnWriteArrayList 追加不丢不重 | `javac ex05-concurrent-collections.java` | `java ConcurrentCollectionsDemo` |
| ex06-virtual-thread-demo.java | VirtualThreadDemo | 虚拟线程 vs 平台线程：1 万个阻塞 10ms 任务耗时对比（**需 JDK 21+**） | `javac ex06-virtual-thread-demo.java` | `java VirtualThreadDemo` |

## 验证状态

- ex01 ~ ex05：已在本环境用 OpenJDK 17.0.18 编译运行验证（零错误，自检断言全部通过）。
- ex06：**已验证：OpenJDK 25.0.2**（Homebrew openjdk@25）——虚拟线程 API 自 Java 21 正式化（`newVirtualThreadPerTaskExecutor` 为 21+；`ExecutorService` 实现 `AutoCloseable` 为 19+），OpenJDK 17 无法编译本文件，故在 JDK 25 上验证；实测平台池约 590ms、虚拟线程约 42ms（具体毫秒数随机器波动），但「虚拟线程远快于固定线程池」与完成数 10000/10000 稳定可复现。

两点说明：

- ex03 运行约 1~2 秒（消费者故意慢消费，用于演示 put 阻塞）；ex04 含一个「链上不兜底异常」的对照段，其 `join()` 抛 `CompletionException` 是预期行为。
- 所有示例的类都不是 `public`——这是 kebab-case 文件名与 Java「public 类必须与文件名同名」约束协调的结果（详见上文说明），`java` 运行不要求主类为 public。
