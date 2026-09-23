# Java Lambda 与 Stream 阶段

> 面向企业级后端、微服务方向，把数据处理写成可读、可组合的函数式流水线——让集合操作代码更接近业务意图、更少出错。

## 1. 概述

Java Lambda 与 Stream 阶段的目标是：**掌握现代 Java 的函数式数据处理方式**——用 lambda 表达式消除匿名类的样板代码，用 Stream API 把「过滤、映射、聚合」写成声明式流水线，用 Optional 优雅表达可能为空的值，并用 Switch Expressions 与 Pattern Matching 让分支与类型判断更简洁、更安全。本阶段是后续一切「数据加工」代码的通用语言：报表统计、日志分析、批量清洗、事件分派都会用到这些能力。

| 核心维度 | 覆盖内容 |
|----------|---------|
| Lambda 与函数式接口 | lambda 语法、`@FunctionalInterface`、方法引用 `::` |
| 四大内置函数式接口 | `Predicate`/`Consumer`/`Function`/`Supplier` 及组合方法 |
| Stream 流水线 | 创建、中间操作（`filter`/`map`/`flatMap`/`distinct`/`sorted`/`limit`）、惰性求值 |
| 终端操作与聚合 | `collect`/`reduce`/`count`/`anyMatch`、短路求值 |
| 收集器 | `groupingBy`/`partitioningBy`/`joining`/`summarizingInt` |
| Optional | 创建（`of`/`empty`/`ofNullable`）、链式处理（`map`/`filter`/`orElse`/`orElseThrow`） |
| 并行流 | `parallelStream`、Fork/Join 模型与适用边界 |
| 新式分支语法 | Switch Expressions（`->`/`yield`，Java 14+）、Pattern Matching（Java 16+/21+） |

这个阶段只涉及 Lambda 表达式、函数式接口、方法引用、Stream 流水线、Collectors、Optional 与 Stream 的配合，以及 Switch Expressions 与 Pattern Matching 两类新式分支语法，**不涉及多线程与并发编程、JVM 深入与性能调优、Spring 框架** — 那些是 ph09 多线程与并发阶段、ph10 JVM 阶段、ph15 Spring 全家桶阶段的内容。本阶段承接 ph07 IO 与文件操作阶段——`Files.lines` 把文件读取接入 Stream 流水线；并行流只讲「何时可用、为何禁止共享可变状态」的边界，线程模型细节留给 ph09/ph10。

## 2. 来源与演变

Java 诞生后近二十年，集合处理一直靠 for 循环加临时变量，业务逻辑被「怎么循环」淹没。2000 年代后期，函数式编程（Haskell/Erlang，以及 Scala、Guava 在 JVM 上的实践）证明了**声明式数据处理**的价值——描述「要什么」，而不是「怎么循环」。Java 8（2014）以 JSR 335（Project Lambda）引入三大件：lambda 表达式（配合函数式接口）、Stream API 与 Optional，同时加入接口默认方法让集合 API 平滑升级。底层借助 Java 7 引入的 `invokedynamic` 字节码指令（JSR 292），使 lambda 的编译方式比匿名内部类更高效、更可优化（见 4.1）。

Java 8 之后的演进分两条线。**Stream 线**持续补能力：Java 9 加 `takeWhile`/`dropWhile`/`ofNullable`，Java 10 提供不可变收集器，Java 12 的 `teeing`，Java 16 的 `Stream.toList()`——核心模型（惰性流水线 + 终端求值）十年未变。**分支语法线**则在 Java 14 的 Switch Expressions（`->`/`yield`）、Java 16 的 instanceof 模式匹配、Java 21 的 switch 模式匹配中，把「样板代码」从语言层面逐步消除——与 lambda 一脉相承：让代码表达意图，而非机械步骤。

| 版本 | 演进 |
|------|------|
| Java 7（2011） | `invokedynamic` 指令（JSR 292），为高效 lambda 铺路 |
| Java 8（2014） | Lambda、函数式接口、Stream API、Optional、方法引用、接口默认方法 |
| Java 9（2017） | Stream 增强：`takeWhile`/`dropWhile`/`ofNullable`；`Optional.or` |
| Java 12（2019） | `Collectors.teeing` 双下游合并 |
| Java 14（2020） | Switch Expressions 正式化（JEP 361）：`->` 与 `yield` |
| Java 16（2021） | `Stream.toList()`；instanceof 模式匹配正式化（JEP 394） |
| Java 17（2021） | switch 模式匹配首轮预览（JEP 406）；sealed class 正式化 |
| Java 21（2023） | switch 模式匹配与 `case null` 正式化（JEP 441；17~20 预览，JEP 406）、record patterns（JEP 440） |

本文示例以 **Java 17（LTS）** 为基线（当前主流生产 LTS，覆盖 Lambda/Stream 全部核心 API、Switch Expressions 与 instanceof 模式匹配的正式特性），验证工具链 OpenJDK 17.0.18；switch 模式匹配（`case null`、类型模式分派）正式化于 Java 21+（17~20 为预览，需 `--enable-preview`，JEP 406），文中与代码层单独标注。这个阶段的语法是自 Java 8 以来最稳定的部分——lambda 与 Stream 的核心 API 十年未变，写下的代码在更新的 JDK 上原样运行。

