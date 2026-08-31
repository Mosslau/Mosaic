# ph10 JVM 示例

> 每个示例是主文档「6. 代码示例」对应示例的完整可运行版，自带自检断言（失败抛 `AssertionError`）。验证环境：全部用 OpenJDK 17.0.18（`javac -version` → 17.0.18，默认 G1 收集器）。本阶段的示例重点是「**能跑出真实观测结果**」——javap 反汇编、GC 日志、栈深等输出均为本机实测记录，随机器波动的部分已如实标注。

## 类名与文件名说明

为保持 `ex0X-` 编号命名，文件名（`ex01-class-file.java`）与类名（`Ex01ClassFile`）不一致。因此这些示例**刻意不声明为 `public` 类**（Java 规定 public 类必须与文件名同名，非 public 类无此限制；唯一的例外是 ex02 的配套类 `LoadedHelper.java`——它要被不同类加载器加载演示，必须是 public 独立文件）。编译时用**文件名**，运行时用**类名**：

```bash
# 1. 编译（ex02 会顺带编译引用的 LoadedHelper.java）
javac ex01-class-file.java
# 2. 运行（注意是类名不是文件名）
java Ex01ClassFile
```

所有示例的 `.class` 产物建议编译到临时目录，验证完清理（见下文「产物清理」）。

## 示例列表

| 文件 | 类名 | 说明 | 编译 | 运行 |
|------|------|------|------|------|
| ex01-class-file.java | Ex01ClassFile | class 文件结构：程序内读取自身 .class 验证魔数 0xCAFEBABE；配合 javap -c/-v/-l 观察字节码与 `javac -g` 差异 | `javac ex01-class-file.java` | `java Ex01ClassFile` |
| ex02-class-loader.java（+ LoadedHelper.java） | Ex02ClassLoaderDemo | 类加载机制：加载链（App→Platform→Bootstrap）、懒初始化、双亲委派、打破双亲委派（类身份 = 类名 + 加载器） | `javac ex02-class-loader.java` | `java Ex02ClassLoaderDemo` |
| ex03-gc-observation.java | Ex03GcObservation | GC 观察：制造 Young GC 与大对象（humongous），用 `-Xlog:gc*` 输出真实 GC 日志 | `javac ex03-gc-observation.java` | `java -Xms64m -Xmx64m -Xlog:gc* Ex03GcObservation` |
| ex04-jit-escape-analysis.java | Ex04JitEscapeAnalysis | JIT 与逃逸分析：预热曲线、`-Xint` 纯解释对比、非逃逸 vs 逃逸对象的 GC 次数差异 | `javac ex04-jit-escape-analysis.java` | `java -Xms256m -Xmx256m Ex04JitEscapeAnalysis` |
| ex05-jmm-demo.java | Ex05JmmDemo | JMM 内存模型：非 volatile 标志可见性实验、volatile 可见性（必然退出）、synchronized 安全发布 | `javac ex05-jmm-demo.java` | `java Ex05JmmDemo`（约 4~5 秒） |
| ex06-jvm-params.java | Ex06JvmParams | JVM 参数观察：进程内读取生效堆配置与 GC 收集器名；`-Xss` 与递归栈深（StackOverflowError）关系 | `javac ex06-jvm-params.java` | `java Ex06JvmParams` / `java -Xss256k Ex06JvmParams` / `java -Xss4m Ex06JvmParams` |

## 验证状态与真实输出要点

全部示例已在本环境（OpenJDK 17.0.18，Apple Silicon / macOS，14 核，24GB 内存）编译运行验证。以下记录的是**实测输出**，随机器变化的数字已标注，不要当作精确断言：

### ex01：class 文件结构与 javap

- 运行输出：`class 文件魔数 = 0xCAFEBABE (应为 0xCAFEBABE): 通过`（程序读取自身 .class 字节验证魔数；**注意必须用 `0xCAFEBABEL` long 字面量比较**——写成 `0xCAFEBABE` 是负数 int，与 long 比较恒不相等，这是本示例开发时真实踩过的坑）
- `javap -v` 常量池片段（本机实测）：

```text
Constant pool:
   #1 = Methodref          #2.#3         // java/lang/Object."<init>":()V
   #2 = Class              #4            // java/lang/Object
   #7 = Fieldref           #8.#9         // Ex01ClassFile.base:I
   #8 = Class              #10           // Ex01ClassFile
```

- `javap -c` 反汇编（`add` 方法，本机实测）：`getstatic calls / iconst_1 / iadd / putstatic` 与 `aload_0 / getfield base / iadd / ireturn` 清晰可见
- **`javac -g` 差异（实测）**：`javac -g` 编译后 `javap -l` 有 `LineNumberTable`（如 `line 20: 0`）；`javac -g:none` 编译后 `javap -l` 只剩方法签名、无行号表——调试信息默认不生成，异常堆栈与 IDE 调试依赖 `-g`
- class 文件版本（实测）：`minor version: 0, major version: 61`（61 = Java 17）

### ex02：类加载器

