# Java JVM 阶段

> 面向企业级后端、微服务方向，本阶段理解 Java 程序运行机制并具备性能分析能力——看得懂 class 字节码与 GC，拿得起 jps/jstack/jmap/Arthas。

## 1. 概述

JVM 阶段的目标是：**能理解 Java 程序从源码到字节码再到运行的完整机制，并具备性能分析与线上问题排查能力**。解释类加载、内存区域与 GC 如何协同工作，用 JVM 参数约束内存行为，用 jps/jstack/jmap/jstat/Arthas 定位死锁、内存泄漏与 GC 异常。这是从「会写 Java」走向「懂 Java」的关键一跃——并发、框架、分布式最终都运行在同一套 JVM 机制之上，ph09 里 synchronized 的锁升级、线程池的工作队列，其底层原理都藏在对象头与内存区域中。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 运行时数据区 | 程序计数器、虚拟机栈、本地方法栈、堆、方法区/元空间 |
| 类加载机制 | 加载·验证·准备·解析·初始化、双亲委派模型 |
| 字节码与 JIT | class 文件结构、javap 反汇编、解释执行与分层编译 |
| GC 基础 | GC Roots、可达性分析、分代、Minor GC / Full GC |
| 收集器 | Serial、Parallel、CMS、G1、ZGC 对比与选型 |
| JVM 参数 | 堆大小、GC 选择、GC 日志、OOM 转储 |
| 诊断工具 | jps、jstack、jmap、jstat、jcmd、jinfo、Arthas |
| 问题排查 | 死锁与阻塞、内存泄漏、OOM、GC 停顿 |

本阶段承接 ph09 多线程并发——jstack 线程分析、synchronized 锁升级（对象头 Mark Word）都是 JVM 机制的直接体现；不涉及构建工程化（ph11 Maven/Gradle）、Web 框架与 Spring 生态（ph15）、分布式问题（ph16）等。

## 2. 来源与演变

Java 诞生时 JVM 采用**解释执行**（interpreter）——逐条翻译字节码指令，简单但慢。真正的转折是 **HotSpot VM**：Sun 在 1999 年收购 Longview Technologies 获得该技术，JDK 1.3（2000）起 HotSpot 成为默认 JVM。它得名于「热点检测」——运行时统计方法调用次数，只对**热点代码（hot code）**做深度编译优化，避免「把所有代码都编译一遍」的启动代价。早期 JIT 编译器分两套：**C1（Client Compiler）**编译快、优化浅，**C2（Server Compiler）**编译慢、优化深；后来用**分层编译（tiered compilation）**把两者串起来：解释执行起步，热点方法先升 C1 再升 C2，兼顾启动速度与峰值性能（JDK 8 起默认开启）。

GC 的演进是「吞吐 → 停顿 → 可预测停顿」的路线。**Serial**（串行）最简单；**Parallel** 用多线程并行回收、吞吐优先，是 JDK 8 的默认收集器；**CMS**（Concurrent Mark Sweep）引入并发标记以降低停顿，但碎片化与浮动垃圾问题突出，JDK 9 弃用、JDK 14 移除；**G1（Garbage First）**把堆切成 Region，可设置停顿目标（`-XX:MaxGCPauseMillis`），JDK 9 起成为默认；**ZGC** 用染色指针与读屏障把停顿压到**亚毫秒级**，JDK 15 正式化，JDK 21 又推出分代 ZGC。内存结构同步演进：JDK 8 移除永久代（PermGen），类元数据移入**元空间（Metaspace，本地内存）**，字符串常量池移入堆。

诊断工具链随之成熟。JDK 5/6 起 jps、jstack、jmap、jstat 陆续进入标准 JDK，jcmd（JDK 7）把 VM 级诊断统一到一个入口；JFR（Java Flight Recorder）JDK 11 开源进 OpenJDK，成为低开销的在线采样工具。真正改变线上排查体验的是**阿里巴巴 Arthas**（2018 年开源）——基于 Java Agent 的在线诊断工具，不需要重启进程即可 dashboard 看全局、thread 查线程、jad 反编译线上代码、watch/trace 观测方法入参与返回值，成为国内排查线上问题的标配。

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
- **栈是线程私有的**：每个线程一个虚拟机栈，栈帧随方法调用压栈/出栈——递归无限会 `StackOverflowError`，不是内存泄漏
- **堆是线程共享的**：`new` 出来的对象都在堆上；栈上只存引用（对象地址）
- **元空间用本地内存**：默认没有上限（受系统内存约束），所以动态生成类（代理、热部署）可能悄然吃满内存——生产建议显式 `-XX:MaxMetaspaceSize`