## 3. 语法与参数

### 3.1 Lambda 表达式与函数式接口

lambda 是**匿名函数的语法糖**：`(参数列表) -> { 方法体 }`，只能赋给**函数式接口（functional interface）**——恰好只有一个抽象方法的接口，用 `@FunctionalInterface` 注解做编译期校验（多写一个抽象方法即编译失败）。

```java
@FunctionalInterface
interface Calculator {
    int calc(int a, int b);           // 唯一抽象方法，可另有 default/static 方法
}
Calculator add = (a, b) -> a + b;     // 单表达式体自动返回结果
System.out.println(add.calc(2, 3));   // 5

Runnable r1 = () -> System.out.println("无参数");
java.util.function.Function<Integer, Integer> f = x -> x * 2;   // 单参数可省括号
java.util.function.BiFunction<Integer, Integer, Integer> g =
        (x, y) -> { int s = x + y; return s; };                 // 多语句必须 return
```

- 参数类型可从目标类型**推导**；单表达式体自动返回，**无需 return**
- lambda 捕获外部局部变量要求 **effectively final**（赋值后不再改变）
- `@FunctionalInterface` 只是习惯——只有一个抽象方法的接口自动就是函数式接口

### 3.2 四大内置函数式接口

日常 90% 的 lambda 都落到 `java.util.function` 的四个基础接口上，先认出它们再读任何方法签名都容易：

| 接口 | 抽象方法 | 语义 | 典型用法 |
|------|---------|------|---------|
| `Predicate<T>` | `boolean test(T)` | 判断真假 | `filter`、`removeIf` |
| `Consumer<T>` | `void accept(T)` | 消费，不返回 | `forEach`、`ifPresent` |
| `Function<T,R>` | `R apply(T)` | 输入 T 转输出 R | `map`、`toMap` |
| `Supplier<T>` | `T get()` | 提供值（可懒加载） | `orElseGet`、工厂 |

```java
Predicate<String> longEnough = s -> s.length() > 3;
Consumer<String> printer = System.out::println;
Function<String, Integer> len = String::length;
Supplier<Double> random = Math::random;
printer.accept(longEnough.test("hello") ? "通过" : "太短");
System.out.println(len.apply("hello"));
```

- 变体：`BiFunction`（两参）、`UnaryOperator`（同类型转换）、`IntPredicate`/`IntFunction` 等**基本类型特化**（避免装箱）
- 组合方法：`Predicate` 的 `and`/`or`/`negate`、`Function` 的 `andThen`/`compose`——见示例 3

### 3.3 方法引用（::）

方法引用是 lambda 的**简写**——当 lambda 体只是「调用某个已有方法」时用 `::`：

```java
List<String> names = Arrays.asList("alice", "bob");
names.stream().map(String::toUpperCase)      // 等价 s -> s.toUpperCase()
     .forEach(System.out::println);          // 等价 s -> System.out.println(s)
Supplier<ArrayList<String>> factory = ArrayList::new;   // 构造器引用
```

- 四种形态：`类名::静态方法`、`对象::实例方法`、`类名::实例方法`（第一个参数作为接收者）、`类名::new`
- 目标方法签名必须与函数式接口的抽象方法兼容

### 3.4 Stream 创建与中间操作

Stream 是**元素的序列**，描述数据处理流水线。中间操作（intermediate operation）返回新 Stream、**惰性执行**，真正计算要等终端操作触发（见 4.2）。

```java
List<Integer> nums = Arrays.asList(1, 2, 3, 4, 5, 6, 2, 3);
List<Integer> result = nums.stream()                 // 从集合创建
        .filter(n -> n % 2 == 0)                     // 过滤：保留偶数
        .distinct()                                  // 去重
        .sorted()                                    // 排序（对象需 Comparator）
        .skip(1).limit(3)                            // 跳过 1 个、最多取 3 个（短路）
        .peek(n -> System.out.println("经过: " + n))  // 调试观察（勿用于业务）
        .collect(Collectors.toList());
```

其他创建方式：`Stream.of("a","b")`、`Arrays.stream(arr)`、`IntStream.range(1, 10)`、`Files.lines(path)`（衔接 ph07，流用完必须关闭）。

- **`flatMap` 展平嵌套**：`Stream<List<Integer>>` → `Stream<Integer>`，把流中每个元素再展开成流并合并
- Java 9+：`takeWhile`/`dropWhile`（按条件取/丢前缀）、`Stream.iterate` 带停止条件
- `peek` 专用于调试观察，**不要**用它做数据修改等副作用

### 3.5 终端操作：collect / reduce / forEach / count / anyMatch

终端操作（terminal operation）**触发求值**，执行后 Stream 被消费、不可复用——它是流水线的「出口」：

```java
int sum = nums.stream().reduce(0, Integer::sum);        // 聚合：0+1+2+3+4+5+6+2+3 = 26
long count = nums.stream().count();                     // 计数
boolean anyBig = nums.stream().anyMatch(n -> n > 4);    // 任一满足（短路）
nums.stream().forEach(System.out::print);               // 遍历（副作用）
Optional<Integer> first = nums.stream()
        .filter(n -> n > 3).findFirst();                // 短路：满足即停，Optional[4]
```

