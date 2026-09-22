# 🔬 Java 语言设计分析（analysis/java）

> 一步步分析 Java 的语言设计，每篇主题配一个可直接运行的 demo。
> 分析结论汇总到 [`Tenet`](../../tenet/Tenet架构设计.md)，作为 Tenet 语言设计的输入。

> 🧭 **定位**：本目录是「设计解剖」——讲*为什么*这么设计。
> 对应的「学习笔记」（讲*怎么学*）在 [`languages/java/`](../../studies/java/)，建议先学后析。

Java 的核心设计命题：**"Write Once, Run Anywhere"——把跨平台、内存安全与并发正确性，
托付给一个托管运行时（JVM）**。字节码中间层、垃圾回收、强类型 + 单根继承、受检异常、
内置 `synchronized` 都是这一命题的推论。它是"用工程稳健换语言优雅"的极致样本：
企业级成功的每一面（GC/接口生态/内存模型）都对应一份被长期诟病的代价（停顿/样板化/竞态靠运气）。

## 分析路线

| # | 主题 | 核心问题 | Demo |
|---|------|---------|------|
| 01 | [垃圾回收与自动内存管理](notes/01-gc-memory.md) | 不手动释放内存，代价是什么？ | `java demos/01_gc.java` |
| 02 | [类型系统：装箱与泛型擦除](notes/02-type-system.md) | 值/引用分裂与擦除，两次调和换来什么？ | `java demos/02_type_system.java` |
| 03 | [单继承与接口](notes/03-inheritance-interface.md) | 怎么既躲开菱形继承又保住多态？ | `java demos/03_inheritance_interface.java` |
| 04 | [受检异常](notes/04-exception-handling.md) | 让编译器强制处理错误，是福是祸？ | `java demos/04_exception_handling.java` |
| 05 | [内存模型与并发原语](notes/05-memory-model.md) | 并发正确性写进语言规范，够了吗？ | `java demos/05_memory_model.java` |

## 快速开始

```bash
cd analysis/java
java demos/01_gc.java      # 依次运行 01~05（JDK 11+ 单文件模式，无需先编译）
# 或传统方式：
javac -d /tmp/ph-java demos/01_gc.java && java -cp /tmp/ph-java GcDemo
```

## 分析方法

每篇笔记的结构：

1. **设计动机**——这个设计解决什么问题
2. **机制拆解**——语法/语义/JVM 运行时规则
3. **代码验证**——最小 demo 亲眼看到机制
4. **代价与取舍**——牺牲了什么
5. **对 Tenet 的启示**——值得吸收 / 应该拒绝（输入 Tenet架构设计.md（完整文档 §1 设计溯源））

## 与其它分析台的关系

Java 分析常与已析语言形成对照，读时建议互参：

| Java 主题 | 对照分析台 |
|-----------|-----------|
| 01 GC（运行时自动内存） | [`cpp/01-raii`](../cpp/notes/01-raii.md)（RAII：把释放绑作用域） |
| 02 装箱/泛型擦除 | [`rs/03-trait-generics`](../rs/notes/03-trait-generics.md)（编译期泛型）、[`py/01-dynamic-typing`](../py/notes/01-dynamic-typing.md)（动态类型） |
| 03 继承与接口 | [`rs/03-trait-generics`](../rs/notes/03-trait-generics.md)（trait 多态） |
| 04 受检异常 | [`rs/04-option-result`](../rs/notes/04-option-result.md)（错误即返回值） |
| 05 JMM 与内置锁 | [`rs/05-send-sync`](../rs/notes/05-send-sync.md)（编译期防数据竞争） |