### 3.2 类加载机制：加载·验证·准备·解析·初始化

.class 字节码要变成可运行的对象，必须经过类加载，**完整生命周期五步**：**加载**（读字节流，把类的二进制表示载入元空间，堆中生成 `Class` 对象）→ **验证**（格式/语义检查，防恶意字节码）→ **准备**（静态变量分配内存并赋**默认值**，如 `int` 赋 0）→ **解析**（把常量池中的**符号引用**替换为**直接引用**）→ **初始化**（执行 `<clinit>`，静态变量赋初始值、静态代码块执行）。

```bash
java -XX:+TraceClassLoading Demo   # 观察哪些类被加载（排查类加载问题的利器）
```

- **准备阶段赋的是默认值，初始化阶段才赋真实值**——`static int x = 42;` 在准备阶段 x=0，初始化阶段才变 42
- **初始化是懒触发的**：只有 `new`、访问静态成员、反射、初始化子类等「主动使用」才触发；`final` 常量编译期直接替换，不触发类初始化
- **双亲委派（parent delegation）**：类加载请求先委托父加载器，父加载器找不到才自己加载（详见 4.1）；`ClassNotFoundException` 与 `NoClassDefFoundError` 的区别——前者是找不到类，后者是类**初始化失败**后再次引用

### 3.3 字节码与 class 文件结构入门

`javac` 编译出的 `.class` 文件是 JVM 的指令集，以魔数 `0xCAFEBABE` 开头，结构依次为：常量池（constant pool）、访问标志（access flags）、本类/父类/接口索引、字段表、方法表（`Code` 属性存放字节码指令）、属性表。

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
- 典型指令：`aload_0`（取 this）、`invokevirtual`（调用实例方法）、`getstatic`（取静态字段）——反汇编后这些指令一目了然
- **字节码是「半编译」产物**：与 C++ 的机器码不同，它不针对任何 CPU，由执行引擎解释或 JIT 编译执行

### 3.4 JIT 编译与分层编译（解释·C1·C2）

字节码有两种执行方式：**解释执行**逐条翻译（启动快、执行慢）；**JIT 编译**（Just-In-Time，即时编译）把热点方法编译为本地机器码（启动慢、执行快）。现代 JVM 两者结合，用**分层编译**分五层递进：解释执行（0 层）→ C1 各优化层（1-3 层）→ C2 深度优化（4 层）。方法调用次数超过阈值（`-XX:CompileThreshold`，默认约 10000 次）即成为热点方法，触发升级。

```bash
java -Xint Demo && java -Xcomp Demo   # 纯解释 / 纯编译执行（对比性能用，生产别用）
java -XX:+PrintCompilation Demo       # 打印 JIT 编译了哪些方法（看热点方法）
```
- **线上服务刚启动「慢热」**：热点方法还没编译完，性能低于稳态——压测前先预热，这是「压测数字忽高忽低」的常见原因
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
- 堆按代划分：**新生代（Young）** = Eden + 两个 Survivor（S0/S1，默认比例 8:1:1，`-XX:SurvivorRatio`）；**老年代（Old）** 存长期存活对象
- 对象在新生代出生，熬过多次 **Minor GC** 后**晋升（promotion）**到老年代（`-XX:MaxTenuringThreshold` 控制阈值，默认 15；另有动态年龄判定）；**大对象**直接进老年代（G1 下为巨型对象 humongous，直接占 Region）
- **GC 自动回收 ≠ 没有内存问题**：泄漏的对象仍被 GC Root 链引用，GC 永远回收不了它——这是本阶段必会概念，也是 3.11 堆 dump 分析的前提

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
- G1 下新生代回收叫 **Young GC**，老年代回收是**混合回收（Mixed GC）**——没有传统意义上的 Full GC 语义

### 3.7 常见收集器对比（Serial·Parallel·CMS·G1·ZGC）

| 收集器 | 策略 | 停顿 | 适用/状态 |
|--------|------|------|-----------|
| Serial | 单线程，串行回收 | 长 | 客户端、单核小内存；`-XX:+UseSerialGC` |
| Parallel | 多线程并行回收，**吞吐优先** | 较长 | JDK 8 默认；批处理、计算型任务 |
| CMS | 并发标记-清除，低停顿 | 短但碎片化 | JDK 9 弃用、JDK 14 移除，**新代码勿用** |
| G1 | Region 化，可预测停顿 | 可控（`-XX:MaxGCPauseMillis`） | **JDK 9+ 默认**，大堆服务端首选 |
| ZGC | 染色指针+读屏障，并发整理 | 亚毫秒级 | JDK 15+ 正式；超大堆、超低延迟场景 |