- **Stream 不能复用**：再次操作抛 `IllegalStateException: stream has already been operated upon or closed`
- `reduce` 无初值重载、`min`/`max` 返回 `Optional`（空流时为空）
- `mapToInt`/`mapToDouble`/`mapToLong` 转基本类型流，自带 `sum`/`average`/`max`/`min`（避免装箱）

### 3.6 collect 收集器：toList / groupingBy / partitioningBy / joining / summarizing

`collect` 把流水线结果**汇聚成容器**，`Collectors` 提供全套工厂方法，报表统计的主要需求都在这里：

```java
List<String> names = Arrays.asList("Alice", "Bob", "Cary");
Set<String> nameSet = names.stream().collect(Collectors.toSet());
String joined = names.stream().collect(Collectors.joining(", ", "[", "]")); // [Alice, Bob, Cary]
Map<Integer, List<String>> byLength = names.stream()
        .collect(Collectors.groupingBy(String::length));   // 按长度分组
Map<Boolean, List<String>> longNames = names.stream()
        .collect(Collectors.partitioningBy(s -> s.length() > 3));   // true/false 两组
IntSummaryStatistics stat = names.stream()
        .collect(Collectors.summarizingInt(String::length));       // 计数/平均/最大/最小
System.out.println(stat.getAverage());
```

- `Collectors.toList()`（Java 8）vs `Stream.toList()`（Java 16）：后者返回**不可变** List，更省内存，只读结果优先
- `groupingBy` 第二参数是**下游收集器**，可叠加 `counting()`/`summarizingInt()`/`mapping()`——分组加统计一步到位（见示例 2）
- `partitioningBy` 返回 `Map<Boolean, ...>`，天然分出「满足 / 不满足」两类

### 3.7 Optional：创建与链式处理

Optional 是**可能为空**的值的容器，把「判空」从散落的 `if (x != null)` 收拢为一条链式表达式，主要出现在**返回值**位置（如 `findFirst`、`average()`）。

```java
Optional<String> c = Optional.ofNullable(x);      // 可能为 null，最常用
String v = c.orElse("默认值");                     // 兜底值
String v2 = c.orElseGet(() -> fetchDefault());    // 懒加载兜底（仅空时执行）
String v3 = c.orElseThrow(() -> new IllegalStateException("缺失"));
c.ifPresent(s -> System.out.println(s));          // 存在才消费
c.filter(s -> s.length() > 3)                     // 链式：存在才转换、再过滤
 .map(String::toUpperCase)
 .ifPresent(s -> System.out.println(s));
```

- **`orElse` 的参数无条件求值**：昂贵的兜底逻辑用 `orElseGet`（lambda 仅为空时执行）
- **不要裸调 `get()`**：空 Optional 调 `get()` 抛 `NoSuchElementException`——用 `orElse`/`orElseThrow` 兜底
- 不要用 Optional 做**字段类型或方法参数**（会让全代码库处处判空）；Java 11+ 可用 `isEmpty()`

### 3.8 并行流基础：parallelStream

`parallelStream()`（或 `stream().parallel()`）让流水线在多核上并行执行，底层是 Fork/Join 框架（见 4.3）：

```java
List<Integer> nums = IntStream.rangeClosed(1, 1_000_000).boxed()
        .collect(Collectors.toList());
long sum = nums.parallelStream()               // 数据自动切分到多个线程
        .filter(n -> n % 2 == 0)
        .mapToInt(Integer::intValue).sum();
```

- 并行度默认 = `CPU 核数 - 1`（ForkJoinPool.commonPool，**全 JVM 共享**）；只对**大集合 + 计算密集且相互独立**有意义，小数据反而更慢
- **禁止写共享可变状态**（如累加到外部变量）——必须用 `collect`/`reduce` 归约；顺序敏感时用 `forEachOrdered`
- `sorted`/`distinct`/`limit` 等有状态操作在并行下开销大：`sorted` 需全量缓冲、`distinct` 的去重集合随元素增长、`limit` 需跨线程协调截断（各自缓冲语义见 4.2）

### 3.9 Switch Expressions（`->` 与 `yield`，Java 14+）

传统 switch 的三个老毛病——**break 穿透**、不能作为表达式、穷尽性靠自觉——在 Switch Expressions 里全部消除：

```java
int day = 3;
String label = switch (day) {          // 整个 switch 是一个表达式，产出值
    case 1, 2, 3 -> "工作日";           // 箭头语法：无穿透，多值用逗号
    case 6, 7 -> "周末";
    default -> "非法日期";              // int 取值有 2^32 种，编译器无法穷举，必须有 default（穷尽）
};
int score = 85;
String grade = switch (score / 10) {
    case 9 -> "优秀";
    case 10 -> {                            // 101~109 /10 也得 10，须再判越界
        yield score == 100 ? "优秀" : "非法分数";
    }
    case 8 -> "良好";
    case 7 -> "中等";
    case 6 -> "及格";
    default -> {                        // 块体分支用 yield 返回值
        if (score < 0 || score > 100) yield "非法分数";
        yield "不及格";
    }
};
```

