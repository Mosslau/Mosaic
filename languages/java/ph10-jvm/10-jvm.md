# Java JVM 阶段

> 面向企业级后端、微服务方向，本阶段理解 Java 程序运行机制并具备性能分析能力——看得懂 class 字节码与 GC 日志，拿得起 jps/jstack/jmap/jstat/jcmd 与 Arthas。

## 1. 概述

JVM 阶段的目标是：**能理解 Java 程序从源码到字节码再到运行的完整机制，并具备性能分析与线上问题排查能力**。解释类加载、内存区域与 GC 如何协同工作，用 JVM 参数约束内存行为，用 jps/jstack/jmap/jstat/jcmd/Arthas 定位死锁、内存泄漏与 GC 异常。这是从「会写 Java」走向「懂 Java」的关键一跃——并发、框架、分布式最终都运行在同一套 JVM 机制之上：ph09 里 synchronized 的锁升级、线程池的工作队列，其底层原理都藏在对象头 Mark Word 与内存区域中。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 运行时数据区 | 程序计数器、虚拟机栈、本地方法栈、堆、方法区/元空间 |
| 类加载机制 | 加载·验证·准备·解析·初始化、双亲委派模型 |
| 字节码与 JIT | class 文件结构、javap 反汇编、解释执行与分层编译 |
| GC 基础 | GC Roots、可达性分析、分代、Minor GC / Full GC、-Xlog:gc 日志 |
| 收集器 | Serial、Parallel、CMS、G1、ZGC 对比与选型 |
| JVM 参数 | 堆大小、栈大小、GC 选择、GC 日志、OOM 转储 |
| 诊断工具 | jps、jstack、jmap、jstat、jcmd、jinfo、jfr、Arthas |
| 问题排查 | 死锁与阻塞、内存泄漏、OOM、GC 停顿 |

这个阶段只涉及单机 JVM 内部的运行机制与诊断（class 文件与字节码、类加载、GC、JIT、内存模型、JVM 参数与诊断工具），**不涉及构建工程化、依赖管理与多模块工程**（ph11 Maven/Gradle 与工程化阶段，目录已建）、**不涉及单元测试与工程质量体系**（ph12 单元测试与工程质量阶段，roadmap 第 12 节，目录待建）、**不涉及 Web 框架与 Spring 生态的启动优化、连接池与 JVM 联动**（ph15 Spring 全家桶阶段，roadmap 第 15 节，目录待建）、**不涉及分布式环境下的内存与并发问题**（ph16 微服务与分布式阶段，roadmap 第 16 节，目录待建）、**不涉及缓存中间件与高并发架构的 JVM 侧实践**（ph18 缓存与高并发阶段，roadmap 第 18 节，目录待建）、**不涉及 Netty 与高级性能调优框架**（ph20 高级 Java 阶段，roadmap 第 20 节，目录待建）。本阶段承接 ph09 多线程与并发阶段——synchronized 锁升级改写的对象头 Mark Word、线程池工作线程与内存区域的关系、JMM 的 happens-before 规则（ph09 4.1 已讲），都将在本阶段的机制与实证里找到落点。

## 2. 来源与演变

Java 诞生时 JVM 采用**解释执行**（interpreter）——逐条翻译字节码指令，简单但慢。真正的转折是 **HotSpot VM**：Sun 在 1999 年收购 Longview Technologies 获得该技术，JDK 1.3（2000）起 HotSpot 成为默认 JVM。它得名于「热点检测」——运行时统计方法调用次数，只对**热点代码（hot code）**做深度编译优化，避免「把所有代码都编译一遍」的启动代价。早期 JIT 编译器分两套：**C1（Client Compiler）**编译快、优化浅，**C2（Server Compiler）**编译慢、优化深；后来用**分层编译（tiered compilation）**把两者串起来：解释执行起步，热点方法先升 C1 再升 C2，兼顾启动速度与峰值性能（JDK 8 起默认开启）。

GC 的演进是「吞吐 → 停顿 → 可预测停顿」的路线。**Serial**（串行）最简单；**Parallel** 用多线程并行回收、吞吐优先，是 JDK 8 的默认收集器；**CMS**（Concurrent Mark Sweep）引入并发标记以降低停顿，但碎片化与浮动垃圾问题突出，JDK 9 弃用、JDK 14 移除；**G1（Garbage First）**把堆切成 Region，可设置停顿目标（`-XX:MaxGCPauseMillis`，实测默认值 200ms），JDK 9 起成为默认；**ZGC** 用染色指针与读屏障把停顿压到**亚毫秒级**，JDK 15 正式化，JDK 21 又推出分代 ZGC。内存结构同步演进：JDK 8 移除永久代（PermGen），类元数据移入**元空间（Metaspace，本地内存）**，字符串常量池移入堆。

诊断工具链随之成熟。JDK 5/6 起 jps、jstack、jmap、jstat 陆续进入标准 JDK，jcmd（JDK 7）把 VM 级诊断统一到一个入口；JFR（Java Flight Recorder）JDK 11 开源进 OpenJDK，成为低开销的在线采样工具（jcmd/jfr 在本机 OpenJDK 17 均可直接用）。真正改变线上排查体验的是**阿里巴巴 Arthas**（2018 年开源）——基于 Java Agent 的在线诊断工具，不需要重启进程即可 dashboard 看全局、thread 查线程、jad 反编译线上代码、watch/trace 观测方法入参与返回值，成为国内排查线上问题的标配。

| 版本/年份 | 演进 |
|-----------|------|
| JDK 1.0（1996） | 解释执行；JVM 成为「一次编译、到处运行」的载体 |
| JDK 1.3（2000） | HotSpot 成为默认 JVM；C1/C2 JIT 编译器成型 |
| JDK 6（2006） | 锁升级、逃逸分析、压缩指针（compressed oops） |
| JDK 7（2011） | G1 以实验特性引入；jcmd 诊断工具 |
| JDK 8（2014） | 移除永久代 → 元空间；默认 Parallel 收集器；分层编译默认开启 |
| JDK 9（2017） | G1 成为默认收集器；`-Xlog` 统一 GC 日志；CMS 弃用；jhat 移除 |
| JDK 11（2018） | JFR 开源进 OpenJDK；ZGC 实验特性 |
| JDK 15（2020） | ZGC 正式化；Shenandoah 正式化 |
| JDK 17（2021） | 移除实验性 AOT（jaotc）；默认 G1 + 分层编译 + 逃逸分析（均为本阶段实测基线） |
| JDK 21（2023） | 分代 ZGC（JEP 439） |

本文示例以 **Java 17（LTS）** 为基线（examples/exercises/project 的验证工具链为 OpenJDK 17.0.18，`javac -version` → 17.0.18，默认 G1 收集器；`-Xlog:gc` 自 JDK 9 起统一、17 上完全适用），JDK 25 独有的新特性按需标注。JVM 的类加载、GC 与内存模型核心语义自 JDK 8 以来保持稳定，17 上观察到的行为可直接迁移到 21/25；涉及诊断工具的断言（GC 日志格式、类加载顺序、栈深与 `-Xss` 的关系）全部经本环境实测证实，随机器波动的数字已标注——这个阶段的知识是整个 Java 生态中最稳定、最值得深挖的部分之一。

## 3. 语法与参数

### 3.1 运行时数据区：程序计数器·栈·堆·方法区/元空间

JVM 内存按职责分为五大区域，这是理解一切内存问题的地图：