```bash
java -XX:+UseG1GC -XX:MaxGCPauseMillis=200 -jar app.jar   # 明确使用 G1 并设停顿目标
java -XX:+UseZGC -Xmx16g -jar app.jar                      # 超大堆低延迟场景用 ZGC
```
- **G1 是当前默认与主流**：把堆划分为约 2048 个 Region，回收时优先回收「垃圾最多」的区域（Garbage First 得名），通过 `-XX:MaxGCPauseMillis` 让停顿可预期
- **选型口诀**：追求吞吐（批处理）用 Parallel；追求低延迟（在线服务）用 G1；延迟极度敏感且堆很大再考虑 ZGC
- 收集器只能**配对使用**（新生代/老年代组合），G1/ZGC 是整堆的；不要盲调参数，先用默认收集器跑出 GC 日志再决策

### 3.8 JVM 参数（堆大小·GC 选择·日志参数）

JVM 参数分三类：`-X` 非标准参数（`-Xms`/`-Xmx`/`-Xss`/`-Xmn`）、`-XX` 高级参数（布尔型 `-XX:+UseG1GC` 开启、`-XX:-UseG1GC` 关闭；数值型 `-XX:MaxMetaspaceSize=256m`）、普通参数（`-Dkey=value` 系统属性）。

| 参数 | 作用 | 示例 |
|------|------|------|
| `-Xms` / `-Xmx` | 堆初始 / 最大大小 | `-Xms512m -Xmx512m`（生产建议相等，避免扩容抖动） |
| `-Xmn` / `-XX:NewRatio` | 新生代大小 / 新生代:老年代比例 | `-Xmn256m`、`-XX:NewRatio=2` |
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
- **坑：堆设太大未必好**——堆越大 GC 停顿越长；容器部署还要注意 cgroup 内存限制（`-XX:MaxRAMPercentage` 按比例取堆，JDK 8u191+ 默认容器感知）
- 查看当前生效参数：`jcmd <pid> VM.flags` 或 `java -XX:+PrintFlagsFinal -version`

### 3.9 诊断工具（jps·jstack·jmap·jstat·jcmd·Arthas）

JDK 自带工具是排查第一梯队，Arthas 是进阶利器：

| 工具 | 用途 | 常用命令 |
|------|------|---------|
| jps | 查看 Java 进程（JVM Process Status） | `jps -lv`（-v 显示启动参数） |
| jstack | 线程 dump（thread dump） | `jstack <pid> > thread.txt` |
| jmap | 堆信息、导出堆快照 | `jmap -histo <pid>`、`jmap -dump:format=b,file=h.hprof <pid>` |
| jstat | 实时 GC 统计 | `jstat -gcutil <pid> 1000`（每秒一次） |
| jcmd | 统一诊断入口（JDK 7+） | `jcmd <pid> help`、`jcmd <pid> Thread.print` |
| Arthas | 在线诊断，免重启 | `java -jar arthas-boot.jar` 后 `dashboard` / `thread` / `watch` / `trace` / `jad` |

```bash
jps -l                      # 1. 找到目标进程 pid
jstat -gcutil <pid> 1000    # 2. 看 GC 健康度（S0/S1/E/O/M 各区使用率 + YGC/FGC 次数）
jstack <pid> > thread.txt   # 3. 线程 dump 到文件，供分析
jmap -dump:format=b,file=heap.hprof <pid>   # 4. 导出堆快照（大堆会暂停，注意时机）
```
- **Arthas 的核心价值是「免重启」**：`thread -n 3` 找 CPU 最高线程、`watch com.x.Service method` 观测方法入参返回值、`jad com.x.Service` 反编译线上代码、`trace` 打方法耗时——改不了代码的线上问题它都能看
- 工具需要目标进程的**同用户权限**；容器里先 `docker exec` 再执行；`jcmd <pid> GC.heap_dump h.hprof` 可替代 jmap 导出

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
- **jstack 检测死锁直接给出答案**：输出 `Found one Java-level deadlock` 并列出两个线程互相等待的锁与持有者（见示例 2）
- **大量 `BLOCKED` 线程堆积 = 锁竞争或死锁**；`WAITING` 多且 `parking to wait` 频繁则查线程池配置与 `LockSupport`
- 线程 dump 是**快照**，建议间隔几秒抓 2-3 份对比，判断线程是「短暂等待」还是「一直卡住」