- **箭头标签（`->`）天然不穿透**：不会落入下一个 case，传统 `break` 消失
- switch 现在是**表达式**：可直接赋值、返回、作参数；**必须穷尽**——`int`/`String` 必须有 `default`，枚举要么全覆盖要么给 `default`（见 4.4）
- 块体分支用 **`yield`** 返回结果，替代「临时变量 + break」的样板

### 3.10 Pattern Matching（instanceof / switch，Java 16+/21+）

模式匹配把「类型判断 + 强转」合并为一步：匹配成功的同时声明**模式变量**，作用域仅限匹配成功的分支。

```java
Object obj = "hello";
// instanceof 模式匹配（Java 16+）
if (obj instanceof String s) {            // s 自动声明为 String，无需强转
    System.out.println(s.length());
}
// switch 模式匹配（Java 21+）：按类型分派 + null 分支
String info = switch (obj) {
    case null -> "空值";
    case String s -> "字符串: " + s;
    case Integer i -> "整数: " + i;
    default -> "其他类型";
};
```

- 模式变量**流式作用域**：`if (obj instanceof String s && s.length() > 3)` 中 `s` 可继续用；`||` 右侧不可
- `case null` 正式化于 Java 21（JEP 441；17~20 为预览，需 `--enable-preview`，JEP 406）——免去先判空；guard 条件 `case String s when s.length() > 3` 可加分支守卫
- 对 sealed class（ph02）分派时编译器可做**穷尽性检查**：覆盖全部 permitted 子类型后无需 default；模式按**声明顺序**匹配，具体类型（子类）放前面

### 3.11 何时不用 Stream

roadmap 明确要求「能判断何时不用 Stream」，以下场景请回退传统控制流：

- **两三行的小逻辑**：简单 for 循环更直白，Stream 是负担
- **需要中途跳出**（`break`/`return`）：Stream 没有 break，复杂跳出用循环
- **强依赖前一步结果的状态累积**：reduce 写不出来或可读性差时，循环 + 局部变量更清晰
- **受检异常多的业务**：Stream 内无法直接抛受检异常，循环里 try/catch 更直接
- **调试困难的超长链**：先拆中间变量、加 `peek` 观察，必要时整体回退 for 循环

### 3.12 本阶段高频坑一览

| 坑 | 症状 | 对策 |
|----|------|------|
| Stream 复用 | `IllegalStateException: stream has already been operated upon or closed` | 每轮处理新建 Stream |
| 忘记接终端操作 | 中间操作「没执行」，结果为空 | 惰性求值：必须加 `collect`/`count` 触发 |
| 裸调 `Optional.get()` | 空 Optional 抛 `NoSuchElementException` | `orElse`/`orElseThrow` 兜底 |
| `orElse` 放昂贵兜底 | 兜底逻辑被无条件执行 | 用 `orElseGet` 懒加载 |
| 并行流写共享变量 | 数据竞争、结果随机错误 | 用 `collect`/`reduce` 归约 |
| 传统 switch 忘写 break | 分支穿透，多个 case 被执行 | 改用箭头语法（Switch Expressions） |
| switch 表达式不穷尽 | 编译错误 `does not cover all possible input values` | 枚举全覆盖或加 `default` |
| 过度链式调用 | 一行 8 个操作，读不懂、难调试 | 拆方法、拆中间变量，适时回退 for |

## 4. 底层原理

### 4.1 lambda 的字节码实现：invokedynamic + LambdaMetafactory

直觉上 lambda 是「匿名内部类的语法糖」，**实际不是**。javac 不为 lambda 生成独立 class 文件，而是在调用点生成一条 **`invokedynamic`** 指令，引导方法 `LambdaMetafactory.metafactory` 在**首次执行时**动态生成函数式接口的实现类（隐藏类）并绑定调用点：

| 对比项 | 匿名内部类 | Lambda |
|--------|-----------|--------|
| 编译产物 | 每个匿名类一个 `.class` 文件 | 一条 `invokedynamic` 指令，运行期生成实现 |
| 对象创建 | 每次 `new` 一个新实例 | 非捕获 lambda 缓存为**单例**复用 |
| `this` 语义 | 指向匿名类自身 | 指向外层对象（lambda 不是新作用域类） |
| 优化空间 | 固定字节码，JVM 难改 | 调用点可内联、实现策略可替换，字节码不动 |

两个直接收益：**非捕获 lambda 零开销复用**（不引用外部变量时全程只有一个实例），以及**未来可演进**——JVM 换掉生成策略不需要重新编译代码。

### 4.2 Stream 的惰性管道：Sink 链与求值时机

惰性求值靠**责任链（Sink 链）**实现：调用中间操作时不遍历数据，只是把上一个操作包装进新的 `Sink`（内部处理节点）；直到终端操作触发，元素才从源头**逐个流经整条链**，一次遍历完成全部操作——不是每个操作各遍历一遍集合：

```text
nums.stream()  ──▶  Sink1(过滤)  ──▶  Sink2(映射)  ──▶  Sink3(限额)  ──▶  终端触发求值
元素从源头逐个穿过 Sink 链，垂直执行、水平短路
```