| 区域 | 线程共享 | 内容 | 异常 |
|------|---------|------|------|
| 程序计数器（Program Counter Register） | 否 | 当前线程执行的字节码行号；线程切换后恢复执行位置 | 无 |
| 虚拟机栈（JVM Stack） | 否 | 每个方法一个**栈帧**：局部变量表、操作数栈、动态链接、返回地址 | `StackOverflowError`（递归过深） |
| 本地方法栈（Native Method Stack） | 否 | 执行 native 方法（如 JNI） | `StackOverflowError` |
| 堆（Heap） | 是 | 所有对象实例与数组；GC 的主战场，分新生代/老年代 | `OutOfMemoryError: Java heap space` |
| 方法区（Method Area） | 是 | 类元数据、常量池、静态变量；JDK 8 起实现为**元空间（Metaspace）**，使用本地内存 | `OutOfMemoryError: Metaspace` |

```bash
java -Xss512k -Xms512m -Xmx512m App   # -Xss 线程栈大小；-Xms/-Xmx 堆大小（3.8 详述）
```

- **栈是线程私有的**：每个线程一个虚拟机栈，栈帧随方法调用压栈/出栈——递归无限会 `StackOverflowError`，不是内存泄漏；栈大小默认值与平台相关（本机 macOS 实测 `ThreadStackSize` 默认 2048KB，见示例 6 栈深实验）
- **堆是线程共享的**：`new` 出来的对象都在堆上；栈上只存引用（对象地址）
- **元空间用本地内存**：默认没有上限（实测 `MaxMetaspaceSize` 默认值为 uintx 最大值，即「无限」），所以动态生成类（代理、热部署）可能悄然吃满内存——生产建议显式 `-XX:MaxMetaspaceSize`

### 3.2 类加载机制：加载·验证·准备·解析·初始化

.class 字节码要变成可运行的对象，必须经过类加载，**完整生命周期五步**：**加载**（读字节流，把类的二进制表示载入元空间，堆中生成 `Class` 对象）→ **验证**（格式/语义检查，防恶意字节码）→ **准备**（静态变量分配内存并赋**默认值**，如 `int` 赋 0）→ **解析**（把常量池中的**符号引用**替换为**直接引用**）→ **初始化**（执行 `<clinit>`，静态变量赋初始值、静态代码块执行）。

```bash
java -XX:+TraceClassLoading Demo   # 观察哪些类被加载（排查类加载问题的利器）
```

- **准备阶段赋的是默认值，初始化阶段才赋真实值**——`static int x = 42;` 在准备阶段 x=0，初始化阶段才变 42
- **初始化是懒触发的**：只有 `new`、访问静态成员、反射、初始化子类等「主动使用」才触发；`static final` 编译期常量被 javac 直接内联进使用方字节码（`ConstantValue` 属性），不触发类初始化——示例 2 用真实运行证实了这一点
- **双亲委派（parent delegation）**：类加载请求先委托父加载器，父加载器找不到才自己加载（详见 4.1）；`ClassNotFoundException` 与 `NoClassDefFoundError` 的区别——前者是找不到类，后者是类**初始化失败**后再次引用
- 完整的行为实证（加载链、懒初始化、双亲委派、打破双亲委派）见示例 2

### 3.3 字节码与 class 文件结构入门

`javac` 编译出的 `.class` 文件是 JVM 的指令集，以魔数 `0xCAFEBABE` 开头（实测：Java 17 编译的 class 文件 `minor version: 0, major version: 61`），结构依次为：常量池（constant pool）、访问标志（access flags）、本类/父类/接口索引、字段表、方法表（`Code` 属性存放字节码指令）、属性表。

```bash
javac Hello.java && xxd Hello.class | head -3   # 编译；前 4 个字节即 ca fe ba be（魔数）
javap -c Hello && javap -v Hello                 # -c 反汇编指令；-v 完整视图（常量池/方法表）
```

```java
public class Hello {
    public static void main(String[] args) {
        System.out.println("hello jvm");
    }
}
```

- **栈帧（stack frame）**是执行方法的骨架：局部变量表（参数与局部变量）、操作数栈（运算的工作台，`iload`/`iadd` 等指令在它上面进出栈）、动态链接（指向常量池中的类/方法引用）
- 典型指令（示例 1 反汇编实测）：`aload_0`（取 this）、`getstatic`/`putstatic`（读写静态字段）、`getfield`（读实例字段）、`invokevirtual`（调用实例方法）、`if_icmpgt`（整数比较跳转）
- **字节码是「半编译」产物**：与 C++ 的机器码不同，它不针对任何 CPU，由执行引擎解释或 JIT 编译执行
- **`javac -g` 影响调试信息（实测）**：`-g` 编译后 `javap -l` 有 `LineNumberTable`（源码行号 ↔ 字节码偏移）；`javac -g:none` 编译后行号表消失——生产要留异常堆栈与可调试性，别关掉 `-g`（构建工具默认行为见 ph11）

### 3.4 JIT 编译与分层编译（解释·C1·C2）

字节码有两种执行方式：**解释执行**逐条翻译（启动快、执行慢）；**JIT 编译**（Just-In-Time，即时编译）把热点方法编译为本地机器码（启动慢、执行快）。现代 JVM 两者结合，用**分层编译**分五层递进：解释执行（0 层）→ C1 各优化层（1-3 层）→ C2 深度优化（4 层）。方法调用次数超过阈值（`-XX:CompileThreshold`，实测默认 10000）即成为热点方法，触发升级。

```bash
java -Xint Demo && java -Xcomp Demo   # 纯解释 / 纯编译执行（对比性能用，生产别用）
java -XX:+PrintCompilation Demo       # 打印 JIT 编译了哪些方法（看热点方法）
```

- **JIT 的提速是数量级的（实测）**：同一热点方法（每批 500 万次迭代）默认分层编译下约 1~3ms/批，`-Xint` 纯解释下约 150~160ms/批——**解释执行比 JIT 慢约 50 倍**（示例 4，数字随机器波动，结论稳定）
- **线上服务刚启动「慢热」**：热点方法还没编译完，性能低于稳态——压测前先预热，这是「压测数字忽高忽低」的常见原因；`-XX:+PrintCompilation` 实测可见方法经历 `% 3` → `% 4`（C1 → C2）与 `made not entrant`（旧编译版本失效）
- JIT 优化包括**方法内联**、**逃逸分析**（4.4）、**循环展开**、**锁消除**——同一份代码在 JVM 上跑得比解释型语言快，主要靠 C2 的这些优化
- JDK 17 起移除了实验性 AOT（`jaotc`），提前编译方向转向 **GraalVM Native Image**（构建期编译为原生镜像，启动毫秒级，但失去动态能力）

### 3.5 GC 基础：GC Roots 与可达性分析

**垃圾回收（Garbage Collection, GC）**自动回收不再使用的对象，判断依据是**可达性分析（reachability analysis）**：从一组**GC Roots**出发，沿引用链能到达的对象视为存活，其余即垃圾。

**GC Roots 包括**：虚拟机栈帧中的局部变量/操作数栈引用、静态字段引用、常量池中的引用（字符串常量等）、被 `synchronized` 持有的对象（monitor）、JNI 引用。

```java
public class GcRootsDemo {
    static Object root = new Object();   // 静态字段 → GC Root
    public static void main(String[] args) {
        Object local = new Object();     // 局部变量 → GC Root（方法结束即失去 Root 资格）
        // local 不再被使用后（如置 null），它引用的对象就可被回收
    }
}
```

- 堆按代划分：**新生代（Young）** = Eden + 两个 Survivor（S0/S1，实测 `SurvivorRatio` 默认 8，即 Eden:Survivor = 8:1，表述「8:1:1」是常见近似）；**老年代（Old）** 存长期存活对象
- 对象在新生代出生，熬过多次 **Minor GC** 后**晋升（promotion）**到老年代（`-XX:MaxTenuringThreshold` 实测默认 15；另有动态年龄判定）；**大对象**直接进老年代（G1 下为巨型对象 humongous，直接占 Region——示例 3 的 GC 日志实测可见 `Humongous regions` 行）
- **GC 自动回收 ≠ 没有内存问题**：泄漏的对象仍被 GC Root 链引用，GC 永远回收不了它——这是本阶段必会概念，也是 3.11 堆 dump 分析的前提（练习 3 与 project 的泄漏实验台都是围绕它）