### 3.11 堆 dump 与内存泄漏分析（MAT/jhat）

**堆 dump（heap dump）** 是堆中所有对象与引用关系的快照，用于回答「内存被谁占着、为什么回收不掉」。内存泄漏（memory leak）指对象已无用但仍被 GC Root 链引用——GC 永远回收不了，堆持续上涨直至 OOM。

```bash
jmap -dump:format=b,file=heap.hprof <pid>     # 导出堆快照（或 jcmd <pid> GC.heap_dump heap.hprof）
jmap -histo <pid> | head -20                  # 先快速看对象直方图：哪些类实例最多、占内存最大
# MAT：File → Open Heap Dump → Leak Suspects 报告 → Dominator Tree → Path to GC Roots 沿引用链找持有者
```
- **Leak Suspects 报告**直接给出「一个对象持有 X MB 内存，被 XX 引用」，双击即可沿引用链找到泄漏源头（通常是某个静态集合）
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
| 上线不开 GC 日志与 OOM 转储 | 故障后无据可查 | 生产默认 `-Xlog:gc*` + `-XX:+HeapDumpOnOutOfMemoryError` |

## 4. 底层原理

### 4.1 类加载的双亲委派与类卸载

JDK 9 起的类加载器层级：**启动类加载器（Bootstrap）**（C++ 实现，加载 `java.base` 等核心模块）→ **平台类加载器（Platform）**（替代旧扩展类加载器，加载 `java.sql` 等平台模块）→ **应用类加载器（Application）**（加载 classpath 下的应用类）。**双亲委派（parent delegation）**：类加载请求沿层级**自下而上**委托，父加载器能加载就交给父，父加载不了才由自己加载。

```
请求加载 com.example.Demo → 委托 Application → Platform → Bootstrap
  → Bootstrap 能加载 java.base 核心类则由其加载 → 找不到则逐级回退 → Application 从 classpath 加载
```
- **双亲委派的意义**：避免同一个类被不同加载器重复加载（类身份 = 类名 + 定义它的加载器）；**保护核心类**——自定义的 `java.lang.String` 永远不会被 Bootstrap 之外的加载器加载，防止污染核心库
- **打破双亲委派**：**线程上下文类加载器（Thread Context ClassLoader）**——JDBC 等 SPI 场景由 Bootstrap 加载核心接口，但实现类（MySQL 驱动）在应用 classpath，必须让应用类加载器反向加载；`ServiceLoader` 就是典型
- **类卸载**：类由加载它的 ClassLoader 卸载，前提是该加载器不可达且其加载的所有类均不可达——**自定义 ClassLoader + 不释放 = 元空间泄漏**（热部署/动态代理频繁生成类正是元空间 OOM 的元凶）

### 4.2 对象头与内存布局（Mark Word·Klass Pointer·对齐）

堆中一个普通对象由三部分组成：**对象头（Object Header）** + **实例数据** + **对齐填充**（64 位 JVM 对象大小按 8 字节对齐）。

对象头又分两部分：
- **Mark Word**：64 位（未压缩时），存储**锁状态**（无锁/偏向锁/轻量级锁/重量级锁）、身份哈希码（identity hashcode）、**GC 分代年龄**（4 bit）、偏向线程 ID——ph09 的 synchronized 锁升级就是改写 Mark Word
- **Klass Pointer（类型指针）**：指向元空间中的类元数据；默认开启**压缩指针（compressed oops）**时占 4 字节（堆 ≤ 32G），关闭或堆更大时 8 字节；数组对象还有 4 字节**长度字段**

- **Mark Word 是「多功能复用区」**：同一块空间在不同时刻存不同信息——无锁时存哈希码+年龄，轻量级锁时存锁记录指针，重量级锁时存 monitor 指针
- 对象头开销可观：一个空 `Object` 在 64 位 JVM 上是 16 字节（Mark Word 8 + Klass Pointer 4 + 对齐 4）——**几百万个小对象会吃掉大量内存**，这是「对象数量膨胀」类 OOM 的物理原因；开启 `-XX:+UseCompressedOops`（默认）能显著降低引用内存占用

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
- **栈上分配不是语言保证，而是 JIT 优化**：`-XX:+DoEscapeAnalysis`（JDK 8 默认开启）、`-XX:+PrintEscapeAnalysis` 可观察；对象被返回、存入全局/静态结构、传入其他线程即「逃逸」，优化失效
- 这就是为什么「循环里 `new` 对象」在 JVM 上通常并不可怕——逃逸分析兜底；但**逃逸对象**（如塞进静态集合）仍要进堆、走 GC