- **水平短路**：`limit(3)` 在链里记录剩余额度，取满即停；`anyMatch`/`findFirst` 同理——「惰性 + 短路」是性能来源
- **无状态 vs 有状态**：`filter`/`map` 逐元素处理、无需缓冲；`sorted` 须收集完**全部**元素才能排序、`distinct` 的内部 Set 随去重数量增长——这两者才把整段数据放进内存；`limit` 只在链里记录剩余额度、取满即停，**不缓冲全量**
- `peek` 也是中间操作：不接终端操作**永远不会执行**

### 4.3 并行流的 Fork/Join 实现

并行流复用 Java 7 引入的 **Fork/Join 框架**（JSR 166y）：`Spliterator.trySplit()` 把数据递归拆成子任务，提交给共享的 `ForkJoinPool.commonPool`（默认并行度 = CPU 核数 - 1）。工作线程执行 **work-stealing（工作窃取）**——空闲线程从别的队列尾部偷任务，保证多核满载。

- **fork**：数据段不断对半切分；**计算**：各子任务独立跑同一流水线；**join**：`collect` 时各子任务先 `accumulate`，最后用 **`combiner`** 合并
- 这正是并行流**禁止共享可变状态**的原因：合并依赖「局部累加 → combiner 归约」，外部变量累加既无锁也不可合并，结果必然出错
- 何时值得：数据量足够大、元素处理相互独立且计算密集；否则切分/合并/调度开销大于收益（ph10 再深入）

### 4.4 Switch 表达式与模式匹配的编译期检查（穷尽性）

Switch Expressions 和模式匹配的「安全」不只靠运行时，更靠**编译期静态检查**：

- **穷尽性（exhaustiveness）**：编译期校验 switch 表达式覆盖所有可能输入——`int`/`String` 必须有 `default`；枚举需覆盖全部常量或有 `default`；Java 21 起对 sealed class 层次可校验覆盖全部 permitted 子类型后省略 `default`
- **穿透消除**：箭头标签（`->`）编译后每个分支独立跳转，天然不落入下一分支——「漏写 break」这类 bug 从语言层面消失
- **模式匹配的类型安全**：编译期检查类型合法性与模式变量流式作用域；switch 模式匹配按声明顺序匹配，`case null` 与守卫条件（`when`）的求值顺序由编译器保证
- **字节码层面**：仍是 `tableswitch`/`lookupswitch` 与 `instanceof`/`checkcast`，新增的是编译器在生成字节码**之前**完成的静态分析

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 集合过滤 / 映射 / 排序 / 去重 | `filter` / `map` / `sorted` / `distinct` / `limit` |
| 数据聚合统计（求和、平均、TopN） | `reduce` / `mapToInt` / `summarizingInt` / `min` / `max` |
| 分组报表（按班级、状态、地区） | `groupingBy` + 下游收集器 / `partitioningBy` / `joining` |
| 按条件查找单个元素 | `filter` + `findFirst` + `Optional` |
| 日志 / 文件逐行分析（衔接 ph07） | `Files.lines` + Stream 流水线 + `groupingBy` |
| 类型分派处理（消息、事件、支付） | Switch Expressions + Pattern Matching |
| 大批量独立计算加速 | `parallelStream`（数据量大且计算密集时） |

**不适合**此阶段的事项：

- 复杂状态机 / 多分支业务逻辑——用传统控制流，可读性远胜硬套 Stream
- 受检异常较多的业务代码——Stream 内抛受检异常要包装，循环里 try/catch 更直接
- 性能敏感的**超大集合**并行化——并行流线程模型与开销分析留到 ph10（JVM 与性能）
- Stream 调试困难的长链——拆中间变量、加 `peek`，必要时回退 for 循环，不要为「函数式」牺牲可维护性

## 6. 代码示例

本节展示完整可运行示例的关键片段，完整文件在 [`examples/`](./examples/) 目录（各文件的编译/运行命令与验证环境见 examples/README.md）。

### 示例 1：过滤学生成绩（filter + map + 统计）—— Java 8+

对应 roadmap 练习「过滤学生成绩」「统计平均分」：过滤及格、映射姓名、统计平均分与及格率。

```java
// examples/ex01-score-filter.java —— 过滤学生成绩：filter + map + 统计（已验证：OpenJDK 17.0.18）
import java.util.*;
import java.util.stream.*;

public class ScoreFilter {
    public static void main(String[] args) {
        List<Student> students = Arrays.asList(
                new Student("Alice", 92), new Student("Bob", 58),
                new Student("Cary", 76), new Student("Dana", 45));

        // filter 过滤 -> map 取姓名 -> collect 收集
        List<String> passed = students.stream()
                .filter(s -> s.score >= 60)
                .map(s -> s.name)
                .collect(Collectors.toList());
        System.out.println("及格名单: " + passed);

        double avg = students.stream().mapToInt(s -> s.score)
                .average().orElse(0);
        int max = students.stream().mapToInt(s -> s.score)
                .max().orElse(0);
        long passedCount = students.stream()
                .filter(s -> s.score >= 60).count();
        System.out.printf("平均分: %.1f, 最高分: %d, 及格率: %.0f%%%n",
                avg, max, passedCount * 100.0 / students.size());
    }

    static class Student {
        String name;
        int score;
        Student(String name, int score) { this.name = name; this.score = score; }
    }
}
```