### 3.6 Minor GC 与 Full GC（复制·标记清除·标记整理）

不同代的回收算法不同，产生两种 GC：

| 类型 | 回收范围 | 算法 | 特点 |
|------|---------|------|------|
| Minor GC（Young GC） | 新生代 | **复制算法（copying）**：存活对象复制到 Survivor，Eden+Survivor 整体清空 | 频繁、快（大部分对象朝生夕灭） |
| Major GC | 老年代 | 标记-清除 / 标记-整理 | 少见、慢 |
| Full GC | 整个堆（+元空间） | 综合 | **最慢、停顿最长**，是性能问题第一信号 |

**标记-清除（mark-sweep）**只标记并清除，产生内存碎片；**标记-整理（mark-compact）**在清除后把存活对象向一端移动，消除碎片但成本更高；**复制算法**把存活对象搬到另一半，无碎片但浪费一半空间（用 Survivor 分担，无需浪费一半）。

- **GC 是「停止世界（Stop-The-World, STW）」的**：回收期间业务线程全部暂停——Minor GC 停顿毫秒级，Full GC 可能秒级；线上「服务卡顿」第一嫌疑就是 Full GC
- 触发 Full GC 的常见原因：老年代空间不足、元空间不足、`System.gc()` 被显式调用（含某些框架）、`-XX:+DisableExplicitGC` 可关闭显式 GC
- G1 下新生代回收叫 **Young GC**，老年代回收是**混合回收（Mixed GC）**——没有传统意义上的 Full GC 语义；示例 3 / 练习 4 用 `-Xlog:gc*` 实测了 `Pause Young (Normal) (G1 Evacuation Pause)` 行

### 3.7 常见收集器对比（Serial·Parallel·CMS·G1·ZGC）

| 收集器 | 策略 | 停顿 | 适用/状态 |
|--------|------|------|-----------|
| Serial | 单线程，串行回收 | 长 | 客户端、单核小内存；`-XX:+UseSerialGC` |
| Parallel | 多线程并行回收，**吞吐优先** | 较长 | JDK 8 默认；批处理、计算型任务 |
| CMS | 并发标记-清除，低停顿 | 短但碎片化 | JDK 9 弃用、JDK 14 移除，**新代码勿用** |
| G1 | Region 化，可预测停顿 | 可控（`-XX:MaxGCPauseMillis`，实测默认 200） | **JDK 9+ 默认**（实测 `UseG1GC` 默认 true），大堆服务端首选 |
| ZGC | 染色指针+读屏障，并发整理 | 亚毫秒级 | JDK 15+ 正式；超大堆、超低延迟场景 |

```bash
java -XX:+UseG1GC -XX:MaxGCPauseMillis=200 -jar app.jar   # 明确使用 G1 并设停顿目标
java -XX:+UseZGC -Xmx16g -jar app.jar                      # 超大堆低延迟场景用 ZGC
```

- **G1 是当前默认与主流**：把堆划分为约 2048 个 Region，回收时优先回收「垃圾最多」的区域（Garbage First 得名），通过 `-XX:MaxGCPauseMillis` 让停顿可预期
- **选型口诀**：追求吞吐（批处理）用 Parallel；追求低延迟（在线服务）用 G1；延迟极度敏感且堆很大再考虑 ZGC
- 收集器只能**配对使用**（新生代/老年代组合），G1/ZGC 是整堆的；不要盲调参数，先用默认收集器跑出 GC 日志再决策——程序内可以用 `ManagementFactory.getGarbageCollectorMXBeans()` 读到当前收集器名（示例 6 实测：默认 `G1 Young Generation + G1 Old Generation`，换 `-XX:+UseSerialGC` 变 `Copy + MarkSweepCompact`）

### 3.8 JVM 参数（堆大小·GC 选择·日志参数）

JVM 参数分三类：`-X` 非标准参数（`-Xms`/`-Xmx`/`-Xss`/`-Xmn`）、`-XX` 高级参数（布尔型 `-XX:+UseG1GC` 开启、`-XX:-UseG1GC` 关闭；数值型 `-XX:MaxMetaspaceSize=256m`）、普通参数（`-Dkey=value` 系统属性）。

| 参数 | 作用 | 示例 |
|------|------|------|
| `-Xms` / `-Xmx` | 堆初始 / 最大大小 | `-Xms512m -Xmx512m`（生产建议相等，避免扩容抖动） |
| `-Xmn` / `-XX:NewRatio` | 新生代大小 / 新生代:老年代比例 | `-Xmn256m`、`-XX:NewRatio=2` |
| `-Xss` | 线程栈大小 | `-Xss512k`（影响递归深度，见示例 6） |
| `-XX:MaxMetaspaceSize` | 元空间上限 | `-XX:MaxMetaspaceSize=256m` |
| `-XX:+UseG1GC` | 选择收集器 | `-XX:+UseG1GC`（另见 3.7） |
| `-XX:+HeapDumpOnOutOfMemoryError` | OOM 时自动导出堆快照 | 搭配 `-XX:HeapDumpPath=/data/dump` |
| `-Xlog:gc*` | GC 日志（JDK 9+ 统一日志） | `-Xlog:gc*:file=gc.log` |
| `-XX:+PrintGCDetails` | GC 日志（JDK 8 及以前） | 搭配 `-Xloggc:gc.log` |

```bash
# 生产启动参数参考（G1 + 相等堆 + OOM 转储 + GC 日志）
java -Xms512m -Xmx512m -XX:+UseG1GC -XX:MaxGCPauseMillis=200 \
     -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/data/dump \
     -Xlog:gc*:file=/data/logs/gc.log -jar app.jar
```

- **坑：`-Xmx` 只管堆**——元空间、线程栈、直接内存（NIO）都不算在内，堆配得再大也可能在别处 OOM
- **坑：堆设太大未必好**——堆越大 GC 停顿越长；容器部署还要注意 cgroup 内存限制（实测默认 `MaxRAMPercentage=25`，即最大堆默认为物理内存 1/4——本机 24GB 内存实测默认 `maxMemory` 为 6GB；JDK 8u191+ 默认容器感知）
- 查看当前生效参数：`jcmd <pid> VM.flags`、`java -XX:+PrintFlagsFinal -version`，或程序内 `Runtime.maxMemory()`/`ManagementFactory.getRuntimeMXBean().getInputArguments()`（示例 6 实测 `-Xms64m -Xmx256m` → 程序读到 `maxMemory=256MB / totalMemory=66MB`）

### 3.9 诊断工具（jps·jstack·jmap·jstat·jcmd·jfr·Arthas）

JDK 自带工具是排查第一梯队，Arthas 是进阶利器；本机 OpenJDK 17 实测 jps/jstat/jstack/jmap/jcmd/jinfo/jfr 全部可用：

| 工具 | 用途 | 常用命令 |
|------|------|---------|
| jps | 查看 Java 进程（JVM Process Status） | `jps -lv`（-v 显示启动参数） |
| jstack | 线程 dump（thread dump） | `jstack <pid> > thread.txt` |
| jmap | 堆信息、导出堆快照 | `jmap -histo <pid>`、`jmap -dump:format=b,file=h.hprof <pid>` |
| jstat | 实时 GC 统计 | `jstat -gcutil <pid> 1000`（每秒一次） |
| jcmd | 统一诊断入口（JDK 7+） | `jcmd <pid> help`、`jcmd <pid> Thread.print`、`jcmd <pid> GC.heap_dump h.hprof`、`jcmd <pid> VM.metaspace` |
| jfr | 飞行记录器（JDK 11+ 开源进 OpenJDK） | `jcmd <pid> JFR.start` / `JFR.dump` 后 `jfr view` 分析 |
| Arthas | 在线诊断，免重启 | `java -jar arthas-boot.jar` 后 `dashboard` / `thread` / `watch` / `trace` / `jad` |

