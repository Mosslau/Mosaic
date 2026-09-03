# ex07 GC 日志演示：GcLogDemo + 日志解读

> 程序周期性制造「大量一次性大对象 + 少量存活」，配合 `-Xlog` 采集真实 GC 日志，练习「读日志 → 判断回收类型与停顿 → 反推内存行为」。程序仅做分配，分析靠下面的日志文件。

## 验证状态

**已验证**（OpenJDK 17.0.18，G1 默认收集器）：本机运行采集到 521 行 info 级日志，其中 **Pause Young 140 次、Pause Full 0 次**——证明示例程序对 48MB 堆的内存压力全部由 Young GC 消化，无 Full GC 停顿。

## 复现命令

```bash
# 1. 编译
/opt/homebrew/opt/openjdk@17/bin/javac -encoding UTF-8 -d /tmp/tl20-cls GcLogDemo.java

# 2. info 级日志（够用，推荐）
/opt/homebrew/opt/openjdk@17/bin/java -Xms48m -Xmx48m "-Xlog:gc:file=/tmp/gc-demo.log" \
    -cp /tmp/tl20-cls GcLogDemo

# 3. debug 级日志（含 region/TLAB/age 明细，用于深挖）
/opt/homebrew/opt/openjdk@17/bin/java -Xms48m -Xmx48m "-Xlog:gc*=debug:file=/tmp/gc-debug.log" \
    -cp /tmp/tl20-cls GcLogDemo
```

日志文件用 `cat /tmp/gc-demo.log` 查看，统计用 `grep -c 'Pause Young' /tmp/gc-demo.log`。

## 本机采集的真实样例与逐段解读

### ① 汇总行（info 级，一行讲清一次停顿）

```text
[0.108s][info][gc] GC(0) Pause Young (Concurrent Start) (G1 Humongous Allocation) 21M->21M(48M) 0.588ms
```

| 字段 | 含义 |
|------|------|
| `[0.108s]` | JVM 启动后第 0.108 秒（与墙钟无关，用于定位慢在哪） |
| `GC(0)` | 本次停顿序号（从 0 数，全进程唯一） |
| `Pause Young` | **Stop-The-World 的 Young GC**（G1 中年轻代回收） |
| `(Concurrent Start)` | 该次 Young GC 顺带发起了并发标记周期（G1 的旧生代回收前置） |
| `(G1 Humongous Allocation)` | **触发原因：巨型对象分配失败**（见下） |
| `21M->21M(48M)` | 堆占用：回收前 21MB → 回收后 21MB（括号=堆总容量 48MB）。**回收后没下降**说明本次清理的是大量 humongous 区里的死对象但被存活大对象占着，或腾挪后总量未变——量变看多次 GC 的趋势 |
| `0.588ms` | 本次 STW 停顿耗时（核心指标：这里都 <3ms，无问题） |

### ② 触发原因为什么是 Humongous

本程序每轮 `new byte[1024 * 1024]`——**1MB 对象超过了 G1 region（1024KB）的一半**，G1 按「巨型对象」处理：直接整块放进连续 humongous region，不进入普通 young 区，其分配失败会直接触发一次 Young GC：

```text
[0.066s][debug][gc,heap] GC(0) region size 1024K, 1 young (1024K), 0 survivors (0K)
```

`region size 1024K` 就是 G1 把 48MB 堆切成约 48 个 region 的证据（G1 的堆 = 等尺寸 region 网格，ph20 主文档 3.1 的 Region 结构在此可见）。

### ③ debug 明细：GC 前后各线程/区域状态（挑有用的看）

```text
[0.066s][debug][gc,heap] GC(0) Heap before GC invocations=0 (full 0): garbage-first heap total 49152K, used 21408K
[0.066s][debug][gc,task ] GC(0) Using 2 workers of 11 for evacuation   ← 用了 2 个 GC 线程做复制
[0.066s][debug][gc,age  ] GC(0) Desired survivor size 1572864 bytes, new threshold 15
```

- `invocations=0 (full 0)`：GC 序号与 Full 次数——`(full N)` 为 0 表示从未 Full GC，健康。
- `new threshold 15`：对象在 survivor 区熬过 15 次 Young GC 才升入 old（年龄阈值）。

### ④ 并发标记周期（Concurrent Mark Cycle，G1 回收 old 区的铺垫）

```text
[0.068s][info][gc] GC(1) Concurrent Mark Cycle
```

GC(0) 之后的并发标记不 STW，逐阶段输出在 debug 日志里。**看到 `Concurrent Mark Cycle` 不等于 old 区回收**——只有后续出现 `Pause Young (Mixed)` 才真的回收 old region。

## 怎么判断一次 GC 是否值得担心

| 观察点 | 健康信号 | 告警信号 |
|--------|---------|---------|
| 停顿耗时 | 每次 < 几十 ms 且平稳 | 突增或持续 >100ms（G1 默认目标 200ms，超过要调） |
| `(full N)` | 恒为 0 | 持续增长 = 老年代回收不掉 = 内存泄漏或堆过小 |
| 回收后堆占用 | 波动后回到低水位 | 持续走高趋近 `(上限)`——堆不够或对象逃逸进 old |
| Humongous 占比 | 偶发 | 频繁 = 大数组/大缓存分配频繁，容易碎片化 |

## 线上对照：为什么 ph19 只用 `-XX:MaxRAMPercentage` 而这里要看日志

ph19（容器部署）只回答了「把 75% 配额给 JVM」，**没回答给完够不够用**——判断「够不够」就要读这类 GC 日志与堆占用曲线（主文档 3.1 与 4.2）。日志里 `21M->21M(48M)` 的「回收前后」和「距上限的距离」就是最原始的堆内外曲线素材；再往上就是 jstat/JMX/Arthas 的实时曲线（ph10 已讲工具用法，本阶段只讲读法与机制）。
