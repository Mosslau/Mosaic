# Java 高级 Java 阶段

> 面向「能读懂框架、能定位疑难、能设计大型模块」：本阶段承接 ph09/ph10 的并发与 JVM 基础，把「会用」推入「懂机制」——JMM 讲清可见性与有序性的来源、AQS 讲清 java.util.concurrent 的地基、线程池与 CHM 落到源码执行路径，ClassLoader/反射/代理/SPI 揭穿框架的能力来源，Netty 展示高并发网络编程的工程答案，最后用设计模式索引与 DDD 把知识收回「复杂业务怎么建模」。

## 1. 概述

本阶段是 Java 学习路线从「**能干活**」到「**能攻坚**」的一站。roadmap 第 20 节目标：**理解 Java 底层和大型工程设计能力**。前面 19 个阶段铺完了语法（ph01~ph08）、并发与 JVM 的「入门级」（ph09/ph10）、工程生态（ph11~ph19），本阶段的任务是给这些已会用的东西补上「为什么」与「怎么造」：

- ph09 讲过 `synchronized`/`volatile` 怎么用、`ReentrantLock` 怎么用、线程池参数怎么配——本阶段补 **JMM 为什么需要这两件事、AQS 用什么结构实现锁、ThreadPoolExecutor 的执行链逐行怎么走**；
- ph10 讲过运行时数据区、GC Roots、Serial→G1→ZGC 的名字与用途、`-Xlog:gc` 怎么开——本阶段补 **GC 怎么选（决策树）、Region/humongous 怎么读、GC 日志与堆内外指标曲线怎么解读**，并把 ph19 预告兑现；
- ph15 用过 Spring 的 IOC/代理/事务——本阶段补 **容器与 AOP 脚下的反射/类加载器/动态代理/SPI 机制**（ph15 是消费方视角，这里是制造方视角）；
- 网络、消息、缓存、部署都做过了（ph14~ph19），最后用 **Netty、设计模式、DDD** 把「高并发网络怎么写」「框架里的模式怎么认」「大业务怎么建模」收口。

| 核心维度 | 覆盖内容 |
|----------|---------|
| JVM 深入 | GC 选型决策（G1 的 Region / ZGC 的染色指针与读屏障）、调优参数族、GC 日志解读、堆内外指标曲线、CDS/Native Image 部署形态（兑现 ph19 预告） |
| JMM | 可见性/有序性来源（缓存一致性、重排序、内存屏障）、happens-before、volatile 精确语义、DCL |
| AQS | state + CLH 队列 + 模板方法；独占/共享；ReentrantLock/Semaphore/CountDownLatch 的统一地基；LockSupport |
| 线程池原理 | ThreadPoolExecutor 七参数、execute 四段路径、ctl 状态机、Worker 复用、拒绝策略 |
| 集合源码 | HashMap（JDK7→8 演进/树化/扩容）、ConcurrentHashMap（锁分段→CAS+synchronized、并发计数、扩容协助） |
| 类加载与反射 | ClassLoader 源码链、双亲委派及打破场景、Reflection 边界、JDK 动态代理 vs CGLIB、SPI 服务发现 |
| 高性能网络 | Reactor 线程模型、EventLoop、pipeline、Netty 零拷贝概念；JDK NIO 痛点对照 |
| 模式与建模 | 设计模式在 JDK/JUC 的应用索引；DDD（限界上下文/聚合/领域服务）与大型业务建模 |

这个阶段只涉及 **JVM/JMM/并发底层机制与大型工程的通用模式与建模方法**，**不涉及数据平台业务的整合落地（数据接入协议、告警规则引擎、任务发布平台、作业历史查询如何用这些机制实现）** — 那是 [ph21 数据平台 / 数据中心后端方向 Java 阶段](../ph21-data-platform/21-data-platform.md)，本阶段只在 DDD 与场景两处以「数据平台将用到」点题不展开。**ph10 已讲过的 JVM 基础入门（运行时数据区五件套、GC Roots、类加载五阶段流程、jps/jstack/jmap/jstat 的命令用法）不重复展开，本阶段只在其之上做机制深水与工程化增量**；**ph09 已讲过的并发入门（synchronized/volatile 基本用法、ReentrantLock 用法、线程池七参数怎么配、虚拟线程怎么用）同样不重复，只深入其源码与模型**。设计模式部分**不重讲 GoF 每种模式的语法示例**（那些收进模式索引一张表，重点是「JDK 里长什么样」），DDD **不涉及具体行业业务规则**。

## 2. 来源与演变

**本阶段几乎所有主题都是「解决问题演化出来的工程遗产」**——没有一项是教科书拍脑袋设计出来的：JMM 是对上世纪多核乱序执行事故的制度化回应，AQS 是 Doug Lea 为统一并发原语写的抽象，Netty 是对 JDK NIO 难用与缺陷的工程反叛，DDD 是 Eric Evans 对「复杂业务被贫血模型拖垮」的诊疗方案。

- **JVM 规范与垃圾回收器**：1996 年 JDK 1.0 只有串行复制式 GC（新生代 stop-the-world），吞吐靠硬件翻倍。此后每个收集器都是对上一代痛点的定点打击：2002 年 JDK 1.4.1 引入 **Parallel Scavenge**（吞吐优先，多线程并行收集）；2004 年 **CMS** 首次做到老年代并发回收（低延迟，但碎片化与 CPU 抢占是痼疾，JDK 14 移除）；2012 年 **G1** 随 JDK 7u4 可用，2017 年 JDK 9 设为默认（把堆切成 Region，用「可预测停顿」替代 CMS 的近似并发标记）；2018 年 JDK 11 引入 **ZGC**（染色指针 + 读屏障，停顿 <1ms 且与堆大小无关），2020 年 JDK 14 的 ZGC、2023 年 JDK 21 的 **Generational ZGC** 分代化进一步降开销。JVM 内存与 GC 的白皮书级定义在《The Java Virtual Machine Specification》；GC 行为的可观测靠 `-Xlog`（JDK 9 起统一日志框架）。
- **JMM 与 JSR-133**：1995~2004 年 Java 的内存语义长期由「平台直觉」与各 JVM 的实现差异主宰，多核 x86 普及后可见性问题爆发。2004 年 **JSR-133**（Java Memory Model）随 Java 5 落地，首次给 Java 一个**跨平台的、可证明的形式化内存模型**（happens-before 偏序 + 顺序一致性程序子集），2014 年 Java 8 的 JLS §17.4 仍是其措辞的延续。
- **AQS**：2004 年 Java 5 的 `java.util.concurrent`（JSR-166，Doug Lea 主导）把散落的自旋锁/监视器实现统一为 **AbstractQueuedSynchronizer**——一个用 int state + CLH 变体队列表达的同步器框架。ReentrantLock/Semaphore/CountDownLatch/ReentrantReadWriteLock/FutureTask/ThreadPoolExecutor 的 Worker 全是它的子类，**看懂 AQS = 看懂半本 JUC**。
- **Netty**：JDK 1.4 引入 NIO（2002）后，直接在 Selector 上写业务被公认为「反人类」（ByteBuffer 状态机、粘包半包、跨平台空轮询 bug）。2012 年起 **Netty**（JBoss 主导、Trustin Lee 早期贡献）成为事实标准：用「Channel + pipeline + codec」把 NIO 的字节细节沉淀为可插拔组件，Redis/ES/Kafka/Dubbo 的内部网络层与 Spring WebFlux 的底层都在用它。
- **DDD**：2003 年 Eric Evans《领域驱动设计》提出**让领域模型成为软件核心、让业务语言进入代码**（通用语言/限界上下文/聚合/仓储），反对「表驱动 + 贫血对象」的 CRUD 式大型系统；2009 年后被微服务运动重新拾起——因为**微服务边界本质上就是限界上下文的物理化**（ph16 的拆服务到这里才拿到「按什么拆」的理论依据）。

| 里程碑 | 年份 | 主要变化 |
|--------|------|---------|
| JSR-133（Java 5） | 2004 | Java 第一个形式化内存模型：happens-before、volatile 完整语义 |
| JUC（Java 5） | 2004 | AQS + 并发集合 + 线程池一次性进入 JDK |
| JDK 7u4 G1 可用 | 2012 | Region 化收集器；JDK 9（2017）设为默认 |
| JDK 11 ZGC | 2018 | 染色指针 + 读屏障，亚毫秒停顿与堆大小解耦 |
| JDK 9 统一日志 | 2017 | `-Xlog` 取代 `-XX:+PrintGCDetails` 等旧参数 |
| JDK 17（本阶段基线） | 2021 | G1 为默认；CDS/AppCDS 可用；强封装 JDK 内部（反射受限） |
| 分代 ZGC | 2023 | ZGC 分代化（JDK 21），为 Web 服务级负载铺路 |

> 现实基线：**G1 是 JDK 17 默认收集器**，绝大多数服务「开了默认就能跑」，GC 选型只在大堆 / 超低延迟 / 高吞吐三选一场景才动手；本阶段全部 JVM 演示在 G1 + 48MB 小堆上完成。