```bash
jps -l                      # 1. 找到目标进程 pid
jstat -gcutil <pid> 1000    # 2. 看 GC 健康度（S0/S1/E/O/M 各区使用率 + YGC/FGC 次数）
jstack <pid> > thread.txt   # 3. 线程 dump 到文件，供分析
jmap -dump:format=b,file=heap.hprof <pid>   # 4. 导出堆快照（大堆会暂停，注意时机）
```

- **Arthas 的核心价值是「免重启」**：`thread -n 3` 找 CPU 最高线程、`watch com.x.Service method` 观测方法入参返回值、`jad com.x.Service` 反编译线上代码、`trace` 打方法耗时——改不了代码的线上问题它都能看
- 工具需要目标进程的**同用户权限**；容器里先 `docker exec` 再执行；`jcmd <pid> GC.heap_dump h.hprof` 可替代 jmap 导出
- **平台小坑（实测）**：本机 macOS 上 `jstat -gcutil` 的 M（元空间）/CCS 列显示 `-`——该平台构建未向 PerfData 暴露这两个指标，元空间使用率改用 `jcmd <pid> VM.metaspace` 查看；其他列正常
- 三个工具的实操（练习 1~3）：`jps` 找进程 → `jstat` 看 GC 健康度 → `jstack` 定位死锁 → `jmap` 找可疑类与导出快照，见 exercises/

### 3.10 线程 dump 与死锁分析

**线程 dump** 是某一时刻所有线程的栈快照，配合 jstack 抓取。它回答了三个问题：每个线程在干什么、卡在哪个锁上、有没有死锁。线程常见状态：`RUNNABLE`（运行/可运行）、`BLOCKED`（等锁）、`WAITING`（无限等待）、`TIMED_WAITING`（限时等待）、`NEW`/`TERMINATED`。

```bash
jstack <pid> > thread.txt   # 线程 dump 落盘
grep -c "java.lang.Thread.State" thread.txt && grep -A 1 "Found one Java-level deadlock" thread.txt   # 统计线程数 + 直接看死锁结论
# CPU 飙高定位三步：
top -Hp <pid>          # 1. 找 CPU 占用最高的线程，记线程号 N
printf '%x\n' N        # 2. 十进制转十六进制（jstack 的 nid 是十六进制）
jstack <pid> | grep -A 20 "nid=0x..."                # 3. 定位到具体代码行
```

- **jstack 检测死锁直接给出答案（实测）**：输出 `Found one Java-level deadlock` 并列出两个线程互相等待的锁与持有者（练习 2 实测输出：`"worker-1": waiting to lock monitor ... which is held by "worker-2"` 与反向一条）
- **大量 `BLOCKED` 线程堆积 = 锁竞争或死锁**；`WAITING` 多且 `parking to wait` 频繁则查线程池配置与 `LockSupport`；线程状态与死锁的并发层面原理属于 ph09 多线程与并发阶段，这里聚焦工具用法
- 线程 dump 是**快照**，建议间隔几秒抓 2-3 份对比，判断线程是「短暂等待」还是「一直卡住」

### 3.11 堆 dump 与内存泄漏分析（MAT/jhat）

**堆 dump（heap dump）** 是堆中所有对象与引用关系的快照，用于回答「内存被谁占着、为什么回收不掉」。内存泄漏（memory leak）指对象已无用但仍被 GC Root 链引用——GC 永远回收不了，堆持续上涨直至 OOM。

```bash
jmap -dump:format=b,file=heap.hprof <pid>     # 导出堆快照（或 jcmd <pid> GC.heap_dump heap.hprof）
jmap -histo <pid> | head -20                  # 先快速看对象直方图：哪些类实例最多、占内存最大
# MAT：File → Open Heap Dump → Leak Suspects 报告 → Dominator Tree → Path to GC Roots 沿引用链找持有者
```

- **Leak Suspects 报告**直接给出「一个对象持有 X MB 内存，被 XX 引用」，双击即可沿引用链找到泄漏源头（通常是某个静态集合——project 实验台三种泄漏模式在 MAT 里沿引用链分别看到 `STATIC_CACHE`、`leak-worker` 线程的 ThreadLocalMap、`OPEN_CONNECTIONS`）
- **jmap -histo 是快照定位第一招（实测）**：三种泄漏模式在 40MB 保持期实测 `[B`（byte[]）约 9700 实例 / 42.5MB，远超其他类——先认出「哪个类占大头」，再决定 dump 与 MAT
- **jhat 已被移除（JDK 9）**；MAT 之外也可用 VisualVM 或 `-XX:+HeapDumpOnOutOfMemoryError` 让 OOM 时自动留证
- **内存泄漏 ≠ 内存不足**：堆 dump 看到「明明没在用却大量存活」的对象，才是泄漏；堆本来就小则属于容量问题（调 `-Xmx`）

### 3.12 本阶段高频坑一览

| 坑 | 症状 | 对策 |
|----|------|------|
| 堆太小（`-Xmx` 过低） | 频繁 Full GC、`Java heap space` OOM | 结合对象规模设置堆，配合堆 dump 验证 |
| **静态集合不断 add** | 内存持续上涨，老年代占满 | 定位持有者（MAT）、定期清理、换带淘汰的缓存 |
| **连接/IO 未关闭** | 句柄与内存双泄漏 | try-with-resources |
| ThreadLocal 不 remove | 线程池复用导致对象滞留 | `finally { threadLocal.remove(); }` |
| 大对象频繁产生 | 老年代快速占满，Full GC 频繁 | 控制单对象大小、检查大缓存 |
| 元空间溢出 | `Metaspace` OOM（动态代理/热部署） | `-XX:MaxMetaspaceSize` + 排查动态生成类 |
| 线程泄漏（无限 `new Thread`） | `unable to create new native thread` | 线程池 + 有界队列（衔接 ph09） |
| 裸 `new byte[...]` 当语句 | **编译错误**（数组创建不是合法语句） | 赋值给变量并累计使用，防逃逸分析消除 |
| 上线不开 GC 日志与 OOM 转储 | 故障后无据可查 | 生产默认 `-Xlog:gc*` + `-XX:+HeapDumpOnOutOfMemoryError` |

## 4. 底层原理

### 4.1 类加载的双亲委派与类卸载

JDK 9 起的类加载器层级：**启动类加载器（Bootstrap）**（C++ 实现，加载 `java.base` 等核心模块）→ **平台类加载器（Platform）**（替代旧扩展类加载器，加载 `java.sql` 等平台模块）→ **应用类加载器（Application）**（加载 classpath 下的应用类）。**双亲委派（parent delegation）**：类加载请求沿层级**自下而上**委托，父加载器能加载就交给父，父加载不了才由自己加载。

```
请求加载 com.example.Demo → 委托 Application → Platform → Bootstrap
  → Bootstrap 能加载 java.base 核心类则由其加载 → 找不到则逐级回退 → Application 从 classpath 加载
```