### 4.5 OOM 的类型与触发场景

`OutOfMemoryError` 不是一个异常而是一族，类型不同、根因不同、排查路径不同：

| OOM 类型 | 触发场景 | 排查思路 |
|----------|---------|---------|
| `Java heap space` | 堆满：堆太小或内存泄漏 | 堆 dump + MAT 定位泄漏或扩容 |
| `GC overhead limit exceeded` | GC 占用超过 98% 时间且回收不到 2% 堆 | 堆 dump：通常也是泄漏，先找谁在疯狂分配 |
| `Metaspace` | 类元数据占满（动态代理/热部署/反射） | `jstat -gcutil` 看 M 列；排查动态生成类；设 `-XX:MaxMetaspaceSize` |
| `unable to create new native thread` | 线程数超 OS/容器限制（线程泄漏） | `ulimit -u`、`ps -eLf | wc -l` 数线程；查线程池 |
| `Direct buffer memory` | NIO 直接内存泄漏（ByteBuffer 未释放） | `-XX:NativeMemoryTracking=summary` 跟踪本地内存 |

- **GC overhead limit exceeded 是「堆快满且回收无果」的强信号**——通常意味着泄漏对象已占满堆，GC 每次只能回收一点点
- **OOM 排查第一原则：先留证据再重启**——`-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=...` 让 OOM 自动落盘 hprof，否则一重启现场就没了

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 线上 CPU 飙高 | `top -Hp` + `jstack` 定位热点线程与代码行 |
| 服务卡死、接口超时 | 线程 dump：`BLOCKED`/`WAITING` 分析、死锁检测 |
| 内存持续上涨、频繁 Full GC | `jstat -gcutil`、GC 日志、堆 dump + MAT |
| 应用启动/运行报 OOM | OOM 类型识别（4.5）+ `HeapDumpOnOutOfMemoryError` 留证 |
| 新服务上线配 JVM 参数 | `-Xms/-Xmx`、G1、停顿目标、GC 日志（3.8 参考命令） |
| 线上无法加日志排查问题 | Arthas：dashboard/thread/watch/trace/jad 免重启观测 |

**不适合**此阶段的事项：
- **构建工程化、依赖管理、多模块工程、CI 集成**——Maven/Gradle 属于 ph11 构建工具阶段
- **JVM 调优在 Spring 生态的实践**（Spring Boot 启动优化、连接池与 JVM 联动、Actuator 监控指标）——留到 ph15 Web 框架阶段
- **分布式环境下的内存与并发问题**（分布式锁、分布式缓存、跨进程故障）——留到 ph16 分布式阶段

## 6. 代码示例

### 示例 1：查看 Java 进程（jps + jstack 读取线程状态）—— Java 9+

对应 roadmap 练习「查看 Java 进程」：写一个持续运行的程序，用 jps 找到它，用 jstat 看 GC、jstack 看线程。
```java
public class BusyProcess {
    public static void main(String[] args) throws Exception {
        System.out.println("PID = " + ProcessHandle.current().pid());   // 打印自身 pid
        long sum = 0;
        for (int i = 0; ; i++) {                        // 持续计算，保持进程存活
            for (long j = 0; j < 1_000_000L; j++) sum += j;
            if (i % 10 == 0) System.out.println("第 " + i + " 轮计算完成");
            Thread.sleep(200);
        }
    }
}
```
```bash
javac BusyProcess.java && java BusyProcess &   # 编译并后台运行，记住输出的 PID
jps -l && jps -lv             # -l 列出进程（主类名）；-v 附带启动参数
jstack <pid> | head -30       # 线程 dump：能看到 main 线程 RUNNABLE 在执行我们的循环
jstat -gcutil <pid> 1000      # 每秒输出一次 GC 统计
```
```
jstat -gcutil 输出解读：S0/S1 = Survivor 使用率、E = Eden、O = 老年代、M = 元空间；
YGC/FGC = Young/Full GC 次数，YGCT/FGCT/GCT = 累计耗时（秒）
```
提示：`jps` 找不到进程时检查是否已退出、是否同用户权限；`jcmd <pid> help` 可以查看所有可用诊断命令，是 jps 之外的统一入口。

### 示例 2：死锁定位（构造死锁程序 + jstack 输出分析）

