# 05 · 内存模型与内置并发原语

> demo: `java demos/05_memory_model.java`

## 1. 设计动机

多线程最难的 bug 是**数据竞争**：两个线程读写同一变量，编译器/CPU 重排指令、
CPU 缓存不一致——结果"理论上不该发生却发生了"。C/C++ 把这套复杂性全交给程序员
（谁记得 `volatile` 的完整语义？）。Java 的命题：**把并发正确性的规则写进语言规范**
——`synchronized` 内置锁 + `volatile` + 一份正式的内存模型（JMM），
程序员不需要懂 x86/ARM 缓存协议也能写出跨平台正确的并发代码。
这是托管运行时路线在"并发安全"上的又一次集中承诺（呼应 01 号的内存承诺）。

## 2. 机制拆解

**JMM 的核心是 happens-before 规则**：如果操作 A happens-before 操作 B，
则 A 对内存的写在 B 可见、且 A 不会被重排到 B 之后。程序员只需遵守规则，
不必关心底层屏障：

```java
class Counter {
    private int count = 0;
    private volatile boolean ready = false;

    public synchronized void incr() { count++; }   // 内置锁：互斥 + happens-before
    public synchronized int get()   { return count; }

    public void publish(int v) { count = v; ready = true; }  // volatile 写
    public int read()          { return ready ? count : -1; } // volatile 读 → 见 count
}
```

三条最常用规则：

- **解锁 happens-before 后续加锁**：`synchronized` 块内写的变量，另一线程进入
  同一把锁后全部可见——锁既是互斥也是"内存屏障"；
- **`volatile` 写 happens-before 后续 `volatile` 读**：状态标志（上例 `ready`）
  用 volatile 即可安全发布；
- **线程启动/join**：`t.start()` 前的写对 `t` 内可见；`t.join()` 后见 `t` 的全部写。

**synchronized 的演化**是"语言级并发"的自我修正史：早期重量级（操作系统锁）
→ JDK 6 起**偏向锁 → 轻量级锁（CAS）→ 重量级锁**的膨胀路径，
让无竞争锁几乎免费；JDK 15 正式启用偏向锁废弃（维护成本 > 收益）。

## 3. 代码验证（demos/05_memory_model.java）

demo 演示：① 无同步的计数器在 N 线程下丢失更新（跑出 < N×M 的错误总数）；
② 加 `synchronized` 后总数精确；③ `volatile` 标志让一个线程安全地"发布"状态、
另一线程看到（对比无 volatile 时的可见性问题——现代 JVM 上很难稳定复现，
demo 用大量迭代放大概率并解释原因）；④ 展示 happens-before 的正确用法而非
`Thread.sleep` 碰运气。

```bash
java demos/05_memory_model.java
```

## 4. 代价与取舍

| 代价 | 说明 |
|------|------|
| 竞态仍是运行时才炸 | JMM 保证"写对了就安全"，但写没写对（漏同步）编译器不报错 |
| 锁有成本与风险 | 死锁、锁粒度选择、性能调优是并发 Java 的日常 |
| JMM 难学 | happens-before/重排/可见性是高级话题，多数人靠经验而非规范 |
| 共享内存模型的固有限制 | 需要分布式时得换 Actor/消息（Akka）或外部中间件 |

**换来的**：一份**跨平台**的内存模型——同样代码在 x86、ARM（弱内存序）上语义一致，
这是 C/C++ 至今没给到同等程度的承诺（C++11 才有正式内存模型，且更难用）；
`java.util.concurrent`（ConcurrentHashMap、原子类、线程池）建立在正确原语上，
让"并发容器开箱即用"成为 Java 生态的巨大优势。

## 5. 对 Tenet 的启示

- ✅ **吸收"内存模型写进规范"的认真**：Tenet 若未来加线程，必须定义清楚
  "哪些保证可见/顺序"——不能只说"有锁"，要向 JMM 学"happens-before 是唯一裁判"
- ✅ **吸收"锁的正确默认"**：`synchronized` 的"内置、不可忘、自动释放"
  （异常也释放）值得吸收为"作用域锁"设计——对应 Rust 分析的锁纪律
- ❌ **拒绝共享内存并发作为默认**：Tenet 的教学定位（呼应全库车辆/数据场景的
  单机处理）下，线程 + 锁的复杂度可以推迟；若加并发，优先学 Rust 的
  "消息传递 + 类型层面防数据竞争"精神（Send/Sync 是编译器保证，Java 是运行时保证）
- 💡 Java 的教训：**运行时保证不如编译期保证**——漏一个 `synchronized` JVM 不会提醒；
  这正是 Rust `Send/Sync` 在编译期拦截的原因。Tenet 演进并发时选哪条路，
  取决于想要"教学简单"还是"默认安全"

**一句话**：Java 用 JMM + 内置锁把并发正确性的规则**规范化**，跨平台一致但漏同步仍靠
运气；Tenet 现阶段不需要共享内存并发，未来若加，应向 Rust 学"编译期挡住数据竞争"。