- 加载链（实测）：`AppClassLoader → PlatformClassLoader → null`（null 即 Bootstrap）；`java.lang.String` 的加载器为 `null`
- 懒初始化（实测）：`Class.forName("LoadedHelper", false, app)` 不输出 `<clinit>`；访问编译期常量（已内联进 `ConstantUser` 的 `ConstantValue` 属性）同样不触发；`Class.forName("LoadedHelper")` 才输出 `>> LoadedHelper <clinit> 执行`
- 双亲委派（实测）：`ParentFirstLoader.loadClass("LoadedHelper")` 返回的类是 `AppClassLoader` 加载的——父能加载就不自己加载
- 打破双亲委派（实测）：两个 `BreakingLoader` 各自 `defineClass` 同一份字节 → 两个 `Class` 对象不相等（`hash` 不同）；`b1 实例 instanceof LoadedHelper` 为 `false`——**类身份 = 类名 + 定义它的加载器**

### ex03：GC 观察（`-Xlog:gc*`）

运行 `java -Xms64m -Xmx64m -Xlog:gc*,gc+promotion=debug Ex03GcObservation`，实测日志关键行：

```text
[0.027s][info][gc,start    ] GC(0) Pause Young (Normal) (G1 Evacuation Pause)
[0.028s][info][gc,heap     ] GC(0) Humongous regions: 2->2
[0.028s][info][gc          ] GC(0) Pause Young (Normal) (G1 Evacuation Pause) 25M->3M(64M) 0.350ms
[0.032s][info][gc          ] GC(4) Pause Young (Normal) (G1 Evacuation Pause) 60M->3M(64M) 0.217ms
```

- 解读：`Pause Young (Normal)` = Young GC（Minor GC），`25M->3M(64M)` = 回收前后用量与堆上限，末尾 `0.350ms` = 停顿耗时；`Humongous regions` = 1MB 大对象直接以巨型区域分配（G1 中 ≥ 区域大小一半的对象为 humongous，直接进老年代区）
- **注意：停顿毫秒数、GC 次数随机器/GC 时机波动，观察「模式」即可**（如「堆 64M 时短期对象触发多次 Young GC」「大对象以 humongous 分配」）；本程序不自断 GC 数字，只断言跑完 200 轮无 OOM

### ex04：JIT 与逃逸分析

- 默认配置预热（实测）：第 1 批 3ms → 第 2 批 2ms → 第 3/4 批 1ms（本机预热差异小，因为 JIT 很快）
- `-Xint` 纯解释（实测）：每批稳定约 150~160ms——**解释执行比 JIT 慢约 50 倍**，这是「JIT 编译热点方法」最直观的证据
- `-XX:+PrintCompilation`（实测片段）：`Ex04JitEscapeAnalysis::pointSum @ 4 (43 bytes)` 出现 `% 3` / `% 4`（OSR 与 C2 编译层级）与 `made not entrant`（旧编译版本失效）
- 逃逸分析（实测）：同样 8×500 万次 `new Point`，非逃逸写法触发 GC **0 次**，逃逸写法（存入 ArrayList）触发 GC **63 次**——逃逸分析把不逃逸的对象标量替换掉，堆分配几乎为零；数字随机器波动，但「逃逸版本 GC 明显更多」稳定复现
- 说明：`-XX:+PrintEscapeAnalysis` 在 OpenJDK 17 发布版**不可用**（仅 debug 版 JVM，实测报 `notproduct` 错误），观察逃逸分析效果用上面的 GC 次数对比；`-XX:+DoEscapeAnalysis` / `-XX:-DoEscapeAnalysis` 开关可用（默认开启）

### ex05：JMM 内存模型

- 非 volatile 标志（实测）：主线程置 `plainStop=true` 后，工作线程 **2 秒内未退出**（JIT 把标志读提升到循环外）——可见性失败真实存在；**但这是平台/编译相关的观察结果**，x86 强内存模型下本机多次实测一致，换架构/编译器不一定复现，程序如实打印而不作硬断言
- volatile 标志（实测）：工作线程及时退出（`volatile` 写 happens-before 后续读，JMM 保证，与硬件无关）——断言稳定成立
- synchronized 安全发布（实测）：读线程在锁内读到完整 `payload=[11,22,33]`——监视器锁规则保证写线程解锁前的写入全部可见

### ex06：JVM 参数与栈深

- 进程内读取生效配置（实测）：`-Xms64m -Xmx256m` → `maxMemory=256MB / totalMemory=66MB`；默认（本机 24GB 内存）→ `maxMemory=6144MB`（JVM 默认最大堆为物理内存 1/4）；GC 收集器默认 `G1 Young Generation + G1 Old Generation`，换 `-XX:+UseSerialGC` 变为 `Copy + MarkSweepCompact`
- 栈深与 `-Xss`（实测，随机器/JIT 波动）：

| -Xss | 最大递归深度（本机实测） |
|------|--------------------------|
| 256k | 1,478 |
| 默认（约 1m） | 45,662 |
| 4m | 126,154 |

- 结论：**递归深度随 `-Xss` 增大而增大**（单调）；每帧实际消耗 ≈ 栈大小 / 深度，约 56~100 字节/帧量级（含 JIT 帧布局差异）

## 产物清理

编译运行后当前目录会产生 `.class` 文件，验证完清理（不要把字节码提交进仓库）：

```bash
# 1. 编译
javac ex01-class-file.java
# 2. 运行
java Ex01ClassFile
# 3. 验证后清理 .class
rm -f *.class
```

ex02 会额外产出 `LoadedHelper.class`、`ConstantUser.class`、`Ex02ClassLoaderDemo$*.class`，一并 `rm -f *.class` 即可；ex03/ex04/ex05/ex06 同理。