对应 roadmap 练习「分析线程死锁」与必会概念「线程 dump 可定位死锁和阻塞」：两个线程以相反顺序抢两把锁，必然死锁。
```java
public class DeadlockDemo {
    static final Object LOCK_A = new Object();
    static final Object LOCK_B = new Object();
    public static void main(String[] args) throws Exception {
        Thread t1 = new Thread(() -> {
            synchronized (LOCK_A) {                    // t1 先拿 A
                sleep(50);
                synchronized (LOCK_B) { System.out.println("t1 拿到两把锁"); }
            }
        }, "worker-1");
        Thread t2 = new Thread(() -> {
            synchronized (LOCK_B) {                    // t2 先拿 B
                sleep(50);
                synchronized (LOCK_A) { System.out.println("t2 拿到两把锁"); }
            }
        }, "worker-2");
        t1.start();
        t2.start();
        t1.join();
        t2.join();      // 程序卡死：两个线程互相等待，谁也拿不到第二把锁
    }
    static void sleep(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }
}
```
```bash
javac DeadlockDemo.java && java DeadlockDemo &   # 编译并后台运行，程序将卡死
jps -l && jstack <pid>                            # 找到 pid 后线程 dump，直接给出死锁结论
```
```
jstack 关键输出（节选）：
Found one Java-level deadlock:
=============================
"worker-1": waiting to lock monitor ... which is held by "worker-2"
"worker-2": waiting to lock monitor ... which is held by "worker-1"
```
提示：死锁四条件（互斥、持有并等待、不可剥夺、循环等待）——示例正好满足全部四条；修复方法是**统一加锁顺序**（都先拿 A 再拿 B）或 `tryLock` 超时。`jstack <pid> > thread.txt` 存文件后，用 `grep -A 20 "Found one Java-level deadlock" thread.txt` 提取结论。

### 示例 3：堆 dump 与内存泄漏分析（制造泄漏 + jmap 导出 + MAT 思路）

对应 roadmap 练习「导出 heap dump」、必会概念「堆 dump 可分析内存泄漏」与推荐项目「内存泄漏 demo」：静态集合持续持有对象，制造典型泄漏。
```java
import java.util.ArrayList;
import java.util.List;
public class LeakDemo {
    static final List<byte[]> CACHE = new ArrayList<>();   // 静态集合：GC Root 可达，永不回收
    public static void main(String[] args) throws Exception {
        int i = 0;
        while (true) {
            CACHE.add(new byte[1024 * 1024]);   // 每轮 1MB 且一直被静态集合持有
            if (++i % 50 == 0) System.out.println("已累计 " + i + " MB，进程仍在运行");
            Thread.sleep(10);
        }
    }
}
```
```bash
javac LeakDemo.java && java -Xms256m -Xmx256m LeakDemo &   # 编译运行，限制堆让泄漏更快暴露
jps -l && jmap -histo <pid> | head -20    # 找 pid；直方图里 byte[] 必然异常突出
jmap -dump:format=b,file=leak.hprof <pid> # 导出堆快照（或 jcmd <pid> GC.heap_dump leak.hprof）
# MAT：File → Open Heap Dump → Leak Suspects 报告 → Dominator Tree → Path to GC Roots 沿引用链看到 LeakDemo.CACHE
```
提示：泄漏根源是**静态集合 CACHE**——静态字段是 GC Root，`add` 进去的对象永远可达。对比练习：把 `CACHE` 改为普通局部变量后程序会在方法结束前一直涨、结束后可回收（试试换 `-Xmx64m` 触发 OOM）。线上排查顺序：`jstat -gcutil` 确认老年代持续上涨 → `jmap -histo` 快速定位类 → 堆 dump 用 MAT 沿引用链找持有者。

### 示例 4：GC 日志查看（-Xlog:gc 参数 + 解读 Minor/Full GC）

