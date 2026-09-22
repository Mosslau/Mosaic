# ph10 阶段项目：内存泄漏实验台（Memory Leak Lab）

## 需求

对应 Roadmap「ph10 JVM 阶段」推荐项目第二个「内存泄漏 demo」：实现 **2~3 种典型内存泄漏**，分别用 `jstat` 观察老年代上涨、`jmap -histo` 找可疑类、堆 dump + MAT 定位持有者，并给出修复前后的对比与预防清单。项目覆盖本阶段核心知识点：GC Roots 与可达性分析（3.5）、静态集合泄漏（3.12）、ThreadLocal 泄漏（3.12）、连接未关闭（3.12）、`jmap -histo` 快速定位（3.11）、堆 dump 分析路径（3.11）、`-Xmx` 与 OOM 类型识别（3.8 / 4.5）。

Roadmap 推荐项目第一个「JVM 问题排查笔记」（把每次排查写成「现象 → 诊断命令与输出 → 根因 → 解决 → 预防」的 Markdown）作为**扩展方向**给出（见下），本仓库落地的代码项目是第二个。

## 文件结构

| 文件 | 类 | 职责 |
|------|----|------|
| memory-leak-lab.java | MemoryLeakLab | 实验台：`static` / `threadlocal` / `conn` 三种泄漏模式 + `clean` 对照组，按模式运行到指定量后保持存活供诊断 |

## 功能清单

- [ ] 泄漏模式 1（static）：静态集合 `STATIC_CACHE` 持续 add 1MB 对象——静态字段是 GC Root，对象永远可达
- [ ] 泄漏模式 2（threadlocal）：8 线程池 + 每任务新建 `ThreadLocal` 塞 1MB 且**不 remove**——任务结束后值仍被工作线程的 ThreadLocalMap 持有
- [ ] 泄漏模式 3（conn）：模拟连接未关闭——「打开」的连接持有 1MB 缓冲、永不 `close`，被静态开放列表持有（句柄与内存双泄漏的简化模型）
- [ ] 对照组（clean）：同样每轮分配 1MB 但立即丢弃引用——300 轮正常结束、无 OOM，用于对比「泄漏 vs 正常」
- [ ] 通用骨架：每模式分配到目标 MB 后**保持存活约 60 秒**供诊断（jstat / jmap -histo / 堆 dump），之后继续分配直至 OOM
- [ ] 打印自身 pid 与启动参数（`ProcessHandle.current().pid()` / `RuntimeMXBean`）
- [ ] 参数校验：未知模式抛 `IllegalArgumentException` 并列出可选模式

## 验收标准

- `javac memory-leak-lab.java` 编译零错误（OpenJDK 17.0.18）
- `java -Xms256m -Xmx256m MemoryLeakLab clean 60` 正常运行结束（无 OOM），打印「300 轮完成」
- 三种泄漏模式运行时 `jmap -histo <pid> | head -6` 中 `[B`（byte[]）的实例数与字节数**远超其他类**（本机实测均约 9700 实例 / 42.5MB，见下）；`jstat -gcutil` 可见老年代占比持续上涨
- 用 `jmap -dump:format=b,file=heap.hprof <pid>`（或 `jcmd <pid> GC.heap_dump heap.hprof`）导出快照，MAT 打开后 Leak Suspects / Dominator Tree / Path to GC Roots 能沿引用链找到持有者：
  - static 模式 → 持有者是 `MemoryLeakLab.STATIC_CACHE`（静态字段是 GC Root）
  - threadlocal 模式 → 持有者是工作线程（`leak-worker-N`）的 `ThreadLocalMap` 条目
  - conn 模式 → 持有者是 `MemoryLeakLab.OPEN_CONNECTIONS` 列表中的 `FakeConnection`
- 运行无 `.class`/日志/hprof 残留仓库内（产物清理命令见下）

## 实测输出（本机 OpenJDK 17.0.18 验证）

三种泄漏模式在 `-Xms256m -Xmx256m` 下运行至 40MB 保持存活时，`jmap -histo` 前几行（实例数/字节数随机器波动，模式固定）：

```text
 num     #instances         #bytes  class name (module)
-------------------------------------------------------
   1:          9728       42546360  [B (java.base@17.0.18)     ← byte[] 占绝对大头
   2:          1567        1120520  [I (java.base@17.0.18)
   3:          8404         201696  java.lang.String (java.base@17.0.18)
```

- static / threadlocal / conn 三种模式的 histo 形态一致（byte[] 42.5MB 左右居首），区别在 MAT 沿引用链看到的**持有者不同**——这正是「堆 dump 定位持有者」的价值
- `jstat -gcutil` 观察（static 模式实测）：`O`（老年代）列随泄漏持续上涨（40MB 保持期实测 O≈38% 且单调增加，数字随机器波动）
- clean 对照组：300 轮分配正常结束，无 OOM

## 扩展方向

- **JVM 问题排查笔记**（Roadmap 推荐项目第一个）：把练习 1~4 与本项目三种泄漏的排查过程各写成一篇「现象 → 诊断命令与输出 → 根因 → 解决 → 预防」Markdown 笔记，沉淀自己的线上排查手册——这是把本阶段工具链内化的最佳方式
- **修复对比**：给每种泄漏加一个修复版开关（static 换局部变量 / threadlocal 加 `finally { tl.remove(); }` / conn 加 try-with-resources），用 `jstat` 对比修复前后老年代曲线
- **OOM 自动留证**：启动参数加 `-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/tmp`，验证「先留证据再重启」的排查第一原则（主文档 4.5）
- **接入 GC 日志**：`-Xlog:gc*:file=gc.log` 观察 Full GC 频率随泄漏的变化，衔接 GC 日志解读（主文档 3.6 / 3.8）

## 验证环境与命令

- 工具链：OpenJDK 17.0.18（Homebrew，`javac -version` → 17.0.18），jps/jstat/jmap/jcmd 为 JDK 自带
- 编译：`javac memory-leak-lab.java`
- 运行：

```bash
# 1. 编译
javac memory-leak-lab.java
# 2. 对照组（正常结束）
java -Xms256m -Xmx256m MemoryLeakLab clean 60
# 3. 泄漏模式（后台运行, 记录 pid）
java -Xms256m -Xmx256m MemoryLeakLab static 60 &
JPID=$(jps -l | grep MemoryLeakLab | awk '{print $1}')
jstat -gcutil $JPID 1000          # 看老年代上涨
jmap -histo $JPID | head -10      # 找可疑类
jmap -dump:format=b,file=heap.hprof $JPID   # 导出堆快照（或 jcmd $JPID GC.heap_dump heap.hprof）
# 4. 验证后清理: 杀进程 + 删产物
kill $JPID
rm -f *.class heap.hprof
```

已在本环境用 OpenJDK 17.0.18 编译运行验证（零错误，clean 正常结束，三种泄漏模式 jmap -histo 均见 byte[] 居首，进程与产物已清理）。