- **双亲委派的意义**：避免同一个类被不同加载器重复加载（**类身份 = 类名 + 定义它的加载器**，示例 2 实测：两个自定义加载器各自 defineClass 同一份字节 → 两个 `Class` 对象不相等、`instanceof` 为 false）；**保护核心类**——自定义的 `java.lang.String` 永远不会被 Bootstrap 之外的加载器加载，防止污染核心库
- **打破双亲委派**：**线程上下文类加载器（Thread Context ClassLoader）**——JDBC 等 SPI 场景由 Bootstrap 加载核心接口，但实现类（MySQL 驱动）在应用 classpath，必须让应用类加载器反向加载；`ServiceLoader` 就是典型；示例 2 的 `BreakingLoader` 用「先自己 defineClass、读不到再回退父」演示了同一机制
- **类卸载**：类由加载它的 ClassLoader 卸载，前提是该加载器不可达且其加载的所有类均不可达——**自定义 ClassLoader + 不释放 = 元空间泄漏**（热部署/动态代理频繁生成类正是元空间 OOM 的元凶）

### 4.2 对象头与内存布局（Mark Word·Klass Pointer·对齐）

堆中一个普通对象由三部分组成：**对象头（Object Header）** + **实例数据** + **对齐填充**（64 位 JVM 对象大小按 8 字节对齐）。

对象头又分两部分：

- **Mark Word**：64 位（未压缩时），存储**锁状态**（无锁/偏向锁/轻量级锁/重量级锁）、身份哈希码（identity hashcode）、**GC 分代年龄**（4 bit）、偏向线程 ID——ph09 的 synchronized 锁升级就是改写 Mark Word（注意 ph09 4.2 已说明：Java 15 起默认禁用偏向锁）
- **Klass Pointer（类型指针）**：指向元空间中的类元数据；默认开启**压缩指针（compressed oops）**时占 4 字节（堆 ≤ 32G），关闭或堆更大时 8 字节；数组对象还有 4 字节**长度字段**

- **Mark Word 是「多功能复用区」**：同一块空间在不同时刻存不同信息——无锁时存哈希码+年龄，轻量级锁时存锁记录指针，重量级锁时存 monitor 指针
- 对象头开销可观：一个空 `Object` 在 64 位 JVM 上是 16 字节（Mark Word 8 + Klass Pointer 4 + 对齐 4，压缩 oops 开启时的公认参考值）——**几百万个小对象会吃掉大量内存**，这是「对象数量膨胀」类 OOM 的物理原因；开启 `-XX:+UseCompressedOops`（默认）能显著降低引用内存占用

### 4.3 GC 三色标记与并发标记

**可达性分析**的算法基础是**三色标记（tri-color marking）**，把对象分三色：

- **白色**：未访问——可能是垃圾
- **灰色**：已被访问，但引用的子对象还没扫完（扫描的「工作前沿」）
- **黑色**：已扫描完其所有引用——确定存活

```
初始：GC Roots 染灰 → 循环：取灰色对象，其引用的白色对象染灰、自身变黑 → 无灰色对象时，剩余白色即垃圾
```

- **并发标记的致命问题——漏标**：标记线程与业务线程并发，业务线程可能把「黑色对象指向白色对象」的引用改掉，导致**存活对象被误回收**——所以并发收集器必须保证「黑色对象不再指向白色对象」或「新增引用被重新记录」
- 两种解决思路：**CMS 用增量更新（incremental update）**——黑色对象新引用白色对象时，把黑色对象重新变灰；**G1 用 SATB（Snapshot-At-The-Beginning，起始快照）**——标记开始时打快照，期间变化的引用按快照处理，简单但会产生**浮动垃圾（floating garbage）**：标记期间新产生的垃圾要等下一轮 GC
- ZGC 另辟蹊径：用**染色指针（colored pointers）**把标记信息直接编码进 64 位指针的保留位，配合**读屏障**在访问对象时即时标记，实现并发整理、亚毫秒停顿

### 4.4 JIT 编译与逃逸分析（栈上分配）

**逃逸分析（escape analysis）**是 C2 编译期的核心优化：分析对象是否「逃逸」出方法/线程。若对象只在方法内使用、不逃逸，则可以做三种优化：

1. **栈上分配（stack allocation）**：对象直接在栈帧内分配，方法结束即销毁——不经过 GC，堆压力骤减
2. **标量替换（scalar replacement）**：不创建对象，把对象字段拆成局部变量使用（如 `Point(x, y)` 拆成两个 int）
3. **锁消除（lock elision）**：检测到锁只被单线程访问，直接去掉加锁（衔接 ph09）

```java
public class EscapeDemo {
    public static long sum(int n) {          // 每轮循环都 new 一个 Point
        long total = 0;
        for (int i = 0; i < n; i++) {
            Point p = new Point(i, i);       // p 不逃逸出本方法 → 可能栈上分配/标量替换
            total += p.x + p.y;
        }
        return total;
    }
    static class Point { int x, y; Point(int x, int y) { this.x = x; this.y = y; } }
}
```

- **栈上分配不是语言保证，而是 JIT 优化**：`-XX:+DoEscapeAnalysis`（实测默认开启，可用 `-XX:-DoEscapeAnalysis` 关闭对比）；对象被返回、存入全局/静态结构、传入其他线程即「逃逸」，优化失效
- **逃逸与否的堆分配差异是数量级的（实测）**：同样 8×500 万次 `new Point`，非逃逸写法触发 GC 0 次，逃逸写法（存入 ArrayList）触发 GC 63 次——逃逸分析把不逃逸的对象标量替换掉，堆分配几乎为零（示例 4，数字随机器波动，对比关系稳定）
- **工具说明（实测）**：`-XX:+PrintEscapeAnalysis` 在 OpenJDK 17 发布版不可用（仅 debug 版 JVM，实测报 `notproduct` 错误）——观察逃逸分析效果用上面的 GC 次数对比或 JFR/JITWatch，别用不存在的选项
- 这就是为什么「循环里 `new` 对象」在 JVM 上通常并不可怕——逃逸分析兜底；但**逃逸对象**（如塞进静态集合）仍要进堆、走 GC

### 4.5 OOM 的类型与触发场景

`OutOfMemoryError` 不是一个异常而是一族，类型不同、根因不同、排查路径不同：

| OOM 类型 | 触发场景 | 排查思路 |
|----------|---------|---------|
| `Java heap space` | 堆满：堆太小或内存泄漏 | 堆 dump + MAT 定位泄漏或扩容 |
| `GC overhead limit exceeded` | GC 占用超过 98% 时间且回收不到 2% 堆 | 堆 dump：通常也是泄漏，先找谁在疯狂分配 |
| `Metaspace` | 类元数据占满（动态代理/热部署/反射） | `jcmd <pid> VM.metaspace` 看用量；排查动态生成类；设 `-XX:MaxMetaspaceSize` |
| `unable to create new native thread` | 线程数超 OS/容器限制（线程泄漏） | `ulimit -u`、数线程；查线程池（衔接 ph09） |
| `Direct buffer memory` | NIO 直接内存泄漏（ByteBuffer 未释放） | `-XX:NativeMemoryTracking=summary` 跟踪本地内存 |

- **GC overhead limit exceeded 是「堆快满且回收无果」的强信号**——通常意味着泄漏对象已占满堆，GC 每次只能回收一点点
- **OOM 排查第一原则：先留证据再重启**——`-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=...` 让 OOM 自动落盘 hprof，否则一重启现场就没了

### 4.6 JMM 的运行时实证：可见性实验与 happens-before

> JMM（Java 内存模型）的规则体系（happens-before 五条规则、volatile 语义）属于 ph09 多线程与并发阶段，这里不重复展开；本节从 JVM 运行时视角实证「没有同步时的不可见是真实存在的，同步保证可见性」。

**实证 1：非 volatile 标志的可见性失败（示例 5 实测）**——工作线程 `while (!plainStop) counter++;`，主线程 2 秒后置 `plainStop = true`。本机（x86 强内存模型 + HotSpot）多次实测工作线程**均未在超时内退出**：JIT 把标志读提升到循环外，主线程的写入对工作线程不可见。这是「无同步时读线程可能永远看不到写线程的修改」的运行时证据——注意它依赖硬件与编译时机（换架构/编译器可能不同），程序如实打印而不作硬断言，**不违反 JMM 正是因为它「不保证」**。

