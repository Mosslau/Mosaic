# ph10 JVM 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：全部用 OpenJDK 17.0.18（`javac -version` → 17.0.18），诊断工具 jps/jstat/jstack/jmap/jcmd 均为 JDK 自带。参考实现均用非 public 类（文件名 `sol-0X-*.java` 与类名不同），编译用文件名、运行用类名。
> 四题与 Roadmap「ph10 JVM 阶段」练习小节一一对应：查看 Java 进程 / 分析线程死锁 / 导出 heap dump / 查看 GC 日志。题目里的「程序」要自己写，参考实现只在完成后对照。
> 练习 2、3 涉及持续运行的程序与外部诊断工具，**务必在独立终端/后台运行并验证后清理进程**，不要留下僵尸 Java 进程。

## 练习 1：查看 Java 进程（★）

**目标**：启动自己的 Java 程序，用 `jps` 找到它的 pid，用 `jstat` 观察内存分区使用率，用 `jstack` 看线程状态——掌握「先找到进程，再诊断进程」的第一步。
**要求**：

- 写一个持续运行的 Java 程序：打印自身 pid（`ProcessHandle.current().pid()`），循环做一点计算并 `Thread.sleep(200)` 保持存活，每 10 轮打印一次进度
- 后台运行后依次执行：`jps -l` 找到 pid → `jstat -gcutil <pid> 1000` 连续观察 → `jstack <pid> | head -30` 看 main 线程状态
- 用完把进程杀掉（`kill <pid>`），不许留僵尸进程

**验收**：能给出 jps / jstat / jstack 三份真实输出；能说出 `jstat -gcutil` 各列含义（S0/S1/E/O/M 分区使用率、YGC/FGC 次数、YGCT/FGCT/GCT 累计耗时）；jstack 中能认出 main 线程及其状态——计算时为 `RUNNABLE`、`Thread.sleep` 时为 `TIMED_WAITING`（本机实测 sleep 期间为 `TIMED_WAITING (sleeping)`）。
**注意**：本机（macOS / OpenJDK 17.0.18）实测 `jstat -gcutil` 的 M（元空间）与 CCS 列在**进程尚未发生 GC、元空间未扩展时显示 `-`**，发生 GC 后即出现真实数值（如 MemoryLeakLab 在 YGC=0 时即显示 M=85.16/CCS=56.98）——属工具平台差异而非数据缺失，其余列正常；若目标进程长期显示 `-`，元空间使用率用 `jcmd <pid> VM.metaspace` 查看。

## 练习 2：分析线程死锁（★★）

**目标**：写出必然死锁的两线程程序，用 `jstack` 定位死锁并给出修复。
**要求**：

- 两个线程分别以**相反顺序**抢两把锁（线程 1 先拿 A 再拿 B，线程 2 先拿 B 再拿 A），`Thread.sleep(50)` 放大竞争窗口，两把锁都拿不到就卡死
- `jstack <pid>` 输出中定位 `Found one Java-level deadlock`，看懂「哪个线程在等哪把锁、锁被谁持有」
- 对照死锁四条件（互斥 / 持有并等待 / 不可剥夺 / 循环等待）说明为什么必死锁
- 修复方案（统一加锁顺序或 `tryLock` 超时）写进注释，并用修复版验证程序能正常结束
- 验证后杀掉死锁进程，不留僵尸

**验收**：jstack 输出包含 `Found one Java-level deadlock` 且两个线程互相等待的锁、持有者清晰可读；修复版运行能正常退出；程序代码里能看到加锁顺序不一致是死锁根源。

## 练习 3：导出 heap dump 并分析内存泄漏（★★★）

**目标**：写一个内存泄漏程序（静态集合持续持有对象），用 `jmap -histo` 快速定位可疑类，导出堆快照，沿引用链找到泄漏根因。
**要求**：

- 程序每轮向**静态集合**（`static List<byte[]>`，静态字段是 GC Root）添加一个 1MB 的 `byte[]`，少量 `sleep` 保持进程存活，每 10MB 打印一次累计量——泄漏对象永远可达，堆必然持续上涨直至 OOM
- 用 `-Xmx128m` 限制堆运行，程序支持上限参数：`java -Xms128m -Xmx128m 你的类名 40`（分配到 40MB 后保持存活约 60 秒供诊断，然后继续分配直至 OOM——实测 128m 堆下 cap 设 80 会在 ~60MB 提前 OOM、到不了保持档位，故建议 40~50；不设这一档会很快 OOM 来不及观察）；观察路径：`jstat -gcutil` 看老年代持续上涨 → `jmap -histo <pid> | head -20` 看 `byte[]` 实例数与字节数异常突出 → `jmap -dump:format=b,file=heap.hprof <pid>` 导出快照（或 `jcmd <pid> GC.heap_dump heap.hprof`）
- 用 MAT 打开 hprof，走 Leak Suspects / Dominator Tree / Path to GC Roots 沿引用链找到持有者，把「持有者是谁」写进结论
- 修复思路（把静态集合换局部变量 / 定期清理 / 换带淘汰的缓存）写进注释；验证后清理进程与 hprof 文件

**验收**：`jmap -histo` 中 `byte[]` 的实例数与占用字节数远超其他类（真实输出为准）；能说清「静态集合是 GC Root、add 进去的对象永远回收不了」；hprof 沿引用链能看到持有者是程序里的静态集合。

## 练习 4：查看 GC 日志（★★）

**目标**：写程序频繁创建短命对象触发 Young GC，用 `-Xlog:gc*`（JDK 9+ 统一日志）观察并解读，区分 Minor / Full GC。
**要求**：

- 程序循环创建大量 64KB 短命对象（触发 Young GC），每隔一段时间保留一个 1MB 长命对象（可能晋升老年代）
- `java -Xms128m -Xmx128m -Xlog:gc* 你的类名` 运行，收集 GC 日志
- 从日志中识别 `Pause Young (Normal)` 行，解读 `25M->3M(128M)` 三个数字（回收前 / 回收后 / 堆上限）与末尾停顿毫秒
- 换 `-Xmx64m` 再跑一次，观察 Young GC 频率变化（堆越小 GC 越频繁——用真实日志佐证）

**验收**：给出两份真实 GC 日志片段（128m 与 64m），能指出 GC 类型、回收前后用量、停顿耗时，并能解释「堆越小、Young GC 越频繁」；日志中 `Pause Full` 出现且频繁时应能意识到老年代/元空间可能不足（本练习不要求制造 Full GC）。

> **提示**：四题对应主文档第 6 章之外的诊断工具知识（3.9~3.11），做完后对照 `sol-*` 检查。`sol-*` 为参考实现（文件头已注明验证环境与验证状态），做完再看；练习 2、3 的进程验证务必 kill 清理。