提示：`mapToInt(...).average()` 返回 `OptionalDouble`，空集合时为 empty——用 `orElse(0)` 兜底，正是「Optional 表达可能为空」的典型出场；`Collectors.toList()` 换成 `Stream.toList()`（Java 16+）则得到不可变列表。

### 示例 2：按班级分组统计（groupingBy + summarizing）—— Java 8+

对应 roadmap 练习「按班级分组」「统计平均分」：`groupingBy` 分组 + `summarizingInt` 一次算出各班全部统计量。

```java
// examples/ex02-group-by-class.java —— 按班级分组统计：groupingBy + summarizingInt（已验证：OpenJDK 17.0.18）
import java.util.*;
import java.util.stream.*;

public class GroupByClass {
    public static void main(String[] args) {
        List<Student> students = Arrays.asList(
                new Student("一班", "Alice", 92), new Student("一班", "Bob", 58),
                new Student("二班", "Cary", 76), new Student("二班", "Dana", 88),
                new Student("三班", "Eve", 65));

        Map<String, IntSummaryStatistics> stats = students.stream()
                .collect(Collectors.groupingBy(
                        s -> s.clazz,
                        Collectors.summarizingInt(s -> s.score)));

        stats.forEach((clazz, st) -> System.out.printf(
                "%s: 人数=%d 平均=%.1f 最高=%d 最低=%d%n",
                clazz, st.getCount(), st.getAverage(), st.getMax(), st.getMin()));

        System.out.println("按平均分排名:");
        stats.entrySet().stream()
                .sorted((a, b) -> Double.compare(
                        b.getValue().getAverage(), a.getValue().getAverage()))
                .forEach(e -> System.out.println("  " + e.getKey()
                        + " 平均 " + e.getValue().getAverage()));
    }

    static class Student {
        String clazz, name;
        int score;
        Student(String clazz, String name, int score) {
            this.clazz = clazz; this.name = name; this.score = score;
        }
    }
}
```

提示：`groupingBy` 第一参数是**分类函数**（按什么分），第二参数是**下游收集器**（分了之后怎么统计）——报表统计的万能句式。

### 示例 3：设备状态筛选（Predicate 组合 + Optional 处理缺失）—— Java 8+

对应 roadmap 练习「设备状态筛选」：`Predicate.and` 组合条件，`findFirst` + `Optional` 处理「查无设备」。

```java
// examples/ex03-device-filter.java —— 设备状态筛选：Predicate 组合 + Optional 兜底（已验证：OpenJDK 17.0.18）
import java.util.*;
import java.util.function.*;
import java.util.stream.*;

public class DeviceFilter {
    public static void main(String[] args) {
        List<Device> devices = Arrays.asList(
                new Device("d-001", "online", 85), new Device("d-002", "offline", 60),
                new Device("d-003", "online", 30), new Device("d-004", "fault", 95));

        Predicate<Device> isOnline = d -> "online".equals(d.status);
        Predicate<Device> componentOk = d -> d.component >= 50;
        List<Device> candidates = devices.stream()
                .filter(isOnline.and(componentOk))        // Predicate 组合
                .collect(Collectors.toList());
        System.out.println("可调度设备: " + candidates);

        Optional<Device> found = devices.stream()
                .filter(d -> d.id.equals("d-999"))
                .findFirst();
        Device result = found.orElse(new Device("unknown", "offline", 0));  // 兜底默认对象
        System.out.println("查找 d-999: " + result);

        int component = devices.stream()
                .filter(d -> d.id.equals("d-001"))
                .findFirst()
                .map(d -> d.component)                    // 链式：存在才转换
                .orElseThrow(() -> new IllegalStateException("设备 d-001 不存在"));
        System.out.println("d-001 电量: " + component);
    }

    static class Device {
        String id, status;   // status: online / offline / fault
        int component;         // 0-100
        Device(String id, String status, int component) {
            this.id = id; this.status = status; this.component = component;
        }
        @Override public String toString() {
            return id + "(" + status + ", 电量" + component + "%)";
        }
    }
}
```

提示：`Optional.map` 把「值存在才转换」串进链上，`orElseThrow` 替代「判空 + 抛异常」两块样板——「按 ID 查，可能没有」是 Optional 的主战场。

### 示例 4：日志过滤统计（读取日志行 + Stream 流水线）—— Java 8+

对应 roadmap 推荐项目「日志过滤统计」，衔接 ph07：`Files.lines` 逐行读入，Stream 过滤、清洗、分组计数。

```java
// examples/ex04-log-stream.java —— 日志过滤统计：Files.lines + Stream 流水线（已验证：OpenJDK 17.0.18）
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.stream.*;

public class LogStream {
    public static void main(String[] args) throws IOException {
        Path log = Paths.get("app.log");
        Files.write(log, Arrays.asList(
                "2026-01-01 10:00:00 INFO 启动服务",
                "2026-01-01 10:00:01 ERROR 数据库连接超时",
                "2026-01-01 10:00:02 WARN 重试第 1 次",
                "2026-01-01 10:00:03 ERROR 数据库连接超时",
                "2026-01-01 10:00:04 ERROR 空指针: line 42"),
                StandardCharsets.UTF_8);

        try (Stream<String> lines = Files.lines(log, StandardCharsets.UTF_8)) {
            long errorCount = lines
                    .filter(line -> line.contains("ERROR"))
                    .count();
            System.out.println("ERROR 行数: " + errorCount);
        }   // Files.lines 的流用完必须关闭（同 ph07）

        try (Stream<String> lines = Files.lines(log, StandardCharsets.UTF_8)) {
            Map<String, Long> errors = lines
                    .filter(line -> line.contains("ERROR"))
                    .map(line -> line.replaceFirst("^.*ERROR ", ""))  // 清洗时间戳前缀
                    .collect(Collectors.groupingBy(msg -> msg, Collectors.counting()));
            errors.forEach((msg, n) -> System.out.println("  " + msg + " x " + n));
        }
        Files.deleteIfExists(log);
    }
}
```