**实证 2：volatile 的可见性由 JMM 保证（示例 5 实测）**——同样的循环把 `plainStop` 换成 `volatile boolean volStop`，主线程置位后工作线程**总是及时退出**。volatile 写 happens-before 后续对同一 volatile 的读，HotSpot 用内存屏障实现——与硬件无关，断言稳定成立。

**实证 3：synchronized 安全发布（示例 5 实测）**——写线程在 `synchronized (lock)` 内写三个字段后释放锁，读线程获取同一把锁后读到完整 `[11,22,33]`。监视器锁规则：解锁 happens-before 后续加锁，解锁前的全部写入对加锁后的读线程可见——这是「安全发布（safe publication）」的最简单形式。

三个实证合起来回答一个问题：**JMM 不是「运气模型」而是「保证模型」**——不保证时（无同步）可能出问题（实证 1），保证时（volatile/synchronized）必然成立（实证 2/3）。这也是「并发代码为什么必须用对同步原语」的底层理由，与 ph09 的锁、原子类形成闭环。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 线上 CPU 飙高 | `top -Hp` + `jstack` 定位热点线程与代码行 |
| 服务卡死、接口超时 | 线程 dump：`BLOCKED`/`WAITING` 分析、死锁检测（练习 2） |
| 内存持续上涨、频繁 Full GC | `jstat -gcutil`、GC 日志、堆 dump + MAT（练习 3 / project） |
| 应用启动/运行报 OOM | OOM 类型识别（4.5）+ `HeapDumpOnOutOfMemoryError` 留证 |
| 新服务上线配 JVM 参数 | `-Xms/-Xmx`、G1、停顿目标、GC 日志（3.8 参考命令，示例 6） |
| 线上无法加日志排查问题 | Arthas：dashboard/thread/watch/trace/jad 免重启观测 |
| 面试/理解框架原理 | class 文件、类加载、GC、JIT 是理解 Spring/Netty/中间件底层的前提 |

**不适合**此阶段的事项：

- **构建工程化、依赖管理、多模块工程、CI 集成**——Maven/Gradle 属于 ph11 构建工具阶段（目录已建）
- **单元测试、Mock、覆盖率与工程质量体系**——ph12 单元测试与工程质量阶段（roadmap 第 12 节，目录待建）
- **JVM 调优在 Spring 生态的实践**（Spring Boot 启动优化、连接池与 JVM 联动、Actuator 监控指标）——ph15 Spring 全家桶阶段（roadmap 第 15 节，目录待建）
- **分布式环境下的内存与并发问题**（分布式锁、分布式缓存、跨进程故障）——ph16 微服务与分布式阶段（roadmap 第 16 节，目录待建）

## 6. 代码示例

本节展示完整可运行示例的关键片段与**实测输出**，完整文件在 [`examples/`](./examples/) 目录，各文件的编译/运行命令与验证环境见 examples/README.md。全部示例自带自检断言（失败抛 `AssertionError`），验证工具链 OpenJDK 17.0.18。

> **运行前提**：本机演示 JVM 行为的示例（javap、GC 日志、-Xint、-Xss）需要 JDK 17 工具链；涉及诊断目标进程的练习（exercises 练习 1~3）需要在独立终端运行目标程序，验证后 kill 清理，别留僵尸进程。

### 示例 1：class 文件结构与 javap 反汇编—— Java 8+

对应 ex01：程序读取自身 .class 字节验证魔数，配合 javap 观察字节码与 `-g` 差异。

```java
// examples/ex01-class-file.java —— class 文件结构与 javap 反汇编：魔数自检 + javap -c/-v/-l 解剖
// 验证环境：OpenJDK 17.0.18；编译：javac ex01-class-file.java；运行：java Ex01ClassFile
byte[] magic = in.readNBytes(4);
long magicInt = ((magic[0] & 0xffL) << 24) | ((magic[1] & 0xffL) << 16)
        | ((magic[2] & 0xffL) << 8) | (magic[3] & 0xffL);
// 注意：必须写成 0xCAFEBABEL（long 字面量）——若写 0xCAFEBABE 它是 int 字面量，因最高位为 1 而为负数，
// 与 long 比较时符号扩展成 0xFFFFFFFFCAFEBABE，恒不相等（本文件开发时踩过，正是教学点）
```

实测运行输出：

```text
class 文件魔数 = 0xCAFEBABE (应为 0xCAFEBABE): 通过
add(3,4)+base(10) = 17  (期望 17)
sumUp(100) = 5050  (期望 5050)
```

`javap -c` 反汇编 `add` 方法（实测）：

```text
int add(int, int);
  Code:
     0: getstatic     #13   // Field calls:I
     3: iconst_1
     4: iadd
     5: putstatic     #13   // Field calls:I
     8: iload_1
     9: iload_2
    10: iadd
    11: aload_0
    12: getfield      #7    // Field base:I
    15: iadd
    16: ireturn
```

`javac -g` 差异（实测）：`-g` 编译后 `javap -l` 有 `LineNumberTable`（如 `line 20: 0`）；`javac -g:none` 编译后只剩方法签名、无行号表。class 文件版本 `major version: 61`（= Java 17）。提示：常量池中编译期常量的内联证据见示例 2 的 `ConstantValue` 属性——访问 `static final` 常量不触发类初始化，字节码里也没有对常量所在类的引用。

### 示例 2：类加载机制与双亲委派—— Java 8+

对应 ex02（+ 配套类 LoadedHelper.java）：实证加载链、懒初始化、双亲委派与打破双亲委派。

```java
// examples/ex02-class-loader.java —— 类加载机制演示：加载链 / 懒初始化 / 双亲委派 / 打破双亲委派
// 验证环境：OpenJDK 17.0.18；编译：javac ex02-class-loader.java；运行：java Ex02ClassLoaderDemo
ClassLoader app = Ex02ClassLoaderDemo.class.getClassLoader();
ClassLoader platform = app.getParent();
ClassLoader bootstrap = platform.getParent();
// 核心类由 Bootstrap 加载：getClassLoader() 为 null
ClassLoader stringLoader = String.class.getClassLoader();
```

实测输出（节选）：

```text
Ex02ClassLoaderDemo 的加载链:
  jdk.internal.loader.ClassLoaders$AppClassLoader@...  ← AppClassLoader（应用类加载器）
  jdk.internal.loader.ClassLoaders$PlatformClassLoader@...  ← PlatformClassLoader（平台类加载器）
  null  ← Bootstrap 启动类加载器（getParent() 为 null）
java.lang.String 的加载器 = null  (null 即 Bootstrap, 核心类不在 classpath)
Class.forName("LoadedHelper", false, app) 已加载, 是否初始化? 看上面有无 <clinit> 输出（应无）
ConstantUser.GREETING = 编译期常量  (常量已内联, 不触发 <clinit>)
>> LoadedHelper <clinit> 执行 (initCount=1)
ParentFirstLoader.loadClass("LoadedHelper") 的加载器 = AppClassLoader  (父加载器 App 已能加载, 自定义加载器没机会自己加载)
两个加载器各自加载的 Class 是同一个对象吗? false  (应为 false: 类身份 = 类名 + 加载器)
b1 实例 instanceof LoadedHelper? false  (应为 false: 运行时类型由 b1 定义, 与编译期类型不是同一个类)
```

提示：`LoadedHelper` 是 public 独立文件（要被不同类加载器加载演示，public 保证跨加载器反射可访问）；打破双亲委派时核心类（`java.` 前缀）必须仍交给父加载器，防止污染核心库。

### 示例 3：GC 观察与 -Xlog:gc—— JDK 9+

对应 ex03：制造 Young GC 与 humongous 大对象，用统一日志观察。