对应 roadmap 练习「查看 GC 日志」：程序频繁创建短命对象触发 Minor GC，观察 GC 日志格式与含义。
```java
import java.util.ArrayList;
import java.util.List;
public class GCLogDemo {
    public static void main(String[] args) {
        List<byte[]> keep = new ArrayList<>();       // 少量长命对象（防 OOM）
        int i = 0;
        while (i < 300) {
            for (int j = 0; j < 100; j++) {
                new byte[64 * 1024];                 // 大量短命对象 → 触发 Minor GC
            }
            if (i % 100 == 0) keep.add(new byte[1024 * 1024]);   // 少量对象晋升老年代
            i++;
        }
    }
}
```
```bash
# JDK 9+：统一日志 -Xlog
java -Xms128m -Xmx128m -Xlog:gc* GCLogDemo
# JDK 8 及以前：PrintGCDetails + 输出到文件
java -Xms128m -Xmx128m -XX:+PrintGCDetails -XX:+PrintGCDateStamps -Xloggc:gc.log GCLogDemo
```
```
JDK 9+ 日志片段解读：
[0.032s][info][gc,start] GC(0) Pause Young (Normal) (Allocation Failure)  ← Minor GC，因分配失败触发
[0.034s][info][gc      ] GC(0) Pause Young (Normal) 24M->2M(128M) 2.1ms   ← 堆 24M→2M，停顿 2.1ms
```
提示：日志中 `Pause Young` 是 Minor GC，`Pause Full` 是 Full GC——**Full GC 出现且频繁 = 必须排查**（老年代满/元空间满/显式 GC）。关注三个数字：GC 频率（每秒几次）、每次停顿时长（ms）、堆回收前后用量（24M->2M）。生产用 `-Xlog:gc*:file=gc.log` 落盘，配合 `GCViewer` 等工具看趋势。

### 示例 5：OOM 复现与 JVM 参数（-Xmx 限制 + 异常类型识别）

对应 roadmap 练习「查看 GC 日志」延伸与必会概念「GC 自动回收但不等于没有内存问题」：用 `-Xmx` 限制堆，复现并识别 OOM，验证自动堆转储。
```java
import java.util.ArrayList;
import java.util.List;
public class OomDemo {
    public static void main(String[] args) {
        List<byte[]> list = new ArrayList<>();
        int i = 0;
        while (true) {
            list.add(new byte[1024 * 1024]);     // 每次 1MB，永不释放
            System.out.println("已分配 " + (++i) + " MB");
        }
    }
}
```
```bash
javac OomDemo.java
java -Xms32m -Xmx32m -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=. OomDemo
```
```
运行输出（末尾）：
...
Exception in thread "main" java.lang.OutOfMemoryError: Java heap space
	at OomDemo.main(OomDemo.java:7)
// 且当前目录自动生成堆快照 java_pid<pid>.hprof（-XX:+HeapDumpOnOutOfMemoryError 生效）
```
提示：异常类型是 `Java heap space`——堆被 `list` 撑满。把代码换成「动态生成类」（如 `Proxy` 代理）会得到 `Metaspace`；用 `ExecutorService` 无限提交任务再配合 `-Xmx` 可得到 `unable to create new native thread`——**先认出 OOM 类型，再决定排查方向**（4.5 表格）。修复思路：`list` 是局部变量却逃逸进了堆并持续增长，本质与示例 3 相同——对象被持有且不断新增。

## 7. 总结

### 关键要点

1. **Java 代码先编译成 class 字节码再在 JVM 上运行**——javac → 字节码（`0xCAFEBABE` 魔数）→ 类加载 → 执行引擎（解释 + JIT）
2. **运行时数据区五大区域**——程序计数器、虚拟机栈、本地方法栈、堆、方法区（JDK 8+ 实现为元空间，用本地内存）
3. **类加载五步**——加载、验证、准备、解析、初始化；**双亲委派**保护核心类、避免重复加载，可被线程上下文类加载器打破
4. **GC 自动回收但不等于没有内存问题**——泄漏对象仍被 GC Root 可达，GC 永远回收不了；静态集合、连接未关是高发原因
5. **对象存活靠 GC Roots + 可达性分析判断**——分代收集：新生代复制算法（Minor GC），老年代标记-清除/标记-整理（Full GC）
6. **Minor GC 频繁且正常，Full GC 频繁必有妖**——老年代/元空间满、显式 GC 都会触发；Full GC 停顿秒级，是线上卡顿第一嫌疑
7. **线程 dump（jstack）可定位死锁和阻塞**——`Found one Java-level deadlock` 直接给出互相等待的线程与锁
8. **堆 dump（jmap + MAT）可分析内存泄漏**——Leak Suspects 报告 + Dominator Tree + Path to GC Roots 沿引用链直达持有者
9. **JVM 参数三件套起步**——`-Xms/-Xmx` 相等、`-XX:+UseG1GC`、`-XX:+HeapDumpOnOutOfMemoryError`（+ `-Xlog:gc*` 留日志）
10. **Arthas 让线上排查免重启**——dashboard/thread/watch/trace/jad 覆盖「改不了代码」的场景