提示：大日志靠 `Files.lines` 的**惰性流水线**逐行处理，内存占用恒定——是 ph07「大文件禁止整读」在 Stream 世界的正解；每个 `try` 块各开一个新 Stream（Stream 不可复用）。

### 示例 5：Switch Expressions 与 Pattern Matching——传统 switch 对照 + 新语法（Switch Expressions 14+ / instanceof 模式匹配 16+ / switch 模式匹配 21+）

对应 roadmap 练习「用 Switch Expressions 重写 if-else 分支」「用 Pattern Matching 改写 instanceof 判断」：先看传统 switch 的穿透问题，再看新语法如何消灭样板代码。完整文件拆为两个：`examples/ex05-switch-modern.java`（Java 14/16 语法，已验证）与 `examples/ex06-switch-pattern-matching.java`（switch 模式匹配，需 Java 21+）。

```java
// examples/ex05-switch-modern.java —— Switch Expressions + instanceof 模式匹配（已验证：OpenJDK 17.0.18）
// examples/ex06-switch-pattern-matching.java —— switch 模式匹配 + case null（Java 21+，未在本环境验证，本环境为 OpenJDK 17.0.18）
public class SwitchModern {
    public static void main(String[] args) {
        System.out.println("传统: " + traditional(3));

        int day = 3;   // Switch Expressions（Java 14+）：箭头语法无穿透
        String label = switch (day) {
            case 1, 2, 3 -> "工作日";
            case 6, 7 -> "周末";
            default -> "非法日期";          // int 必须 default（穷尽）
        };
        System.out.println("Switch Expressions: " + label);

        System.out.println("成绩: " + grade(85));   // yield：块体分支产出值

        printShape("hello");   // instanceof 模式匹配（Java 16+）
        printShape(42);
        printShape(3.14);

        System.out.println(classify("abc"));   // switch 模式匹配（Java 21+）
        System.out.println(classify(42));
        System.out.println(classify(null));
    }

    static String traditional(int day) {   // 传统 switch：每个 case 必须 break，漏写即穿透
        String r;
        switch (day) {
            case 1: case 2: case 3: r = "工作日"; break;
            case 6: case 7: r = "周末"; break;
            default: r = "非法日期";
        }
        return r;
    }

    static String grade(int score) {
        return switch (score / 10) {
            case 9 -> "优秀";
            case 10 -> {                        // 101~109 /10 也得 10，须再判越界
                yield score == 100 ? "优秀" : "非法分数";
            }
            case 8 -> "良好";
            case 7 -> "中等";
            case 6 -> "及格";
            default -> {
                if (score < 0 || score > 100) yield "非法分数";
                yield "不及格";
            }
        };
    }

    static void printShape(Object obj) {
        if (obj instanceof String s) {           // 模式变量 s 直接可用
            System.out.println("字符串, 长度 " + s.length());
        } else if (obj instanceof Integer i) {
            System.out.println("整数, 平方 " + (i * i));
        } else {
            System.out.println("其他: " + obj);
        }
    }

    static String classify(Object obj) {         // 需 Java 21+（case null / 类型模式）
        return switch (obj) {
            case null -> "空值";
            case String s -> "字符串: " + s;
            case Integer i -> "整数: " + i;
            case Long l -> "长整型: " + l;
            default -> "其他类型";
        };
    }
}
```

提示：上面片段合并展示两个示例文件——`ex05`（传统 switch 对照、Switch Expressions、`yield`、instanceof 模式匹配）在 Java 17 即可编译运行；`ex06` 的 `classify` 用了 `case null` 与 switch 类型模式，需 **Java 21+** 编译运行（本环境 OpenJDK 17.0.18 无法验证，见 examples/README.md 标注）。输出依次为：`传统: 工作日`、`Switch Expressions: 工作日`、`成绩: 良好`、`字符串, 长度 5`、`整数, 平方 1764`、`其他: 3.14`、`字符串: abc`、`整数: 42`、`空值`、`其他类型`。

## 7. 总结

### 关键要点