```java
// examples/ex03-gc-observation.java —— GC 观察：制造 Minor GC 与对象晋升，配合 -Xlog:gc 解读真实日志
// 验证环境：OpenJDK 17.0.18（默认 G1）
// 运行：java -Xms64m -Xmx64m -Xlog:gc*,gc+promotion=debug Ex03GcObservation
for (int round = 0; round < 200; round++) {
    // 每轮 200 个 32KB 短命对象：Eden 快速填满 → 触发 Young GC（大部分被回收）
    for (int i = 0; i < 200; i++) {
        byte[] tmp = new byte[32 * 1024];
        total += tmp.length;             // 防止逃逸分析把分配整个优化掉
    }
    // 每 40 轮留 1 个 1MB 对象：熬过多次 Young GC 后晋升老年代
    if (round % 40 == 0) keep.add(new byte[1024 * 1024]);
}
```

实测 GC 日志（本机 OpenJDK 17，G1；停顿毫秒随机器波动，观察模式即可）：

```text
[0.027s][info][gc,start    ] GC(0) Pause Young (Normal) (G1 Evacuation Pause)
[0.028s][info][gc,heap     ] GC(0) Humongous regions: 2->2
[0.028s][info][gc          ] GC(0) Pause Young (Normal) (G1 Evacuation Pause) 25M->3M(64M) 0.350ms
[0.032s][info][gc          ] GC(4) Pause Young (Normal) (G1 Evacuation Pause) 60M->3M(64M) 0.217ms
[0.051s][info][gc,heap,exit] garbage-first heap   total 65536K, used 13538K ...
```

解读：`Pause Young (Normal)` = Young GC；`25M->3M(64M)` = 回收前 25M → 回收后 3M（堆上限 64M）；末尾 `0.350ms` = STW 停顿；`Humongous regions` = 1MB 大对象直接以巨型区域分配（G1 中 ≥ 区域大小一半的对象为 humongous，直接进老年代区）。**输出随机器/GC 时机波动，观察模式即可，不要断言精确数字**（ph08 教训：别把一次运行的数字当规律）。

### 示例 4：JIT 与逃逸分析—— Java 8+

对应 ex04：预热曲线、`-Xint` 对比、非逃逸 vs 逃逸的 GC 次数差异。

```java
// examples/ex04-jit-escape-analysis.java —— JIT 与逃逸分析：预热 + 非逃逸 vs 逃逸分配的 GC 差异
// 验证环境：OpenJDK 17.0.18
// 运行：java -Xms256m -Xmx256m Ex04JitEscapeAnalysis
//       java -Xint -Xms256m -Xmx256m Ex04JitEscapeAnalysis    （纯解释对比）
//       java -XX:+PrintCompilation Ex04JitEscapeAnalysis      （看热点方法编译）
static long pointSum(int n) {
    long total = 0;
    for (int i = 0; i < n; i++) {
        Point p = new Point(i, i);
        total += p.x + p.y;
    }
    return total;
}

static long pointSumEscaping(int n) {
    ArrayList<Point> list = new ArrayList<>(1024);
    long total = 0;
    for (int i = 0; i < n; i++) {
        Point p = new Point(i, i);
        list.add(p);                     // p 逃逸出本次迭代 → 逃逸分析失效
    }
    for (Point p : list) total += p.x + p.y;
    return total;
}
```

实测输出（数字随机器波动，结论稳定）：

```text
=== 1. JIT 预热（每批 5000000 次迭代 new Point, 单位 ms）===
  第 1 批:    3 ms   ← 含类加载/解释执行/JIT 编译开销
  第 2 批:    2 ms   ← 热点方法已编译, 进入稳态
  第 3 批:    1 ms
  第 4 批:    1 ms
=== 2. 逃逸分析对比（各跑 8 批）===
  非逃逸 pointSum(8×5000000) 触发 GC 0 次
  逃逸   pointSumEscaping(8×5000000) 触发 GC 63 次
```

`-Xint` 纯解释运行同一程序：每批约 150~160ms——**解释执行比 JIT 慢约 50 倍**；`-XX:+PrintCompilation` 实测可见 `Ex04JitEscapeAnalysis::pointSum @ 4 (43 bytes)` 出现 `% 3` / `% 4` 层级与 `made not entrant`。提示：`-XX:+PrintEscapeAnalysis` 在 OpenJDK 17 发布版不可用（仅 debug 版），别用；`-XX:+DoEscapeAnalysis` / `-XX:-DoEscapeAnalysis` 可开关（默认开启）。

### 示例 5：JMM 可见性实证—— Java 8+

对应 ex05：非 volatile 标志可见性实验 + volatile / synchronized 的保证。

```java
// examples/ex05-jmm-demo.java —— JMM 内存模型演示：volatile 可见性实验 + happens-before 安全发布
// 验证环境：OpenJDK 17.0.18
// 运行：java Ex05JmmDemo（约 4~5 秒）
static boolean plainStop;          // 非 volatile：读线程可能永远看不到写线程的修改
static volatile boolean volStop;   // volatile：写读之间建立 happens-before
Thread worker = new Thread(() -> {
    started.countDown();
    while (!plainStop) counter[0]++;
}, "worker-plain");
```

实测输出（本机 x86 强内存模型 + HotSpot）：

```text
=== 1. 非 volatile 标志可见性实验（观察类输出, 结论随平台波动）===
  主线程置 plainStop=true 后, 工作线程在 2 秒内退出: false  ← 可见性失败真实存在
=== 2. volatile 标志可见性（JMM 保证, 必然退出）===
  主线程置 volStop=true 后, 工作线程及时退出
=== 3. happens-before 传递: synchronized 安全发布 ===
  读线程在锁内读到完整 payload=[11,22,33] —— 监视器锁规则成立
```

提示：实证 1 的「未退出」依赖硬件与 JIT 编译时机（换架构不一定复现），程序如实打印不作硬断言——**这恰恰说明「JMM 不保证时可能出问题」**；实证 2/3 由 JMM 保证，断言稳定成立。规则的完整讲解在 ph09 4.1。

### 示例 6：JVM 参数与栈深—— Java 8+

对应 ex06：进程内读取生效配置 + `-Xss` 与递归栈深（StackOverflowError）。

```java
// examples/ex06-jvm-params.java —— JVM 参数调优观察：进程内读取生效配置 + -Xss 与栈深的关系
// 验证环境：OpenJDK 17.0.18
// 运行：java Ex06JvmParams / java -Xms64m -Xmx256m -Xss256k Ex06JvmParams / java -Xss4m Ex06JvmParams
static int maxRecursionDepth() {
    depth = 0;
    try {
        recurse();
    } catch (StackOverflowError e) {
        return depth;
    }
    return -1;
}
```

实测输出（本机 OpenJDK 17.0.18，14 核 / 24GB 内存；栈深随机器/JIT 波动）：

```text
JVM       : OpenJDK 64-Bit Server VM 17.0.18
堆配置生效: maxMemory=6144MB (对应 -Xmx), totalMemory=392MB (已申请, 对应 -Xms)   ← 默认堆 = 物理内存 1/4
GC 收集器 : G1 Young Generation + G1 Old Generation   ← 默认 G1; 换 -XX:+UseSerialGC 变 Copy + MarkSweepCompact
最大递归深度(触发 StackOverflowError 前) = 45662
```

`-Xss` 与栈深（实测，单调递增、数字随机器波动）：

| -Xss | 最大递归深度（本机实测） |
|------|--------------------------|
| 256k | 1,478 |
| 默认（本机 2048KB） | 45,662 |
| 4m | 126,154 |