本文示例以 **OpenJDK 17.0.18（Homebrew，/opt/homebrew/opt/openjdk@17）** 为基线（选择理由：与 ph14~ph19 全链同基线，G1 默认收集器、JUC 源码即 17 形态、`-Xlog` 语法成熟；ZGC 在 17 已可用但本文档不作主要演示对象）。**验证纪律**：① 纯 Java 可实测部分（JMM/AQS/手写线程池/CHM/ClassLoader/反射代理 SPI/GC 日志采集）已在本机 **javac/java 17.0.18 实测**并标注「已验证」；② Netty 示例因本机无 mvn，采用从 Maven Central 手动拉取 netty 4.1.137.Final 模块 jar 后 javac/java 实测通过，同样标注「已验证」并附 jar 获取命令；③ 涉及 Spring/Maven 构建的「生产形态」表述只给结论与命令，标注「未在本环境验证」。**本阶段的语法面（JMM 语义、AQS API）是 Java 里最稳定的部分**——自 Java 5 起十多年未变，17 与 21 的写法完全一致。

## 3. 语法与参数

### 3.1 JVM 深入：GC 怎么选、Region 怎么读、指标曲线怎么解读（兑现 ph19 预告）

ph10 已经给了 JVM 全景入门，这里**只讲 ph10 没讲的三个深水问题**，它们正是 ph19 预告里埋的钩子：ph19 只回答了「容器配额 75% 给 JVM」（`-XX:MaxRAMPercentage`），本阶段回答**「这 75% 够不够、GC 选谁、从日志与曲线怎么判断」**。

**① 现代收集器怎么工作：G1 的 Region 网格与 ZGC 的染色指针**

G1 与老一代收集器的根本差异是**堆的物理组织**：不再分连续的新生代/老年代，而是把堆切成约 2048 个等尺寸 **Region**（如 48MB 堆 = 48 个 1MB Region），eden/survivor/old 都是 Region 的**逻辑集合**，可动态伸缩：

```text
G1 堆 = Region 网格（本例 ex07 实测：-Xms48m 时 region size 1024K）
┌────┬────┬────┬────┬────┬────┐
│ E  │ E  │ S  │ O  │ H  │ E  │    E=eden  S=survivor  O=old
│ E  │ E  │ O  │ O  │ H  │ E  │    H=humongous（> region 一半的大对象专用区）
├────┼────┼────┼────┼────┼────┤
│ O  │ O  │ E  │ E  │ E  │ O  │    停顿可控的根源：每次 GC 只收一部分 Region
└────┴────┴────┴────┴────┴────┘
```

- **为什么 G1 停顿可预测**：Young GC 只收集 eden+suvivor Region（少）；old 回收走「并发标记 → 混合回收（Mixed GC）」——每轮只回收**收益比最高的一批** old Region，用 `-XX:G1MixedGCCountTarget` 控制轮次，把单次停顿压进目标（默认 200ms）。GC 日志里 `Pause Young (Mixed)` 才是真的在收 old。
- **为什么大对象值得单独说**：超过 Region 一半的对象（如 1MB 的 byte[] 超过 512KB 阈值）进 **humongous Region**，直接整块分配、不参与复制。ex07 的演示程序 `new byte[1MB]` 就是 humongous——日志里出现 `(G1 Humongous Allocation)` 原因。频繁分配 humongous 会让大对象区碎片化，这是「日志里 humongous 次数多」要警惕的原因。
- **ZGC 的思路完全不同**：把指针本身变成状态载体——**染色指针**（64 位指针中拿几位存 Marked/Remapped/Finalizable 状态）+ **读屏障**（每次读引用时顺带检查染色位），让标记/整理能并发进行、STW 压缩到 <1ms 且**不随堆变大**。代价是 CPU 开销（读屏障）与内存占用（ZGC 需要额外地址空间）。

**② GC 选型决策表（不看名字，看三选一）**

| 应用画像 | 选谁 | 一句话理由 |
|---------|------|-----------|
| 默认无特殊诉求 | **G1（JDK 9+ 默认）** | 吞吐与延迟平衡，参数零配置也能跑 |
| 批处理/离线/重计算，能容忍几百 ms 停顿 | **Parallel**（`-XX:+UseParallelGC`） | 吞吐最高，少做并发簿记 |
| 大堆（几十 GB）+ 要求 <10ms 级停顿（金融/在线服务） | **ZGC**（17 支持，21 分代化） | 停顿与堆大小解耦 |
| 老服务/极小堆嵌入式 | Serial | 单核或调试时最简单 |

**选型不是抄参数**：先定「可接受的最大停顿 P99、吞吐、堆大小」三个数字，再对照上表选一个，然后用 GC 日志验证，而不是把网上参数抄一遍——**GC 调优是目标驱动的验证循环，不是参数堆砌**（这正是 ph19「容器里只给 MaxRAMPercentage」就能跑的原因：默认 G1 已经够好）。

**③ 诊断：堆内外指标曲线的两条读法**

ph10 讲了工具的**命令**（jstat/jstack/jmap），本阶段补「看到曲线怎么下结论」。GC 日志汇总行是最粗的曲线：

```text
[0.108s][info][gc] GC(0) Pause Young (Concurrent Start) (G1 Humongous Allocation) 21M->21M(48M) 0.588ms
  ↑耗时点   ↑GC 编号      ↑类型（是否 STW）        ↑原因        ↑回收前后堆占用→曲线数据  ↑停顿
```

- **堆占用曲线**（`jstat -gc <pid> 1000` 的 OU/EU 列，或日志中 `X M->Y M(ZM)`）：看**趋势**而非单点——回收后水位缓慢爬升趋近 Z（堆上限），说明存活对象在涨（泄漏或容量不够）；`(full N)` 编号持续增长 = 老年代回收不掉，是**最刺眼的告警**。
- **停顿曲线**（GC 日志每行尾的毫秒数）：健康时平稳小抖动；突增或持续走高，优先查**外部因素**（GC 期间锁竞争/系统换页）而不是先调收集器。
- **堆内外怎么一起看**（兑现 ph19 的 MaxRAMPercentage 钩子）：容器给了 100% 配额、JVM 只拿 75%——剩下 25% 是 Metaspace + JIT 代码缓存 + 线程栈 + DirectBuffer（ph19 4.4）。**判断「25% 够不够」要看堆外指标**：`-Xlog:gc+metaspace` 看元空间、`jcmd VM.native_memory` 看 Native、`jstat -gc` 的 M 列看 Metaspace 占用——堆外涨到把容器配额顶穿就会 OOMKilled，而堆日志里完全看不出来。

**④ 部署形态的深水：CDS 与 Native Image（ph19 预告「Native Image/CDS 部署形态」兑现）**

ph19 讲到 Java 容器镜像大的代价来自 JVM 运行时本身。两个正在缩小代价的方向，**本阶段只讲机制与适用边界，不做生产配置**：

- **CDS/AppCDS（Class Data Sharing）**：把启动时反复加载的类的**归档形态**（已解析的 class + 元数据 + 部分 AOT 代码）存成共享归档文件，下次启动直接映射，减少类加载与元数据初始化——典型收益是启动提速 20%~40%、内存共享。JDK 17 里：`java -Xshare:dump` 建默认归档；AppCDS 用 `-XX:ArchiveClassesAtExit=app.jsa` 记录应用类再 `-XX:SharedArchiveFile=app.jsa` 复用来加载。它**不动运行时语义**，只是「把加载结果缓存下来」。
- **Native Image（GraalVM）**：把字节码 AOT 编译成原生可执行文件——启动毫秒级、无 JIT/GC 预热成本、镜像可小一个数量级，代价是**必须在构建期关闭动态性**：反射、动态代理、SPI 这类「运行时才发现类」的能力要预先用配置清单（reachability metadata）声明，否则运行即报 `ClassNotFoundException`。这与 3.8 反射/代理/SPI 的能力**正面冲突**——所以 Native Image 适合启动/内存敏感的网关与函数计算，不适合重度反射的框架型应用。

> 本阶段只要求「知道 CDS/Native Image 解决什么、代价是什么」，具体开启与调优命令属工程交付时按需实践，不再展开。

### 3.2 JMM：可见性、有序性与 happens-before 的制度化

ph09/ph10 都演示过可见性现象（ph10 4.6 做过实验），本阶段讲**「为什么会有这些现象、JMM 怎么制度化地约束它」**。

**① 三个问题的来源**

| JMM 要回答的 | 现象来源 | 一句话本质 |
|-------------|---------|-----------|
| 可见性：写者改了，读者看不到 | CPU 多级缓存 + 编译器寄存器化 | 每个线程对共享变量的「视图」可以不同步 |
| 有序性：代码顺序 ≠ 执行顺序 | 编译器重排 + CPU 乱序执行（store buffer/流水线） | 只要单线程语义不变，重排是合法的 |
| 原子性：复合操作被打断 | 读改写不是一条指令 | 需同步原语或 CAS |

**关键认知：这些现象在单线程里完全无害**（单线程语义由编译器保证），只在多线程共享数据时成为 bug。JMM 的做法不是「禁止重排」（那会杀死性能），而是**定义一组规则：哪些重排被禁止、什么时候一个写必须对另一个线程可见**——这就是 happens-before。