1. **Lambda 是函数式接口的语法糖**——`(参数) -> 表达式`，编译为 `invokedynamic` + `LambdaMetafactory`，非捕获 lambda 是单例
2. **先认四大函数式接口**——`Predicate` 判断、`Consumer` 消费、`Function` 转换、`Supplier` 提供
3. **Stream 描述流水线**——「源 → 中间操作（惰性构建 Sink 链）→ 终端操作（一次性触发求值）」；Stream 用完即弃，不可复用
4. **惰性 + 短路是性能来源**——`limit`/`anyMatch`/`findFirst` 满足条件即停；`sorted`/`distinct` 需缓冲整段数据
5. **collect 是结果汇聚器**——`groupingBy` + 下游收集器、`partitioningBy`、`summarizingInt`、`joining` 覆盖报表统计绝大多数需求
6. **Optional 表达可能为空**——`orElse`/`orElseGet`/`orElseThrow` 链式兜底，禁止裸调 `get()`，只用在返回值位置
7. **Switch Expressions 消除穿透**——箭头语法天然不 fall-through，`yield` 返回值，表达式必须穷尽
8. **Pattern Matching 消除强转样板**——instanceof 模式匹配（Java 16+）、switch 模式匹配与 `case null`（正式化于 Java 21+，17~20 为预览）
9. **并行流慎用**——共享 `ForkJoinPool.commonPool`，禁止共享可变状态，小数据更慢
10. **过度链式调用会降低可读性**——适时拆方法、拆中间变量，回退 for 循环不是倒退

### 跨语言对比：函数式数据处理

| 维度 | Java Stream | Python 列表推导 | Kotlin 集合 | C++ ranges | JS 数组方法 |
|------|-------------|-----------------|-------------|------------|-------------|
| 过滤 | `filter(Predicate)` | `[x for x in xs if 条件]` | `filter { 条件 }` | `views::filter` | `arr.filter(fn)` |
| 映射 | `map(Function)` | `[f(x) for x in xs]` | `map { f(it) }` | `views::transform` | `arr.map(fn)` |
| 聚合 | `reduce` / `collect` | `sum` / `functools.reduce` | `fold` / `reduce` | `std::accumulate` | `arr.reduce(fn, init)` |
| 惰性 | 中间操作惰性、终端触发 | 列表推导立即；生成器惰性 | 集合立即；`asSequence()` 惰性 | 视图默认惰性 | 数组方法立即求值 |
| 分组 | `Collectors.groupingBy` | `itertools.groupby` / 字典循环 | `groupBy` | 无内置，手写 map | `Object.groupBy`（ES2024） |
| 空值表达 | `Optional` | 无内置（`None` 检查） | 可空类型 `T?` + `?.` | `std::optional` | `?.` 可选链 + `??` |

对比结论：各语言都提供「过滤-映射-聚合」三件套，差异在**惰性与否**和**空值表达**——Java 用 Optional 把「可能为空」显式类型化，Kotlin 用可空类型在编译期强制处理，JS/Python 靠运行时约定；C++ ranges 与 Java Stream 一样强调惰性视图但无内置分组；Java 的 `groupingBy` 收集器是报表场景里最顺手的一档。

### 阶段验收清单

- [ ] 能写常见 Stream 操作：`filter`/`map`/`sorted`/`distinct`/`limit` 组合出可读流水线，并用 `collect` 收尾
- [ ] 能用 Switch Expressions 替代传统 switch：箭头语法、`yield` 返回值、穷尽性要求都理解
- [ ] 能用 Pattern Matching 简化类型判断：instanceof 模式匹配与 switch 模式匹配消除强转样板
- [ ] 能合理使用 Optional：`ofNullable`/`orElse`/`orElseThrow` 链式兜底，不裸调 `get()`，不用 Optional 做字段
- [ ] 能判断何时不用 Stream：简单循环、中途跳出、复杂状态累积场景能果断回退传统控制流
- [ ] 能解释 lambda 的 `invokedynamic` 实现与 Stream 的惰性求值（Sink 链）原理

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 5 题后继续，题目与 roadmap「练习」小节一一对应：

- **过滤学生成绩并统计平均分**：过滤及格、映射姓名、统计平均分与及格率（提示：`filter` → `map` → `collect(Collectors.toList())`；平均分用 `mapToInt(...).average().orElse(0)`）
- **按班级分组**：按班级分组并输出各班人数、平均分、最高分（提示：`groupingBy(clazz, summarizingInt(score))`，再对 `entrySet()` 流排序）
- **设备状态筛选**：按状态与电量组合筛选设备（提示：`Predicate.and`/`or` 组合，`findFirst` + `Optional.orElse` 处理查无设备）
- **用 Switch Expressions 重写 if-else 分支**：如成绩分级、周几判断（提示：箭头语法多值合并 `case 6, 7 ->`，块体用 `yield`，注意穷尽加 `default`）
- **用 Pattern Matching 改写 instanceof 判断**：类型分派处理（提示：`obj instanceof String s` 后直接用 `s`；Java 21 可用 switch 模式匹配 + `case null`）

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**日志过滤统计**——读取日志文件（衔接 ph07），用 Stream 过滤 ERROR/WARN、清洗行内容、按错误信息分组计数并输出 TopN，大文件用 `Files.lines` + try-with-resources 逐行处理保持内存恒定。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

roadmap 推荐的第二个项目「报表分组统计」（`groupingBy` + `summarizingInt`/`counting` + `partitioningBy` 输出表格报表，进阶用 `joining` 生成 CSV 行）作为扩展方向，示例 2 已给出核心句式。

### 下一阶段

[多线程与并发阶段](../ph09-concurrency/09-concurrency.md) —— Thread/Runnable、ExecutorService、synchronized/volatile、并发集合、CompletableFuture。