### 跨语言对比：运行时与内存管理

| 维度 | JVM（Java） | Go runtime | Python CPython | C++ 手动 | Rust 所有权 |
|------|------------|-----------|----------------|----------|-------------|
| 代码形态 | class 字节码 → JIT 机器码 | 直接编译为机器码 | `.pyc` 字节码 → 解释执行 | 机器码 | LLVM IR → 机器码 |
| 内存管理 | 分代 GC（G1/ZGC） | 并发三色标记 GC | 引用计数 + 分代 GC | 手动 `new`/`delete` | **编译期所有权 + 借用检查** |
| 运行时数据区 | 栈/堆/方法区（元空间）/程序计数器 | 栈/堆（TCMalloc） | 栈/堆 + GIL | 栈/堆（开发者管理） | 栈/堆（所有权模型） |
| GC 停顿 | 可控（G1 目标毫秒级、ZGC 亚毫秒） | 毫秒级，并发标记 | 停顿小但整体性能低 | 无 GC（手动） | 无 GC（编译期） |
| 内存问题排查 | jps/jstack/jmap/jstat/jcmd/Arthas/MAT | pprof | tracemalloc/memray | valgrind/ASan | 编译期拒绝，运行时极少内存错误 |

对比结论：JVM 与 Go 都靠 GC 自动管理，区别在于 JVM 的停顿可配置可预测（G1/ZGC）、工具链最完整；CPython 的引用计数简单但受 GIL 与性能限制；C++ 把内存控制权交给开发者，换来性能但泄漏与悬垂指针风险高；Rust 用所有权模型把内存安全前移到编译期，代价是学习曲线——JVM 生态的独特优势是「**GC + 完备诊断工具**」的组合，这也是本阶段 jstack/jmap/MAT 价值的所在。

### 阶段验收标准

- 能解释 JVM 运行流程：源码 → 字节码 → 类加载（加载·验证·准备·解析·初始化）→ 执行引擎（解释/JIT）→ GC
- 能说出运行时数据区五大区域及职责（程序计数器/虚拟机栈/本地方法栈/堆/方法区-元空间）
- 能使用基础诊断工具（jps、jstack、jmap、jstat、jcmd，含 Arthas 常用命令），能解读 GC 日志区分 Minor/Full GC、识别常见 OOM 类型
- 能用线程 dump 定位死锁和阻塞，用堆 dump（MAT）分析内存泄漏
- 能说出常见 JVM 参数（`-Xms/-Xmx`、GC 选择、日志与 OOM 转储）并给出生产参考配置

### 进入下一阶段前

确保能完成以下练习：
- **查看 Java 进程**：启动自己的程序，用 `jps -l` 找到 pid，用 `jstat -gcutil` 观察各区使用率（提示：`jps -v` 看启动参数；找不到进程先查是否同用户权限、是否已退出）
- **分析线程死锁**：写一个两线程两锁交叉获取的程序，`jstack` 输出中定位 `Found one Java-level deadlock`（提示：加 `Thread.sleep` 放大窗口；先统一加锁顺序验证修复）
- **导出 heap dump**：用 `jmap -dump:format=b,file=h.hprof <pid>` 导出快照，用 MAT 打开并查看 Leak Suspects（提示：`jcmd <pid> GC.heap_dump h.hprof` 是等价替代；大堆导出会暂停应用，注意时机）
- **查看 GC 日志 + OOM 复现**：`-Xlog:gc*`（JDK 9+）输出 GC 日志并区分 Minor/Full GC；再用 `-Xmx32m` 跑示例 5 复现 `Java heap space`（提示：加 `-XX:+HeapDumpOnOutOfMemoryError` 自动留证；GCViewer 可画日志趋势）

### 推荐项目

- **JVM 问题排查笔记**：从本阶段练习出发，把每次排查写成「现象 → 诊断命令与输出 → 根因 → 解决 → 预防」的笔记（Markdown），积累 jstack/jmap/jstat/GC 日志/Arthas 的实战案例，形成自己的线上排查手册
- **内存泄漏 demo**：实现 2-3 种典型泄漏（静态集合、连接未关、ThreadLocal 未 remove），分别用 `jstat` 观察老年代上涨、`jmap -histo` 找可疑类、堆 dump + MAT 定位持有者，并给出修复前后的对比与预防清单

### 下一阶段

[Maven / Gradle 与工程化阶段](../ph11-build-tooling/11-build-tooling.md) —— 构建工具、依赖管理、多模块工程、CI 集成。