**② happens-before 规则（JLS §17.4.5，Java 5 起没变过）**

| 规则 | 内容 | 直觉 |
|------|------|------|
| 程序顺序 | 线程内，前面的语句 hb 后面的 | 单线程是安全的 |
| 监视器锁 | `unlock` hb 后续对同一锁的 `lock` | 拿锁 = 看见临界区写的全部 |
| volatile | `volatile` 写 hb 后续对该变量的 `volatile` 读 | 写发布、读订阅 |
| 传递性 | a hb b 且 b hb c → a hb c | 链式推导 |
| 线程启动/终止 | `start()` hb 该线程一切动作；线程一切动作 hb `join()` 返回 | 起线程 / 收线程是天然边界 |

**happens-before 是「保证」不是「可能」**：写者把普通字段赋值完再写 volatile 标志，读者读到标志 = 一定读到全部普通字段——ex01 的 Phase 2 用 `shared=42; vStop=true` 实证了这一点（读到 `vStop` 必然读到 `42`）。同理 synchronized 的 `unlock→lock`（ex01 Phase 3）与 `start/join`。

**③ volatile 的精确语义与 DCL**

volatile 语义 = **可见性 + 有序性（禁止重排），不含原子性**（`volatile int i; i++` 仍非原子）。它是 JMM 里的「半同步」：读 volatile 相当于 acquire，写 volatile 相当于 release（读者读到最新写的值），但不建立「多步复合操作的互斥」。

双检锁（DCL）为什么**必须** volatile——这是「有序性」最经典的考题：

```java
// examples/ex01-jmm-visibility 思路同源：正确版 DCL 单例（省略部分仅为聚焦 volatile 有序性）
class Holder {
    private static volatile Holder instance;   // ① 若无 volatile：见下
    static Holder get() {
        if (instance == null) {                // ② 第一次检查（无锁，快路径）
            synchronized (Holder.class) {
                if (instance == null) {        // ③ 二次检查（有锁）
                    instance = new Holder();   // ④ 分配+构造+发布
                }
            }
        }
        return instance;
    }
}
```

第 ④ 步在无 volatile 时可能被重排成「先给引用赋值、后跑构造器」：另一个线程在 ② 处看到非 null 的 instance，**直接返回一个构造了一半的对象**。volatile 禁止 `instance = new Holder()` 的写与其后（其实是写内部的）重排，保证发布时构造已完成。**无 volatile 的 DCL 是经典错误示例**，任何一本并发书都不会放过它——这正是「有序性不是玄学，是可论证的规则」的注脚。

### 3.3 AQS：java.util.concurrent 的公共地基

ph09 用过 `ReentrantLock/Semaphore/CountDownLatch` 的 API，本阶段回答「它们为什么能共享同一套实现」。**AQS = 一个 int `state` + 一个 CLH 变体等待队列 + 一组留给子类的模板方法**：

```text
AQS 的结构（以独占锁为例）
state（volatile int）         ← 子类语义：0=空闲 / 1=持有 / n=重入n次 / 许可数(信号量)
   │
   ├─ 获取：compareAndSetState(0,1) 成功 → 直接占有（非公平锁的插队点）
   │
   └─ 失败 → 封装成 Node 挂到 CLH 队列尾 → LockSupport.park 阻塞
                ▲                                    │
                └── 前驱释放时 unpark 后继 ◀──────────┘
```

- **模板方法**：`acquire`/`release` 是 AQS 写好的骨架（排队、park、唤醒、中断处理），子类只需实现 `tryAcquire`/`tryRelease`（独占）或 `tryAcquireShared`/`tryReleaseShared`（共享）——**状态怎么变是子类的事，排队与阻塞是 AQS 的事**。
- **ReentrantLock 的 tryAcquire**：`state==0` 则 CAS 抢；`state!=0` 且当前线程是 owner 则 `state+n`（重入）——ex02 用 30 行把这一整套实现了一遍并实测了重入与互斥。**公平锁与非公平锁只差一行**：非公平在入队前先 CAS 抢一次（后来的线程可以插队），公平锁直接看队列有没有排队的（`hasQueuedPredecessors`）。
- **共享模式**：`CountDownLatch` 把 `state` 当倒数计数，countDown = `releaseShared(1)`，await = `acquireSharedInterruptibly`（state 到 0 时所有等待线程一起被唤醒）；`Semaphore` 的 permits 也是 state。**独占/共享两种模式 + 一个 state，就覆盖了 ReentrantLock / Semaphore / CountDownLatch / ReentrantReadWriteLock 全部语义**。
- **Condition**：`await/signal` 不是 AQS 队列而是挂在同一个 Node 结构上的**条件队列**——`await` 释放锁并把线程移入条件队列 park，`signal` 把条件队列的头移回同步队列等锁。这也是为什么 `Condition.await` 必须持锁调用。

**AQS 在 JDK 里的完整族谱**（这就是「AQS 是半本 JUC」的实锤）：

| 组件 | 模式 | state 语义 |
|------|------|-----------|
| ReentrantLock | 独占 | 重入次数 |
| ReentrantReadWriteLock | 独占+共享 | 高 16 位读锁数、低 16 位写锁重入 |
| Semaphore | 共享 | 剩余许可 |
| CountDownLatch | 共享 | 剩余计数 |
| ThreadPoolExecutor.Worker | 独占 | 0/1（标记 worker 是否可被中断） |
| FutureTask | 共享 | 任务状态（NEW→COMPLETING→…） |

> 本阶段只需要「用 AQS 写一个锁」来理解它的结构（ex02 已验证）；**ReentrantReadWriteLock 的写锁降级、StampedLock 的乐观读属于读写锁深入**，如需展开属后续专题，此处不展开。

### 3.4 线程池原理：ThreadPoolExecutor 的执行链

ph09 讲了七参数「怎么配」，本阶段回答「execute 一个任务后，内部到底发生了什么」。**完整流程是四段式**（与 3.6 的 CHM 一样，是「先判断后动作 + CAS 兜底」的并发套路）：

```text
execute(task)
  ① workerCount < corePoolSize ?  → addWorker(task, true)：新建核心 Worker，task 作 firstTask 直接跑
  ② workQueue.offer(task) 成功    → 入队即返回（等某个 Worker 取走）；入队后要二次检查
  ③ workerCount < maximumPoolSize → addWorker(task, false)：新建非核心 Worker（带 keepAlive）
  ④ 都失败                        → 拒绝策略 reject(task)
```

- **为什么是「先加核心、再入队、再补非核心」**：核心线程是常驻的（队空也不退），非核心是临时劳动力（`keepAliveTime` 空闲即退），队列是缓冲带。**队列无界（`LinkedBlockingQueue`）时 ③ 永不执行**——这就是 `newFixedThreadPool` 不会「扩到 max」的原因；**队列无界 + 提交速度 > 消费速度 = 内存被任务堆满**，这是「newFixedThreadPool 默认无限队列」陷阱的机制根源。
- **状态机：一个 int 装两个数**。ThreadPoolExecutor 用一个 `AtomicInteger ctl` 的**高 3 位存 runState**（RUNNING/SHUTDOWN/STOP/TIDYING/TERMINATED）、**低 29 位存 workerCount**——一个 CAS 就能同时更新状态与计数，避免「改了状态忘了数工人」的竞态。`workerCountOf/runStateOf` 只是掩码位运算。
- **Worker = 一个「从队列取任务」的循环线程**：每个 Worker 包一个 Thread，run 里 `while ((task = getTask()) != null) task.run()`——**线程复用的本质是任务排队，不是线程里套线程**。`getTask()` 按 workerCount 是否 > core 决定 `take()`（阻塞）还是 `poll(keepAlive)`（超时）。
- **Worker 为什么继承 AQS**：Worker 自己实现了一个**不可重入的独占锁**，锁位标记「worker 是否空闲」，让 `shutdown` 能安全地只中断空闲 Worker（`interruptIdleWorkers`）而不误伤正在跑任务的。**这与 3.3 AQS 形成闭环**——线程池内部也在用 AQS。
- **拒绝策略是策略模式的现场**（也呼应 3.10）：`AbortPolicy`（默认，抛异常）、`CallerRunsPolicy`（谁提交谁跑——天然限流）、`DiscardPolicy`/`DiscardOldestPolicy`。**`CallerRunsPolicy` 是最常用的兜底**：任务退回提交线程执行，提交线程忙着跑任务就自然放慢了提交速率。
- **重要扩展钩子**：`beforeExecute/afterExecute/terminated` 让「线程池埋点监控」「任务级日志」「优雅停机后清理」不污染业务代码——Spring 的异步与监控很多基于此。

examples/ex03 与 exercises/sol-02 分别手写了 execute 主链与 `submit`/Future，对照本节的四段式读代码，比背源码更有效。**手写池与 TPE 的差距清单**（诚实版）：没有 ctl 状态机、没有双检 addWorker（我们的 addWorker 用 CAS 兜底但少了 workerCount 越界与状态退化的联合判断）、`shutdown` 只中断不区分 SHUTDOWN/STOP——这些正是读 TPE 源码时值得逐行对照的点。