`-Xms64m -Xmx256m` 时程序内读到 `maxMemory=256MB / totalMemory=66MB`——**参数生效与否可以在进程内直接验证**，这是排查「配了没生效」类问题的第一招。提示：`-Xss` 改的是**每线程**栈大小，不是全局；递归深度 ≈ 栈大小 ÷ 每帧消耗，生产上深递归要同时评估 `-Xss` 与算法。

## 7. 总结

### 关键要点

1. **Java 代码先编译成 class 字节码再在 JVM 上运行**——javac → 字节码（`0xCAFEBABE` 魔数，Java 17 为 major version 61）→ 类加载 → 执行引擎（解释 + JIT）
2. **运行时数据区五大区域**——程序计数器、虚拟机栈、本地方法栈、堆、方法区（JDK 8+ 实现为元空间，用本地内存、默认无上限）
3. **类加载五步**——加载、验证、准备、解析、初始化；初始化懒触发（`static final` 常量内联不触发）；**双亲委派**保护核心类、避免重复加载，可被线程上下文类加载器打破
4. **JIT 的提速是数量级的（实测约 50 倍）**——热点方法从解释执行升 C1 再升 C2；`-Xint` 纯解释慢一个数量级，压测前先预热
5. **GC 自动回收但不等于没有内存问题**——泄漏对象仍被 GC Root 可达，GC 永远回收不了；静态集合、连接未关、ThreadLocal 未 remove 是高发原因
6. **对象存活靠 GC Roots + 可达性分析判断**——分代收集：新生代复制算法（Minor GC），老年代标记-清除/标记-整理（Full GC）；G1 是 JDK 9+ 默认
7. **Minor GC 频繁且正常，Full GC 频繁必有妖**——老年代/元空间满、显式 GC 都会触发；`-Xlog:gc*` 一行日志看懂 GC 类型/用量/停顿
8. **逃逸分析把不逃逸对象标量替换掉（实测 GC 0 vs 63 次）**——循环里 `new` 对象通常并不可怕，逃逸进集合才走 GC
9. **JMM 是「保证模型」不是「运气模型」**——非 volatile 标志实测可见性失败真实存在，volatile/synchronized 的 happens-before 保证必然成立（规则见 ph09 4.1）
10. **诊断工具三件套**——jstack 定位死锁（实测直接输出 `Found one Java-level deadlock`）、jmap -histo + 堆 dump + MAT 定位泄漏、jcmd 统一诊断入口（本机 JDK 17 实测全部可用）；JVM 参数是否生效用进程内读取或 `-XX:+PrintFlagsFinal` 验证

### 跨语言对比：运行时与内存管理

| 维度 | JVM（Java） | Go runtime | Python CPython | C++ 手动 | Rust 所有权 |
|------|------------|-----------|----------------|----------|-------------|
| 代码形态 | class 字节码 → JIT 机器码 | 直接编译为机器码 | `.pyc` 字节码 → 解释执行 | 机器码 | LLVM IR → 机器码 |
| 内存管理 | 分代 GC（G1/ZGC） | 并发三色标记 GC | 引用计数 + 分代 GC | 手动 `new`/`delete` | **编译期所有权 + 借用检查** |
| 运行时数据区 | 栈/堆/方法区（元空间）/程序计数器 | 栈/堆（TCMalloc） | 栈/堆 + GIL | 栈/堆（开发者管理） | 栈/堆（所有权模型） |
| GC 停顿 | 可控（G1 目标毫秒级、ZGC 亚毫秒） | 毫秒级，并发标记 | 停顿小但整体性能低 | 无 GC（手动） | 无 GC（编译期） |
| 内存问题排查 | jps/jstack/jmap/jstat/jcmd/Arthas/MAT | pprof | tracemalloc/memray | valgrind/ASan | 编译期拒绝，运行时极少内存错误 |

对比结论：JVM 与 Go 都靠 GC 自动管理，区别在于 JVM 的停顿可配置可预测（G1/ZGC）、工具链最完整；CPython 的引用计数简单但受 GIL 与性能限制；C++ 把内存控制权交给开发者，换来性能但泄漏与悬垂指针风险高；Rust 用所有权模型把内存安全前移到编译期，代价是学习曲线——JVM 生态的独特优势是「**GC + 完备诊断工具**」的组合，这也是本阶段 jstack/jmap/MAT 价值的所在。

### 阶段验收清单

- [ ] 能解释 JVM 运行流程：源码 → 字节码 → 类加载（加载·验证·准备·解析·初始化）→ 执行引擎（解释/JIT）→ GC
- [ ] 能说出运行时数据区五大区域及职责（程序计数器/虚拟机栈/本地方法栈/堆/方法区-元空间）
- [ ] 能读懂 `javap -c/-v/-l` 输出，能解释 `javac -g` 对行号表的影响
- [ ] 能解释双亲委派与「类身份 = 类名 + 加载器」，知道打破双亲委派的场景（线程上下文类加载器）
- [ ] 能使用基础诊断工具（jps、jstack、jmap、jstat、jcmd、jfr，含 Arthas 常用命令），能解读 `-Xlog:gc*` 日志区分 Minor/Full GC、识别常见 OOM 类型
- [ ] 能用线程 dump 定位死锁和阻塞，用堆 dump（jmap -histo + MAT）分析内存泄漏
- [ ] 能说出常见 JVM 参数（`-Xms/-Xmx`、`-Xss`、GC 选择、日志与 OOM 转储）并给出生产参考配置，能用进程内读取验证参数生效
- [ ] 能说清 JMM 的可见性实证：非 volatile 可能不可见、volatile/synchronized 保证可见（happens-before）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 4 题后继续，题目与 roadmap「练习」小节一一对应：

- **查看 Java 进程**（★）：写持续运行的程序，`jps -l` 找 pid、`jstat -gcutil` 观察各区、`jstack` 看线程状态（提示：jstack 里 main 线程计算时为 `RUNNABLE`、sleep 时为 `TIMED_WAITING`；本机 macOS 上 jstat 的 M/CCS 列显示 `-` 属平台差异，用 `jcmd VM.metaspace` 兜底）
- **分析线程死锁**（★★）：两线程以相反顺序抢两把锁，`jstack` 定位 `Found one Java-level deadlock`（提示：加 `Thread.sleep` 放大窗口；修复 = 统一加锁顺序或 `tryLock` 超时；验证后 kill 进程）
- **导出 heap dump 并分析内存泄漏**（★★★）：静态集合泄漏程序 + `jmap -histo` 找 `byte[]` 突出 + 堆 dump + MAT 沿引用链找持有者（提示：给程序加「分配达上限后保持存活 60 秒」的档位，否则太快 OOM 来不及观察；`jcmd GC.heap_dump` 是等价替代）
- **查看 GC 日志**（★★）：短命对象程序 + `-Xlog:gc*`，识别 `Pause Young` 并解读 `25M->3M(128M)`（提示：实测同一负载 128m 堆 38 次、64m 堆 74 次 Young GC——堆越小 GC 越频繁）

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**内存泄漏实验台**——`static` / `threadlocal` / `conn` 三种典型泄漏模式 + `clean` 对照组，每模式运行到目标量后保持存活供诊断；用 `jstat` 观察老年代上涨、`jmap -histo` 找可疑类、堆 dump + MAT 沿引用链分别定位到静态集合 / 工作线程 ThreadLocalMap / 未关闭连接。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

roadmap 推荐的第一个项目「JVM 问题排查笔记」（把每次排查写成「现象 → 诊断命令与输出 → 根因 → 解决 → 预防」的 Markdown，积累自己的线上排查手册）作为扩展方向，project/README.md 已给出结构与素材。

### 下一阶段

[Maven / Gradle 与工程化阶段](../ph11-build-tooling/11-build-tooling.md) —— 构建工具、依赖管理、多模块工程、CI 集成：回答「javac 一行命令之外，真实项目的构建、依赖与打包怎么做」。