### 3.5 HashMap 深水：JDK7→8 的结构演进与并发不安全

ph04 用过 HashMap，这里进源码级。**HashMap = 数组 + 链表（+ 红黑树）**：`put` 先 `hash(key)` 再 `(n-1) & hash` 定位桶，冲突挂链表。三个源码级问题：

**① 为什么容量是 2 的幂、默认 0.75、树化阈值 8**

| 设计 | 值 | 为什么 |
|------|-----|--------|
| 容量是 2 的幂 | `16`，扩容翻倍 | `(n-1) & hash` 代替取模（位运算快），且扩容后每个元素只可能在「原位」或「原位+旧容量」 |
| 扰动函数 | JDK8：`(h ^ (h >>> 16))` | 让高位参与定位，减少低 16 位相同导致的碰撞 |
| 负载因子 | `0.75` | 空间/时间折中：太高（如 1）链表变长、太低频繁扩容 |
| 树化阈值 | 链表长 **8** 转红黑树 | 负载 0.75 下，泊松分布算得桶内 8 个元素的概率约千万分之六——**8 是「几乎不会自然达到」的警戒线**，达到说明 hash 分布出了问题（如 hashCode 劣质） |
| 退化阈值 | 红黑树节点 **6** 转回链表 | 留 2 的余量，避免在 7/8 之间抖动转换 |

**② JDK7 → JDK8 到底改了哪些结构问题**

| 维度 | JDK 7 | JDK 8 | 动机 |
|------|-------|-------|------|
| 底层 | 数组 + 链表 | 数组 + 链表/**红黑树** | 防 hashCode 攻击（构造大量同桶 key 拖垮 get 到 O(n)） |
| 扩容重排 | 每个元素 rehash 重新定位 | 分**高低位两组**（`(e.hash & oldCap) == 0` 留原位，否则 +oldCap） | 扩容从「重算一遍」变「分组搬移」，顺便保证顺序（配合尾插） |
| 冲突插入 | **头插**（新节点插链头） | **尾插**（插链尾） | 头插 + 并发扩容会形成环（`transfer` 时 next 反转），死循环经典 bug 的根源 |
| 并发 | 线程不安全 | 线程不安全（丢更新/覆写） | **JDK8 修了死循环但从不承诺线程安全**——并发场景用 CHM（3.6） |

**③ 扩容（resize）的一次完整旅程**：`put` 发现 `size > threshold`（capacity×0.75）→ 新表翻倍 → 旧表每个桶：单节点直接迁移；链表按 `hash & oldCap` 拆成 lo/hi 两条链分别放 `原下标` 与 `原下标+oldCap`；红黑树拆完长度 ≤6 则退化为链表。**扩容是 O(桶数) 的全表操作，频繁扩容 = put 频繁抖动**，所以预知容量时用带容量的构造器（`new HashMap<>(预估/0.75f)`）。

> HashMap 的并发缺陷在 examples/ex04 用「裸 HashMap 并发自增丢 40 万次更新」做了对照实证（文件头注明是故意错误对照）。**它不安全是设计使然，不是 bug 待修**——JDK 的作者把这个位置留给 ConcurrentHashMap。

### 3.6 ConcurrentHashMap：从锁分段到 CAS + synchronized

ph09 讲过 CHM 的用法（并发读写、遍历不抛 CME），这里进**并发策略的源码演化**。CHM 是 JDK 并发集合里演进最激进的类，两代结构差异本质上是「**锁的粒度从粗到细、从悲观的整段锁到乐观的桶级 CAS**」：

**① JDK7：锁分段（Segment）**

```text
JDK7 CHM：一个 ConcurrentHashMap = 16 个 Segment（默认并发度）
┌────────┬────────┬────────┬────────┐
│Seg[0]  │Seg[1]  │ …      │Seg[15] │  每个 Segment extends ReentrantLock
│ (HashEntry[])         (HashEntry[])
│ put: 先定位段，再锁段（段内 put 与 JDK7 HashMap 一致）
│ get: 不需要锁（HashEntry.value 是 volatile）
│ size(): 先无锁试两次，不一致则锁全部段求和
└────────┴────────┴────────┴────────┘
```

并发度 = 段数（16），不同 key 落到不同段可并行写——**但一旦 key 分布集中，16 把锁只剩 1 把在干活**。

**② JDK8：CAS 头插 + synchronized 锁桶**

```java
// JDK8 putVal 的核心路径（源码语义，非原文；示例请对照 JDK 源码）
final V putVal(K key, V value, boolean onlyIfAbsent) {
    // for (;;) {
    // ① 桶为空 → CAS 把 Node 放进去（乐观：无锁成功率高）
    // ② 桶非空 → synchronized(桶头 Node) { 链/树里找 key：更新或尾插 }
    // ③ 链长 ≥8 → treeifyBin 转红黑树（与 HashMap 同步的树化）
    // ④ 扩容中 → helpTransfer 协助扩容（3 节见 4.3）
}
```

- **为什么换成 synchronized**：JDK6 以后 synchronized 经过锁升级（偏向→轻量→重量，ph09 4.2）在**低竞争下开销小于显式锁**；桶级锁粒度远细于段级（一个桶的冲突只锁一个桶），JDK 团队甚至在源码注释里承认「synchronized 在这个场景更合适」。
- **get 全程无锁**：`Node.val` 与 `Node.next` 都是 volatile，配合 `table` 的 volatile 引用——读者要么读到已发布的旧链表、要么读到正在写的新链表，**弱一致性但永不看到半写状态**（JMM 的 volatile 语义在此是「无锁读安全」的合法性来源，衔接 3.2）。
- **并发计数 size()**：JDK7 是「锁全部段求和」，JDK8 是 `baseCount + CounterCell[]`——高并发写时把计数**分散到一组 Cell 里各自 CAS**，size 时求和。这正是 `LongAdder` 的算法，**CHM 与 LongAdder 共享了同一位作者（Doug Lea）的同一思路**。
- **原子复合操作**：`compute/computeIfAbsent/merge` 在桶锁内执行「读-改-写」整段逻辑——examples/ex04 实测 32 线程 × 2 万次 `compute` 自增精确无丢失。而裸 `get+put`（无锁读改写）在对照实验里丢了 40 万次。**这提醒：CHM 保单个操作原子，不保「你先 get 再 put」的跨操作原子——复合逻辑要主动用 compute 系列**。

> ph09 已讲过 `ConcurrentHashMap` 的遍历弱一致性；**遍历时并发修改「可能看到也可能看不到」，这是弱一致性设计不是 bug**。强一致的替代要自己加锁——大多数缓存/计数场景弱一致足够。

### 3.7 ClassLoader 深入：委派链的源码真相与三种打破场景

ph10 讲了双亲委派「是什么」（先让父加载器加载），本阶段补**源码链**与**为什么要打破**。

**① 委派链的源码形态（JDK 17 `ClassLoader.loadClass`，语义简化）**

```java
protected Class<?> loadClass(String name, boolean resolve) throws ClassNotFoundException {
    synchronized (getClassLoadingLock(name)) {        // 同类加载的并发去重
        Class<?> c = findLoadedClass(name);           // ① 自己加载过？直接返回
        if (c == null) {
            if (parent != null) {
                c = parent.loadClass(name, false);    // ② 先问父加载器（委派在这里）
            } else {
                c = findBootstrapClassOrNull(name);   // 顶层父是 null → Bootstrap
            }
        }
        if (c == null) {
            c = findClass(name);                      // ③ 父也没有 → 自己 findClass
        }
        ...
    }
}
```

委派链（JDK 17 实测见 examples/ex06）：**App ClassLoader（`app`）→ Platform（`platform`）→ Bootstrap（打印为 null，C++ 实现）**。为什么要委派：**核心类只加载一次**（`java.lang.String` 若被应用自定义覆盖，整个类型系统就碎了）与**安全**（核心库不能被篡改）。

**② 类的身份 = 类名 + 定义它的 ClassLoader**。两个不同 loader 加载同名类得到两个完全隔离的 Class——examples/ex06 用自定义 loader 从两个目录加载同名 `Greeting`，实测各自输出不同版本。这正是**命名空间隔离**：jar 冲突（ph11 的依赖冲突）在运行时就是这样互相看不见对方的类。

**③ 三种典型的「打破双亲委派」场景**

| 场景 | 为什么必须打破 | 怎么打破 |
|------|---------------|---------|
| **SPI 反向加载**（JDBC 驱动等） | 启动类加载器加载的 `DriverManager` 想用 `Class.forName("com.mysql...")`——但实现类在应用的 classpath，父加载器看不见 | **线程上下文类加载器（TCCL）**：`Thread.currentThread().getContextClassLoader()` 把「以谁的名义加载」从父翻转给子；ServiceLoader（3.8）默认也走 TCCL |
| **Web 容器隔离**（Tomcat） | 多个 Web 应用可带同名不同版本的库，不能共享 | 每个应用一个 `WebappClassLoader`：**自己先加载**应用 lib，找不到才交父——`loadClass` 顺序倒过来 |
| **热部署/模块化** | 一个 JVM 里要同时存在新旧两版类 | 自定义 loader 每次重新 `defineClass`（见 examples/ex06 的 DirBreakingLoader），旧 loader 连同它的类一起被 GC |

> 自定义 loader 的正确姿势是重写 `findClass`（保留委派），**只有需要打破时才重写 `loadClass` 本身**（ex06 演示的是后者，注释里标了「打破点」）。OSGi/JPMS 的模块化是更系统的类隔离方案，本阶段不展开。

### 3.8 Reflection / Proxy / SPI：框架的三把螺丝刀

ph15 用过 Spring 的依赖注入与 AOP，本阶段看「框架凭什么能注入、能织入、能自动装配」。

**① 反射（Reflection）：运行时才看得到类**

`Class` 对象是「类的自描述」：编译期能拿到的（`Class.forName`/`对象.getClass()`/`类型.class`）与拿不到的细节（private 字段、方法、注解、泛型签名）都从它身上取。三个关键点：

- **`getDeclaredXxx` vs `getXxx`**：前者拿本类声明的（含 private），后者沿继承链拿 public——想读 private 必须 `getDeclaredField` + `setAccessible(true)`（examples/ex05 实测读写 private 字段）。这正是 IOC/ORM 注入 private 字段、序列化框架读写字段的机制。
- **模块系统的收紧**：JDK 16+ 默认强封装 JDK 内部——反射第三方模块私有成员会抛 `InaccessibleObjectException`，**反射不是万能钥匙，它尊重模块边界**（`--add-opens` 只能由模块所有者开启）。
- **性能与替代**：反射 `invoke` 比直接调用慢（参数装箱、类型检查、JIT 无法内联），高热点路径用 **MethodHandle**（可被 JIT 当成直接调用优化）更合适；Spring 底层两种都用。**判断要不要优化**：反射用在「装配期」（启动一次）不优化，用在「每请求热路径」才换 MethodHandle。

**② 动态代理（Proxy）：运行时生成一个「接口的实现类」**

```text
JDK Proxy：Proxy.newProxyInstance(loader, 接口数组, InvocationHandler)
  运行时合成一个 $Proxy0 类（implements 你的接口），每个方法调用都转给 handler.invoke
  → 你只写 handler：调用前做日志/鉴权/事务/远程转发，再 method.invoke(目标) 或返回假实现

  限制：只能代理「接口」（Java 单继承，合成类无法 extends 任意业务类）
  CGLIB：绕过限制靠「生成子类 + 重写方法」——不能代理 final 类/final 方法
```

| | JDK 动态代理 | CGLIB 子类代理 |
|--|------------|---------------|
| 生成物 | 实现接口的类 | 继承目标类的子类 |
| 前提 | 目标必须实现接口 | 类非 final、方法非 final |
| Spring 选择 | 有接口默认用 | 无接口或 `proxyTargetClass=true` 用 |
| 机制 | InvocationHandler 回调 | MethodInterceptor 回调 + 字节码生成（ASM） |

examples/ex05 实测了 JDK Proxy：`Proxy.isProxyClass` 为 true、handler 拦截到 `greet` 调用并可加计时。**AOP/事务/MyBatis Mapper 接口**（ph15）全都是这套「接口 + 运行时合成实现」——理解 Proxy 后，`@Transactional` 为什么只对**从容器取出的 bean**生效、自调用为什么失效（`this` 不是代理），都能推出来。

**③ SPI（ServiceLoader）：把「用什么实现」留给外部声明**

反射与代理解决了「运行时找到类」，SPI 解决「**运行时找到哪个实现**」：调用方只依赖接口，实现方在 `META-INF/services/<接口全限定名>` 文件里登记自己的全限定类名，`ServiceLoader.load(接口)` 按文件发现并实例化。examples/ex05 实测：加一个实现 + 加一行登记，调用方零改动就多出一个服务。

**JDK 里的三个 SPI 现场**（背下这三个，面试的 SPI 题就答全了）：

| 现场 | 机制 | 与类加载器的纠缠 |
|------|------|----------------|
| JDBC 驱动 | `META-INF/services/java.sql.Driver` 登记驱动 | `DriverManager` 是 Bootstrap/平台类，驱动在应用 classpath → 必须用 TCCL 反向加载（3.7 场景 1 的实锤） |
| slf4j 绑定 | services 文件登记 logback/log4j 实现 | 绑定的选择完全靠 SPI |
| Spring Boot 自动配置 | `spring.factories` / `AutoConfiguration.imports` | Boot 用它收集自动配置类，再配合条件注解装配 |

### 3.9 Netty：高并发网络编程的工程答案

ph14 用 Tomcat、ph16 用网关处理过 HTTP，本阶段的问题是：**「百万连接、大量小消息」这类长连接高并发，Java 怎么写？** JDK 裸 NIO 的答案太痛（Selector 编码复杂、ByteBuffer 的 flip/compact 状态机反直觉、粘包半包要自己拆、还有历史性的 epoll 空轮询 bug），Netty 把痛点点名解决。

**① 线程模型：Reactor 三种形态，Netty 用主从**

```text
Reactor 单线程：一个线程既 accept 又读又写 —— 简单但单点（Redis 早期模型）
Reactor 多线程：一个 accept 线程 + 一组 IO 线程处理读写
主从 Reactor（Netty 默认形态）：
  bossGroup（默认 1 线程）──accept──▶ 把连接注册给 workerGroup
  workerGroup（2×CPU 线程） ──每个连接的一生绑定到一个 EventLoop 线程──▶ 该连接的全部读写
```

- **EventLoop = 一个「永远 run 事件循环的线程」**：连接注册给它后，它的读写、定时、pipeline 回调全在这个线程上串行执行。**串行 = 无需加锁**——同一 channel 的业务代码不会并发执行，这是 Netty 高性能（无锁争用）与易用（不用锁）的双重来源。examples/ex08 与 exercises/sol-04 的实测都跑在这个模型上（可 `jstack` 看到 `nioEventLoopGroup-*` 线程）。
- **ChannelPipeline**：请求在 pipeline 上**从前往后**过 inbound handler（解码），响应**从后往前**过 outbound handler（编码）。粘包/半包等字节问题被 **codec**（如 `LineBasedFrameDecoder`、`StringDecoder/Encoder`）消化——sol-04 只加三行 codec，业务 handler 收到的就是完整 `String` 行，不用再碰 ByteBuf。**「把协议细节从业务里剥出去」是 Netty 最核心的工程贡献**。
- **零拷贝（概念级）**：Netty 语境下的「零拷贝」主要指**减少用户态拷贝**，包括 Direct Buffer（堆外字节，native IO 直读，省去堆↔堆外一次复制）、`CompositeByteBuf`（多个 buffer 逻辑合并不物理拷贝）、`FileRegion`（文件发送走 `sendfile` 让内核直接搬运，绕过用户态）。**注意别理解成「零系统调用」**——socket 读写本身的系统调用还在。
- **和虚拟线程的关系**：ph09 的虚拟线程（JDK 21）走的是「每个任务一个线程、阻塞也不心疼」的路；Netty 走「少量线程 + 事件驱动」。两者解决同类问题、哲学相反——**虚拟线程让「同步阻塞式」代码享受高并发，Netty 让「事件驱动式」代码高效**。选型：存量同步代码上虚拟线程迁移成本低；重 IO 事件链、需要精细背压控制时 Netty 更成熟（这也是 gateway/网关类 ph16 的底层选 Netty 的原因）。

> 本阶段的 Netty 只到「能搭服务、能读 pipeline」；**Netty 的 TCP 粘包策略选型（定长/分隔/长度域）、自定义协议编解码、背压与水位属于进阶网络专题**，如需深入不在本 roadmap 后续阶段安排，可自行按官方 guide 推进。

### 3.10 设计模式在 JDK 里的应用：模式是「变化的识别」

本阶段不重讲 23 种 GoF 的语法（每种一个类图 + 一段示例是最容易被搜到的内容），换一个更有分析价值的视角——**在 JDK/JUC 里看到模式，模式就有了判断标准：它解决哪种变化**。

| 模式 | 解决的变化 | 在 JDK/JUC 里的现场 | 直觉 |
|------|-----------|--------------------|------|
| 单例 | 全局唯一 | `Runtime.getRuntime()`、`System` 的 console | 工具/基础设施天然唯一 |
| 工厂方法 | 创建哪种对象由子类定 | `Collection.iterator()`、`NumberFormat.getInstance()`、`ExecutorService`（由工厂创建） | 面向接口创建，不 new 具体类 |
| 抽象工厂 | 一族对象的创建 | `DatatypeConverter`、JDBC `DriverManager` 拿到不同驱动 | 换实现族不动调用方 |
| 模板方法 | 算法骨架固定、步骤可变 | **AQS**（3.3，骨架是 acquire/release）、`AbstractList`、`InputStream.read`、`ThreadPoolExecutor` 的钩子（3.4） | 骨架不变，钩子留给你 |
| 策略 | 算法整体可替换 | `RejectedExecutionHandler`（3.4 拒绝策略）、`Comparator`、`ThreadFactory` | 把 if-else 换成一个可注入的对象 |
| 装饰器 | 给对象动态加职责 | `BufferedReader`（字符缓冲）、`Collections.synchronizedXxx/unmodifiableXxx` | 层层包裹，每层加一点 |
| 适配器 | 接口形态不匹配 | `Arrays.asList`、`InputStreamReader`（字节流→字符流）、`List.of` 系列 | 桥接两种接口 |
| 代理 | 控制对目标的访问 | `java.lang.reflect.Proxy`（3.8）、`Collections.checkedXxx` | 加一层壳做拦截 |
| 观察者 | 一对多通知 | `PropertyChangeSupport`、事件监听器体系、`Flow`（响应式流） | 发布-订阅解耦 |
| 生产者-消费者 | 速率解耦 | `BlockingQueue` 全家 + 线程池的任务队列（3.4） | 缓冲带隔开两头 |
| 不可变对象 | 并发下的共享安全 | `String`、包装类型、`LocalDate`、`List.of()` | 不可变 = 天然线程安全（呼应 JMM 3.2） |

**现代视角（为 analysis/ 铺路）**：函数式接口把「策略」和「模板方法」从类层次压成了 lambda——`Comparator.comparing(...)` 不再需要为每个策略建一个类；`execute(Runnable)` 本身就是把「行为」作为参数传递。**模式在 JDK 里逐步从「类结构」演化成「函数形态」**，这是 Java 8+ 之后读老设计模式书时要做的观念更新。

### 3.11 DDD：限界上下文、聚合与领域服务

roadmap 必会概念「DDD 服务复杂业务建模」。DDD 回答的问题是：**当业务复杂到「表结构推不出业务规则、对象只是数据的搬运工」时，怎么建模？** 传统 CRUD 的开发顺序是「先建表 → 生成实体 → service 里写 if-else」——表驱动让业务规则散落在 service 与 Controller，这就是「贫血模型」。DDD 把顺序倒过来：**先理解业务、找边界、建模型，表结构只是模型的持久化投影**。

**① 战略设计：先切边界，再谈建模**

- **限界上下文（Bounded Context）**：一个上下文 = 一组内聚的业务概念 + 自己的通用语言。**同一词在不同上下文可以是不同概念**：「订单」在交易上下文有金额、在物流上下文只有包裹状态——不需要一个全局 Order 模型。**限界上下文是微服务拆分的理论依据**（ph16 的「按业务拆服务」在这里拿到判据：服务边界 ≈ 上下文边界）。
- **上下文之间的映射**：防腐层（ACL，翻译对方模型，防止对方变更传染）、开放主机服务（OHS，对外暴露接口）、共享内核、发布语言（模型间通过事件通信）——`下游防上游、事件做解耦`。
- **通用语言（Ubiquitous Language）**：业务词（不是表名）进入代码：`Order.place()`、`Vehicle.goOffline()`——**代码里的词要能拿给业务专家读**。

**② 战术设计：聚合内的不变式**

| 战术组件 | 一句话职责 | 反例（贫血味） |
|---------|-----------|---------------|
| 实体（Entity） | 有身份（id 相等即同一）且状态可变 | 一个只有 getter/setter 的 POJO |
| 值对象（Value Object） | 无身份、靠属性值相等（`Money(amount,currency)`、坐标） | 把金额拆成两个 double 字段散落 |
| **聚合（Aggregate）** | **一组对象的边界 + 一致性边界**；外部只能通过**聚合根**操作 | 跨对象随意 setter 改状态 |
| 聚合根（Aggregate Root） | 聚合的唯一入口，内部不变式由它保证 | Controller 直接改订单明细 |
| 仓储（Repository） | 聚合的存取抽象（接口在领域层） | 直接在 Service 里写 SQL/拼 JPA |
| 领域服务（Domain Service） | 不属于任何单个实体的业务动作（如「对账」） | 塞进某个实体的上帝方法 |
| 应用服务（Application Service） | 编排用例（事务边界、调领域服务/仓储），不含业务规则 | 业务规则写在 Controller |
| 领域事件 | 聚合间最终一致的通知 | 直接远程调别的服务 |

**聚合设计的三条硬规则**：① 聚合内的修改必须满足自身不变式（如「订单总额 = 明细之和」在根上保证）；② **跨聚合修改只发事件、不直接改别人**（最终一致）；③ 聚合要小——**一致性边界是代价，能小则小**。这三条直接解释了为什么 ph17 的 MQ 用在「跨域事件」上而不是「跨表事务」上。

**③ 怎么落地一个 DDD 模块（典型分层）**

```text
interfaces（Controller/入参出参 DTO）→ application（用例编排/事务）→ domain（实体/聚合/领域服务/仓储接口）
                                                              ↘ infrastructure（JPA/MyBatis 实现仓储、消息、外部服务）
依赖只能向内：domain 不依赖任何框架与数据库 —— 这是「业务核心可独立测试」的根基
```

**④ 什么时候需要 DDD（诚实边界）**：CRUD 管理台、报表、纯数据搬运——DDD 是负担（凭空造领域层 = 浪费）；**业务规则复杂（状态机、金额/库存规则、多方协作）、要长期演进的系统**才值得。这也是 roadmap 把 DDD 放在 ph20（最后一个通用阶段）的原因：前面 ph13 的 ORM、ph15 的 Spring、ph16 的微服务、ph17 的消息都学完，DDD 是把它们按「领域」组织起来的方法论。ph21 数据平台的「节点状态机、告警规则、版本发布管理」就是 DDD 的典型应用场——到 ph21 再结合具体业务展开。

## 4. 底层原理

### 4.1 JMM 的落地：缓存一致性、store buffer 与内存屏障

happens-before 是 JMM 的**规范层**，本小节看它怎么落到真实硬件。现代 CPU 是这样执行「共享变量写」的：

```text
CPU0 ──▶ L1/L2 ──▶ store buffer ◀──┐
                                     │ 总线（缓存一致性协议，如 MESI）
CPU1 ──▶ L1/L2 ──▶ load 队列  ◀───┘

写流程：CPU0 写 x —— 不直接写内存，而是进 store buffer，等缓存行失效确认后合并
读流程：CPU1 读 x —— 可能读到 L1 里的旧值（它还没收到 CPU0 的失效消息）
```

- **MESI 一类的一致性协议**保证「**同一缓存行的内容最终一致**」，但不保证「**立即一致**」——CPU0 的写还躺在自己的 store buffer 里没对外可见。这就是**可见性问题的物理来源**：不是玄学，是 store buffer 的存在。
- **乱序的物理来源**：CPU0 按 `y=1; x=1` 的顺序写，第一条 y 的 store 因缓存行失效慢而卡在 buffer，第二条 x 可能先完成对外发布——**写顺序被 store buffer 打乱**；读侧也有类似（load 队列、猜测执行）。
- **内存屏障 = 强制冲刷这些 buffer**。x86（TSO 模型）只在少数点需要强屏障（`mfence`/带 lock 前缀指令），ARM 则要求更细的屏障（`dmb`）。Java 不直接暴露屏障指令——**volatile 与 synchronized 编译后插入对应屏障**（如 volatile 写在 x86 上是 `lock addl`，在 ARM 上插入 release 屏障），JVM 按平台生成「恰好足够」的屏障序列。**所以同样的 Java 代码在不同 CPU 上行为一致，靠的是 JVM 把 JMM 规则翻译成各平台屏障**——这就是「write once, run anywhere」在并发层的含义。
- **JMM 不是要求所有实现都顺序一致**：它允许弱于顺序一致的重排，只保证 happens-before 链上的读写有序——`volatile int i` 的读写是 acquire/release 语义，**但不阻止它与其他变量在无 HB 关系时乱序**。理解这一层，「为什么 DCL 要 volatile」「为什么无锁读能拿到新值」就不再是背结论。

### 4.2 AQS 的等待队列：CLH 变体与 LockSupport 的唤醒协议

AQS 的队列是 **CLH 锁的变体**：每个等待线程一个 Node，Node 里记录前驱与等待状态（`SIGNAL`/`CANCELLED`/`CONDITION`/`PROPAGATE`），线程用 `LockSupport.park` 阻塞、由前驱释放时 `unpark` 唤醒。为什么这样设计——**省掉「唤醒谁」的广播**：

```text
队列尾 ← Node(t2, waits SIGNAL) ← Node(t1, waits SIGNAL) ← head(=当前持锁线程的占位)
                                                              │
释放锁：head 线程把后继 Node 的状态 CAS 为 0 → LockSupport.unpark(t1)
                                                              │
t1 被唤醒后自旋拿锁（非公平锁还会先 CAS 抢一次）→ 成为新 head
```

- **为什么用前驱节点传状态而不是直接唤醒**：释放者只需要唤醒**队首第一个**后继（一个 unpark），其余线程继续 park——公平、且唤醒开销 O(1)。节点状态 `SIGNAL` 保证「我 park 前先告诉前驱：你释放时记得叫我」，**避免释放发生在 park 之前导致永远睡死**的经典竞态（unpark 与 park 之间的窗口由 AQS 的状态机闭合）。
- **中断的语义**：`park` 被中断不会抛异常，而是返回后由 AQS 检查中断标志决定抛 `InterruptedException` 还是忽略——所以 `lockInterruptibly` 与 `lock` 对中断的响应不同，这是 AQS 模板里刻意保留的策略差异。
- **LockSupport.unpark 的「许可」模型**：unpark 相当于发一张许可，park 消费许可——**先 unpark 后 park 也能让 park 立即返回**（不会睡死），这正是很多手写同步器用 LockSupport 而非 `wait/notify` 的原因（notify 在 wait 之前调用会丢失信号）。**用 `synchronized` 的 wait/notify 时那个「先检查条件再 wait」的 while 循环，换成 LockSupport 也需要同样的条件检查**——许可机制去掉的是「丢唤醒」风险，不是「虚假唤醒」风险。

### 4.3 ConcurrentHashMap 的扩容：transfer 如何被多线程分片

JDK8 CHM 扩容把 O(表长) 的重建工作**切给多个线程协作**，这是它「写并发还能扩容」的关键，也是面试常问的 `sizeCtl` 的用处：

```text
扩容发起线程：newTable = 旧表 ×2 → sizeCtl = -1 - 参与扩容线程数 记录协作人数
transfer 按 stride 分片：旧表下标从高到低，每片若干桶（如 16 个）分给一个线程
  每个参与线程 CAS 认领一个片 → 处理该片桶：迁移单节点/按高低位拆链/拆树
  处理完的桶放 ForwardingNode（hash=-1 的占位）→ 后续读写看到它就知道「此桶已搬走」
线程处理完自己这片 → 再认领下一片 → 全部桶搬完 + sizeCtl 恢复 0 → 扩容结束
```

- **为什么用 ForwardingNode**：搬迁中的桶不能让别的线程再写旧桶（会丢），占位节点让**后到的 put 主动 helpTransfer 加入搬迁**或等待——读写遇到 ForwardingNode 走新表，天然无锁地处理「扩容中间态」。
- **get 在扩容中怎么不丢**：读节点走 `tabAt`（volatile 读 table 元素）；遇到 ForwardingNode 就去读新表。**写者保证「先搬完一个桶再放占位符」**，所以读者要么读旧桶完整链、要么读新表，永远看不到半搬状态（一致性靠 volatile 发布的顺序，衔接 3.6）。
- **「并发扩容」为什么难**：涉及「多个线程同时改 table 引用、认领互不重叠的片、计数收敛」——CHM 用 `sizeCtl`（int 兼作阈值/负数标记/协作人数）这一个字段 + CAS 完成了全部协调。**读 CHM 源码的推荐路线**：先读 `putVal` 主干 → 再读 `addCount`（触发扩容的地方）→ 最后攻 `transfer`；4.1/3.6 的 volatile 语义是理解它的前置。

## 5. 使用场景

- **JVM 深水知识什么时候真正需要**（兑现 ph19 预告的完整链路）：ph19 教会你把服务「装上墙」（容器配额 + MaxRAMPercentage）；本阶段的判断力用在这些时刻——**GC 停顿突增时**知道先看日志里是 young 还是 mixed、先怀疑对象分配速率而不是抄参数；**内存曲线缓涨**知道去查存活集而不是堆大小；**容器被 OOMKilled 而堆日志正常**知道去查堆外（Metaspace/DirectBuffer）。GC 选型表（3.1）只在「默认 G1 不够」时启用。**日常开发 90% 用不到这些——它的价值是线上异常时不抓瞎**。

| 现实问题 | 用到的本阶段机制 | 一句话解法 |
|---------|----------------|-----------|
| 某接口 P99 突增、GC 日志显示频繁 Full | GC 日志解读（3.1）+ 指标曲线 | 先看对象逃逸/大对象，再决定堆大小或收集器 |
| 自研限流/缓存需要一把「可中断、可超时的锁」 | AQS（3.3） | 先看 JUC 有没有现成，再考虑继承 AQS |
| 线程池任务堆积、内存涨 | 线程池原理（3.4） | 队列有界 + CallerRuns + 监控队列深度 |
| 缓存框架选型 | CHM vs HashMap（3.5/3.6） | 并发写选 CHM；单线程或不可变数据选 HashMap |
| 热部署/多版本 jar 并存 | ClassLoader（3.7） | 自定义 loader 隔离，或接受重启 |
| 给框架写 starter / 插件 | SPI（3.8） | META-INF/services 登记 + ServiceLoader |
| 长连接网关、IM、推送 | Netty（3.9） | 主从 Reactor + pipeline codec |
| 复杂业务系统从 0 设计 | DDD（3.11） | 先找限界上下文再建模，别先建表 |

- **什么时候不该用这些**：CRUD 后台不需要 DDD；能跑默认 G1 就别调 GC；能用 `ExecutorService` 工厂就别手写线程池；**「读懂 AQS」的价值在于排查（锁饥饿、死锁 dump 里的 AQS 栈帧）与写扩展，不在于日常造轮子**——生产代码优先用 JUC 现成组件，自研同步器是最后手段。
- **跨语言对比（为 analysis/ 与 Tenet 合成积累素材）**：
  - **Go 并发模型 vs Java JUC**：Go 用 goroutine + channel 通信（CSP，「不要通过共享内存通信」），Java 用平台线程 + 锁/CAS 保护共享内存；Java 的虚拟线程（ph09）让「每任务一线程」重新可行，两边的**调度成本趋近**；Java 的并发工具是「库式」（AQS 由你选锁/队列/原子类组合），Go 的并发是「语言式」（go 语句 + 内置 channel）——同样的生产者-消费者，Java 写 BlockingQueue、Go 写 channel，语义等价而语法归属不同。
  - **C++ 内存模型 vs JMM**：C++11 的 `memory_order`（relaxed/acquire/release/seq_cst）比 Java 更细粒度、更底——JMM 的 volatile 约等于 C++ 的 seq_cst 写/读（Java 不允许 relaxed volatile）；**JMM 把「每个普通字段 + volatile + 锁」统一成一套 happens-before 规则**，C++ 只对标记了原子/屏障的对象给保证。**Java 的「默认安全」来自语言层单规则，C++ 的「精确控制」来自显式标注**——这是托管语言与系统语言在并发契约上的根本分工。
  - **并发集合的对应**：Go 的 `sync.Map` 面向「读多写少 + key 稳定」场景做了读写分离优化，Java 的 CHM 面向通用读写 + 计数 + 复合操作；两者都不承诺强一致遍历。**结论级素材**：Java 并发生态是「二十年积累的库集合」，Go 是「小而正交的原语」，映射到 Tenet 设计时可权衡「并发原语进语言还是进标准库」。

## 6. 代码示例

> 完整可运行版在 [`examples/`](./examples/)（八个示例目录）。验证环境：OpenJDK 17.0.18（Homebrew）；ex08 额外依赖 netty 4.1.137.Final（从 Maven Central 手动拉 jar，实测通过）。全部纯 Java 与 Netty 示例已本机实测标注「已验证」；涉及 Spring/Maven 构建的表述只给结论与命令、标注「未在本环境验证」。练习参考实现（sol-01~04）在 [`exercises/`](./exercises/)，项目在 [`project/`](./project/)。

```java
// examples/ex02-aqs-mini-reentrant-lock/MiniReentrantLock.java —— 30 行实现 AQS 重入锁（已验证）
// state=0 空闲则 CAS；state>0 且当前线程是 owner 则累加（重入）；归零才真正释放
protected boolean tryAcquire(int acquires) {
    Thread current = Thread.currentThread();
    int c = getState();
    if (c == 0) {
        if (compareAndSetState(0, acquires)) {
            setExclusiveOwnerThread(current);
            return true;
        }
    } else if (current == getExclusiveOwnerThread()) {
        int next = c + acquires;
        setState(next);                       // 重入：不需要 CAS，自己独占
        return true;
    }
    return false;                             // 失败 → AQS 入队 + park
}
```

```text
# examples/ex07-gc-log-demo/ 实测采集的日志行（-Xlog:gc:file=...，48MB 堆跑 60 轮×12MB 分配）
[0.148s][info][gc] GC(2) Pause Young (Concurrent Start) (G1 Humongous Allocation) 26M->2M(48M) 0.682ms
# 解读：GC(2)=第 3 次停顿；原因 humongous（1MB 数组超 region 半）；26M->2M 一次回收 24MB 垃圾；
# (48M)=堆上限。本程序 60 轮共 140 次 Pause Young、0 次 Full —— 压力全被 young gc 消化
```

### 示例 1：JMM 可见性实证（[`examples/ex01-jmm-visibility/`](./examples/ex01-jmm-visibility/)）

volatile 修复段（确定性 PASS）+ synchronized 的 unlock→lock happens-before 实证 + 一个**故意错误的非 volatile 对照段**（文件头注明：本机未复现，换环境可能复现——不确定性如实交代）。**已验证**（编译通过可运行，修复段 PASS）。

### 示例 2：AQS 手写可重入锁（[`examples/ex02-aqs-mini-reentrant-lock/`](./examples/ex02-aqs-mini-reentrant-lock/)）

继承 AbstractQueuedSynchronizer 覆写 tryAcquire/tryRelease 的最小互斥锁，8 线程×2 万次重入自增无丢失。**已验证**。

### 示例 3：手写线程池（[`examples/ex03-handwritten-threadpool/`](./examples/ex03-handwritten-threadpool/)）

execute 四段路径（core→queue→max→reject）+ worker 复用循环 + shutdown 中断空闲 worker（真实 TPE shutdown 语义）。**已验证**（8/8 PASS，修过两个实现 bug：任务丢失与线程泄漏——文件注释记录了修复点，本身就是「写并发代码」的教训现场）。

### 示例 4：CHM 并发行为（[`examples/ex04-chm-concurrency/`](./examples/ex04-chm-concurrency/)）

`compute` 原子自增无丢失 + 裸 HashMap 对照（实测丢约 40 万次更新）+ 弱一致遍历安全。对照段是**故意错误示例**，文件头已注明。**已验证**。

### 示例 5：反射 + 动态代理 + SPI（[`examples/ex05-reflection-proxy-spi/`](./examples/ex05-reflection-proxy-spi/)）

getDeclaredField/setAccessible 读 private 字段、JDK Proxy 拦截接口调用、ServiceLoader 发现两个实现。**已验证**。

### 示例 6：类加载器委派链与打破（[`examples/ex06-classloader-hierarchy/`](./examples/ex06-classloader-hierarchy/)）

委派链打印（app→platform→bootstrap）+ 自定义 loader 打破双亲委派加载同名类，证明「类 = 类名 + 加载器」。**已验证**（5/5 PASS）。

### 示例 7：GC 日志演示与解读（[`examples/ex07-gc-log-demo/`](./examples/ex07-gc-log-demo/)）

GcLogDemo（制造 young gc 压力）+ README 里的日志逐段解读表与「健康信号 vs 告警信号」判读表。**已验证**（140 次 Pause Young / 0 次 Full，日志样例为真实采集）。

### 示例 8：Netty Echo（[`examples/ex08-netty-echo/`](./examples/ex08-netty-echo/)）

Netty 4.1.137.Final 的 EchoServer/EchoClient：ServerBootstrap + boss/worker 双 EventLoopGroup + pipeline。**已验证**（实测 ECHO OK；netty jar 手动拉取步骤与 mvn 用 pom 见其 README）。

## 7. 总结

### 关键要点

- **ph20 是「用」（ph09/ph10/ph15）到「造与诊」的翻转**：JMM/AQS/线程池/CHM 从 API 记忆变成机制理解，读框架源码（Spring/AQS/Netty pipeline）有了地图
- **JMM 的答案是 happens-before 规则集**：可见性/有序性不是玄学，是「哪条规则保证什么」的可推导体系；volatile = acquire/release，不含原子性；DCL 必须 volatile 是有序性考题
- **AQS = 一个 int state + CLH 变体队列 + 模板方法**：ReentrantLock/Semaphore/CountDownLatch/ReadWriteLock 的 state 语义各异，排队阻塞一套共享；Condition 是另一条条件队列
- **线程池执行链是四段式**：core → queue → max → reject；无界队列使 ③ 永不触发（fixed 池的真面目）；Worker 是循环取任务的线程，线程复用 = 任务排队；Worker 继承 AQS（3.3 闭环）
- **HashMap 的 8/0.75/2 幂都是算出来的**（泊松分布、位运算、高低位拆分），JDK8 用尾插 + 树化修掉 JDK7 的死循环，但从不承诺线程安全
- **CHM 两代是「锁粒度革命」**：JDK7 锁分段 → JDK8 CAS + 桶锁 synchronized；无锁读依赖 volatile 发布；计数靠 baseCount + CounterCell（LongAdder 同源）；扩容由多线程分片 + ForwardingNode 收尾
- **类加载器：类身份 = 类名 + 加载器**；委派保核心安全，SPI/Tomcat/热部署三种场景主动打破（TCCL 是「从父到子」的翻转）
- **框架三把螺丝刀**：反射（运行时看类）、Proxy（运行时造实现）、SPI（运行时选实现）——IOC 注入、AOP 织入、自动配置全是它们的组合
- **Netty 的关键是线程模型**：连接绑定 EventLoop 线程 → 串行无锁；pipeline + codec 把字节协议剥出业务；零拷贝是「少拷贝」不是「零系统调用」
- **模式 = 变化的识别**，DDD = 复杂业务的建模顺序（先边界后模型），两者都是「什么时候该用比怎么实现更重要」的判断力

### 阶段验收清单

- [ ] 能给一个服务按「停顿/吞吐/堆大小」三数字选 GC，并说清 G1 的 Region/humongous 与 ZGC 染色指针思路
- [ ] 能读懂 `-Xlog:gc` 一行（类型/原因/前后占用/停顿），能区分 young/mixed/full 与健康信号
- [ ] 能默写 happens-before 规则并解释 volatile 为何修好 DCL、为何不含原子性
- [ ] 能画出 AQS 的 state + 队列结构，说清独占/共享、公平/非公平的差异（对应 ex02 实现）
- [ ] 能画出线程池 execute 四段路径，解释无界队列陷阱与 CallerRuns 策略、shutdown 如何中断空闲 worker
- [ ] 能说清 HashMap JDK7→8 的三处结构变化与并发不安全的真实表现（对应 ex04 对照）
- [ ] 能说清 CHM JDK8 的 put 路径（CAS → 桶锁 → 树化 → 协助扩容）与无锁读为何安全
- [ ] 能说出双亲委派三种打破场景并演示自定义 loader 隔离同名类（ex06）
- [ ] 能用反射+代理+SPI 组合解释 Spring IOC/AOP/自动配置的机制（ex05）
- [ ] 能画出主从 Reactor 线程模型并解释「EventLoop 串行 = 无锁」（ex08/sol-04）
- [ ] 能说清聚合的三条规则与限界上下文为何是微服务边界依据

### 跨语言对比

- **Go**：goroutine+channel（CSP）vs Java 线程+锁/队列（共享内存）；虚拟线程拉平调度成本后，差距主要在「并发原语在语言里还是库/框架里」（为 analysis/ 与 Tenet 合成积累素材）
- **C++**：memory_order 的细粒度 vs JMM 的统一 happens-before；C++ 把并发契约做成「显式标注的库+编译器屏障」，Java 做成「语言层规则 + JVM 翻译成各 CPU 屏障」——托管语言用统一规则换默认安全，系统语言用显式标注换极致控制
- **GC**：JVM 的 G1/ZGC 是可调参数 + 并发收集器家族；Go 的 GC 是单一并发收集器（无 CMS/G1 式家族），靠调 GOGC 与内存限制；Rust 无 GC 用所有权（ph03/Rust 路线已学）——**「自动内存」的复杂度要么进运行时（Java 的收集器家族与调优），要么进编译器（Rust 的所有权）**，这是 Tenet 内存策略可对照的坐标
- **网络高并发**：Go 的 netpoller（epoll 封装 + goroutine 阻塞语义）与 Netty 的 EventLoop 殊途同归（底层都是多路复用），差别在 Java 的「少量线程显式事件驱动」与 Go 的「海量 goroutine 隐式阻塞」；虚拟线程让 Java 也能走 Go 的路（ph09）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：手写简易 IOC（练习 1）→ 手写线程池 + submit（练习 2）→ RPC demo（练习 3）→ Netty TCP server（练习 4），四题对应 roadmap 第 20 节列出的四个练习，且分别升级自 examples/ex05、ex03、ex08。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**简易 IOC 容器**（roadmap 推荐项目之一）——纯 Java 注解驱动的迷你容器：@Component 注册、@Inject 构造器/字段注入、单例缓存、接口歧义检测、循环依赖检测（A→B→A 抛异常并打印创建链），7/7 PASS **已在 OpenJDK 17.0.18 本机验证**。它把「反射 + 注解 = 框架能力」这条线走完，并留下与 Spring `DefaultSingletonBeanRegistry` 三级缓存的对照入口。建议完成练习后再动手。
- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立运行 project/ 的 MiniIocDemo（7 行 PASS）并通过其验收标准

### 下一阶段

[**ph21 数据平台 / 数据中心后端方向 Java 阶段**](../ph21-data-platform/21-data-platform.md)——（Java 路线最后一个阶段，现已建成）本阶段积累的所有机制将汇入真实业务：JMM/并发（数据接入的高吞吐）、CHM/线程池（实时状态缓存与接入服务）、反射/代理/SPI（接入协议插拔与规则引擎）、Netty（长连接接入网关的底层形态）、DDD 的限界上下文（任务与资源管理 / 调度发布 / 告警规则按领域切分）——到 ph21 把这些机制按「数据平台链路：数据源 → 接入服务 → Kafka → 清洗/告警/存储 → 运维后台」组织成完整系统。

