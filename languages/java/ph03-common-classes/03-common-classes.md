# Java 常用类阶段

> 面向企业级后端、微服务和数据平台，建立字符串处理、数值计算与日期时间的标准库使用能力。

## 1. 概述

Java 常用类阶段的目标是：**能正确选择 String/StringBuilder，用 BigDecimal 避免精度丢失，用 java.time 替代旧日期 API，并理解包装类型的自动装箱机制**。本阶段覆盖日常开发中最高频的标准库类，是写出健壮 Java 代码的前提。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 字符串处理 | String、StringBuilder、StringBuffer、Text Blocks（Java 15+） |
| 数值计算 | Math、Random、BigDecimal |
| 日期时间 | LocalDate、LocalDateTime、DateTimeFormatter |
| 包装类型 | Integer/Long/Double 等、自动装箱与拆箱 |

本阶段只涉及常用基础类，**不涉及集合框架、Stream API 和 IO 操作** — 那些是 **ph04 集合框架**、**ph08 Lambda 与 Stream**、**ph07 IO 与文件操作**阶段的内容。

## 2. 来源与演变

Java 标准库的设计一直在演进，常用类的变迁尤其能体现这一点：

- **String 的不可变设计**：Java 1.0 起 String 就是不可变对象。动机有三——安全（字符串常量可共享，不会被意外修改）、哈希缓存（hashCode 只需计算一次）、线程安全（不可变对象天然安全）。代价是拼接操作会产生大量中间临时对象，因此 Java 1.0 就提供了 StringBuffer，Java 5 又引入非线程安全的 StringBuilder 以消除同步开销。
- **旧 Date 的缺陷**：`java.util.Date` 和 `Calendar` 从 Java 1.0/1.1 起就存在，但设计糟糕——可变对象（线程不安全）、月份从 0 开始、API 混乱。Java 8（2014）引入 `java.time` 包，借鉴 Joda-Time 设计，提供不可变、线程安全、API 清晰的日期时间类。
- **BigDecimal 的精度需求**：浮点数遵循 IEEE 754，无法精确表示大多数十进制小数（如 0.1 在二进制中是无限循环小数）。在金融计算中，`0.1 + 0.2` 不等于 `0.3` 是不可接受的，因此需要 BigDecimal 提供任意精度的十进制运算。

本文示例以 **Java 17**（LTS）为基线（`java.time` 需 Java 8+、Text Blocks 需 Java 15+），本环境验证工具链为 OpenJDK 17.0.16。String、BigDecimal、`java.time` 的核心语义自 Java 8 起稳定。

## 3. 语法与参数

### 3.1 String：不可变字符串

String 最常用的方法是比较、查找、截取和替换。所有"修改"操作都返回新 String 对象，原字符串不变。

```java
String s = "hello";
s.equals("hello");          // true，比较内容
s.length();                 // 5
s.charAt(0);                // 'h'
s.substring(1, 4);          // "ell"（左闭右开）
s.contains("el");           // true
s.replace("l", "L");        // "heLLo"——返回新对象
```

String 不可变意味着每次拼接都创建新对象。在循环中这是严重的性能陷阱：

```java
String result = "";
for (int i = 0; i < 10000; i++) {
    result += i;  // 每次循环 new 一个 StringBuilder + new 一个 String，极低效
}
```

**String 常用方法速查**（高频方法不用背，会查 javadoc 即可；真正要记的是"不可变 → 每次操作返回新串"这一条）：

| 方法 | 作用 | 示例 |
|------|------|------|
| `split(regex)` | 按分隔符拆成数组 | `"a,b".split(",")` → `["a", "b"]` |
| `String.join(delim, parts)` | 静态方法，把序列拼成串 | `String.join("-", list)` → `"a-b-c"` |
| `strip()` / `trim()` | 去首尾空白（`strip` 处理 Unicode，Java 11+） | `" x ".strip()` → `"x"` |
| `indexOf` / `lastIndexOf` | 查找子串位置，找不到返回 -1 | `"hello".indexOf("l")` → 2 |
| `startsWith` / `endsWith` | 前后缀判断 | `name.endsWith(".java")` |
| `toUpperCase` / `toLowerCase` | 大小写转换 | `"ab".toUpperCase()` → `"AB"` |
| `isEmpty` / `isBlank` | 空判断（`isBlank` 含纯空白串，Java 11+） | `"  ".isBlank()` → true |
| `repeat(n)` | 重复自身（Java 11+） | `"-".repeat(3)` → `"---"` |
| `formatted(args)` | 模板格式化（Java 15+） | `"%s:%d".formatted("id", 1)` |

工程直觉：`split`、`strip`、`isBlank`、`formatted` 在日志解析与文本处理里几乎是日常标配；而判断字符串是否相等永远用 `equals`，`==` 只比较引用——这是 Java 新手第一大坑。

### 3.2 StringBuilder：可变字符串

StringBuilder 在同一个内部缓冲区上修改，避免中间对象。常用 `append`、`insert`、`delete`、`reverse`，支持链式调用。

```java
StringBuilder sb = new StringBuilder();
sb.append("Hello");
sb.append(" Java");
sb.insert(5, ",");
sb.delete(5, 6);
String result = sb.toString();
```

```java
// 链式写法，紧凑清晰
String result = new StringBuilder()
    .append("ID:").append(1001)
    .append(", Name:").append("Alice")
    .toString();
```

| 类 | 线程安全 | 引入版本 | 适用场景 |
|---|---------|---------|---------|
| String | 不可变，天然安全 | Java 1.0 | 少量拼接、常量字符串 |
| StringBuilder | 否 | Java 5 | 单线程大量拼接（**首选**） |
| StringBuffer | 是（synchronized） | Java 1.0 | 多线程拼接（极少使用） |

StringBuffer 所有公开方法都用 `synchronized` 修饰，性能不如 StringBuilder。除非明确需要跨线程共享可变字符串缓冲区，否则始终用 StringBuilder。

**容量与扩容**：`StringBuilder` 内部是一个 `char[]` 缓冲区，`new StringBuilder()` 默认容量 16；追加内容超过容量时自动扩容（新数组容量变大并搬移旧内容），频繁扩容有搬移成本：

```java
StringBuilder sb = new StringBuilder();       // 默认容量 16
System.out.println(sb.capacity());            // 16
sb.append("0123456789abcdef");                // 长度 16，恰好不触发扩容

StringBuilder big = new StringBuilder(1024);  // 预分配：能预估长度就给出容量
for (String line : lines) {
    big.append(line);
}
```

`capacity()`（缓冲区容量）与 `length()`（当前有效长度）是两个概念：容量 ≥ 长度。**能预估最终长度时用 `new StringBuilder(capacity)` 预分配**，把多次扩容压成一次——这正是 5 章选型表里"循环内大量拼接"场景的完整姿势。

### 3.3 Text Blocks（Java 15+）

Text Blocks 用 `"""..."""` 包裹多行字符串，编译期处理缩进。

```java
String json = """
    {
        "name": "Alice",
        "age": 20
    }
    """;
```

编译器以**结束符 `"""` 的位置**为基准，去除每行前导空格。结束符在单独一行时，基准缩进为结束符前的空格数。如果某行内容比基准缩进更短，只去除到实际空格数为止。行末的 `\` 可以抑制换行（拼接长行）。

### 3.4 Math 与 Random

Math 提供常用数学函数；Random 生成伪随机数。

```java
Math.abs(-5);               // 5
Math.max(3, 7);             // 7
Math.pow(2, 10);            // 1024.0
Math.sqrt(16);              // 4.0
Math.round(3.6);            // 4

Random rand = new Random();
rand.nextInt(100);          // [0, 100) 内随机整数
rand.nextDouble();          // [0.0, 1.0) 内随机浮点
```

### 3.5 BigDecimal：精确十进制

BigDecimal 用于金融和需要精确保留小数位数的场景。核心陷阱：**必须用字符串构造**。

```java
// 错误：浮点字面量传入时已经丢失精度
BigDecimal a = new BigDecimal(0.1);
// a 实际值是 0.1000000000000000055511151231257827021181583404541015625

// 正确：用字符串构造
BigDecimal a = new BigDecimal("0.1");
BigDecimal b = new BigDecimal("0.2");
BigDecimal sum = a.add(b);           // 0.3，精确
```

常用运算，注意除法必须指定精度和舍入模式：

```java
BigDecimal a = new BigDecimal("10.50");
BigDecimal b = new BigDecimal("3");

a.add(b);               // 加法
a.subtract(b);          // 减法
a.multiply(b);          // 乘法
a.divide(b, 2, RoundingMode.HALF_UP);  // 除法，保留 2 位小数
a.setScale(0, RoundingMode.HALF_UP);   // 四舍五入到整数：11
a.compareTo(b);         // 比较数值大小（不要用 equals）
```

`equals` 同时比较数值和 scale，因此 `new BigDecimal("2.0").equals(new BigDecimal("2.00"))` 为 `false`。比较数值大小始终用 `compareTo`。

**金额的另一种工业做法：整数"分"存储**。BigDecimal 精确但慢（对象 + 大整数运算），适合汇率、多小数位、任意精度场景；而**纯金额（人民币、美元都只有两位小数）常见做法是直接用 `long` 存"分"**：

| 方案 | 表示 | 优点 | 代价 |
|------|------|------|------|
| `long`（分） | `1999` = 19.99 元 | 快、省内存、无精度问题 | 展示要自己除以 100；乘法后注意溢出（金额大时用 `BigInteger` 或小心） |
| `BigDecimal` | `"19.99"` | 任意精度、语义清晰 | 慢、代码啰嗦 |

取舍口诀：**跨系统/协议传金额用分单位整数最省心（避免序列化的精度坑）；系统内部做复杂财务计算（分摊、汇率）用 BigDecimal**。两者互转要小心：`BigDecimal.valueOf(1999L, 2)` 表示 1999 分 → 19.99。

### 3.6 java.time：日期与时间

Java 8 的 `java.time` 是不可变且线程安全的。核心类为 `LocalDate`（日期）、`LocalDateTime`（日期+时间）、`DateTimeFormatter`（格式化）。

```java
LocalDate today = LocalDate.now();              // 当天日期
LocalDate specific = LocalDate.of(2026, 8, 8);  // 指定日期
LocalDateTime now = LocalDateTime.now();         // 当前日期时间

DateTimeFormatter fmt = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");
String formatted = now.format(fmt);              // 格式化
LocalDateTime parsed = LocalDateTime.parse("2026-08-08 14:30", fmt); // 解析
```

常用日期计算：

```java
today.plusDays(7);              // 7 天后
today.minusMonths(1);           // 1 月前
today.getDayOfWeek();           // 星期几（DayOfWeek 枚举）
today.isAfter(LocalDate.of(2026, 1, 1));  // 比较先后
```

禁止使用 `new Date()` 和 `Calendar`（除非维护遗留代码处理旧 API 边界）。

**时间戳与跨时区：Instant 与互转**。`LocalDate`/`LocalDateTime` 是"本地视角"（不带时区），跨进程传递时间（存数据库、前后端传 JSON）应使用**时间戳（UTC 绝对时刻）**：

```java
Instant now = Instant.now();              // 当前 UTC 时间戳
long epoch = now.getEpochSecond();        // 秒级时间戳（存库/传参用这个）
Instant back = Instant.ofEpochSecond(epoch);  // 从时间戳还原

// LocalDateTime ↔ Instant 必须经过时区
ZonedDateTime zdt = LocalDateTime.of(2026, 8, 8, 14, 30)
        .atZone(ZoneId.of("Asia/Shanghai"));
Instant inst = zdt.toInstant();                    // 本地时间 → UTC 时刻
LocalDateTime restored = inst.atZone(ZoneId.of("Asia/Shanghai")).toLocalDateTime();

// 与遗留 java.util.Date 互转（旧代码边界）
Date legacy = Date.from(inst);
Instant again = legacy.toInstant();
```

工程约定一句话：**存储与传输一律用 UTC（`Instant`/epoch 秒），只有展示时才转本地时区**——否则服务器时区一换，全库的时间全错。`LocalDateTime` 的命名容易误导：它不代表"某个真实时刻"，只是"墙上时间"，脱离时区它不能唯一对应一个时刻。

### 3.7 包装类型与自动装箱拆箱

8 种基本类型各有对应的包装类：`int → Integer`、`long → Long`、`double → Double`、`boolean → Boolean`、`char → Character`、`byte → Byte`、`short → Short`、`float → Float`。

自动装箱（autoboxing）和拆箱（unboxing）由编译器自动插入转换代码：

```java
Integer i = 42;       // 自动装箱 → Integer.valueOf(42)
int n = i;            // 自动拆箱 → i.intValue()

List<Integer> list = new ArrayList<>();
list.add(100);        // 自动装箱
int val = list.get(0); // 自动拆箱
```

核心陷阱——Integer 缓存池（-128 ~ 127）：

```java
Integer i1 = 127;
Integer i2 = 127;
System.out.println(i1 == i2);  // true（命中缓存，同一对象）

Integer i3 = 128;
Integer i4 = 128;
System.out.println(i3 == i4);  // false（超出缓存，不同对象）
```

结论：包装类型比较内容始终用 `equals()`，不要用 `==`。

**拆箱的另一面：null 会抛 NPE**。自动拆箱的本质是调用 `xxxValue()`——包装对象为 `null` 时拆箱即空指针：

```java
Integer count = null;
int n = count;              // NPE!拆箱 → count.intValue()

Integer score = null;
if (score > 60) { ... }     // NPE!score 与 int 比较时先自动拆箱

// 典型现场：从 Map/List 取值赋给基本类型
Integer raw = map.get("age");   // 键不存在时返回 null
int age = raw;                  // NPE——很多线上空指针都长这样
```

| 场景 | 为什么炸 | 修法 |
|------|---------|------|
| `int n = 包装null` | 拆箱调 `intValue()` 遇 null | 先判空再拆箱，或让 `Integer` 一路保持到使用处 |
| 包装类型参与算术/比较 | 运算前自动拆箱 | 参与运算前确认非 null（`Objects.requireNonNull` 或显式判空） |
| `Map.get` / `List.get` 结果直接赋基本类型 | 容器允许 null | 判空 + 给默认值（`map.getOrDefault` 等） |

**"包装类型可以持有 null"是它与基本类型最本质的差别**——它是"能表示缺失"的对象，而 `int` 不行。这个特性让包装类型适合做"可空字段"，代价就是拆箱 NPE；本阶段建立"拆箱即取值、取值先判空"的反射，比记住所有 NPE 场景更有效。

## 4. 底层原理

### 4.1 String 常量池

字符串字面量（如 `"hello"`）在编译期进入 class 文件的常量池，类加载后进入运行时常量池（位于堆中）。当代码中出现相同的字面量时，JVM 返回同一引用。这与 ph01 中提到的字符串池是同一个机制。

```java
String a = "hello";
String b = "hello";
System.out.println(a == b);  // true，复用常量池中同一对象
```

`new String("hello")` 则明确在堆上新建对象，不复用常量池实例。`intern()` 方法可手动将字符串加入常量池并返回池中引用，但通常不推荐手动干预。

### 4.2 自动装箱与 IntegerCache

自动装箱调用 `Integer.valueOf(int)` 而非 `new Integer(int)`。`valueOf` 在 -128 到 127 范围内返回内部缓存数组中的同一对象，超出则新建。这是空间换时间的优化——小整数使用频率极高，复用对象可显著减少 GC 压力。

```java
// Integer.valueOf 的简化实现逻辑
public static Integer valueOf(int i) {
    if (i >= -128 && i <= 127) {
        return IntegerCache.cache[i + 128];
    }
    return new Integer(i);
}
```

Long（-128~127）、Short（-128~127）、Byte（全部 256 个值，byte 范围 -128~127 全覆盖）、Character（0~127）、Boolean（`TRUE`/`FALSE` 两个常量）也有类似缓存机制。Double 和 Float 没有缓存——浮点数的值空间连续且不可数，缓存意义不大。

### 4.3 BigDecimal 内部表示

BigDecimal 内部由两部分组成：一个 `BigInteger`（无精度限制的整数）作为**未缩放值**（unscaledValue），加上一个 `int scale` 表示**小数位数**。例如 `new BigDecimal("12.340")` 内部是 `unscaledValue=12340`、`scale=3`，实际值 = `unscaledValue × 10^(-scale)`。

BigDecimal 的 `equals` 同时比较 unscaledValue 和 scale，因此 `new BigDecimal("2.0")` 和 `new BigDecimal("2.00")` 不相等——尽管数值相同，但 scale 不同（1 vs 2）。这也是为什么比较数值必须用 `compareTo`。

## 5. 使用场景

| 场景 | 推荐选择 | 理由 |
|------|---------|------|
| 少量字符串拼接（< 5 次） | `+` 或 `String` | 编译器会优化为 StringBuilder |
| 循环内大量拼接 | `StringBuilder` | 避免中间对象，性能最优 |
| 多行文本（JSON/SQL/HTML） | Text Blocks（JDK 15+） | 可读性好，避免大量转义 |
| 金额计算 | `BigDecimal(String)` | 精确十进制，字符串构造避免浮点陷阱 |
| 科学计算 | `double` | 性能远优于 BigDecimal |
| 日期存储与计算 | `LocalDate` / `LocalDateTime` | 不可变、线程安全、API 清晰 |
| 日期格式化/解析 | `DateTimeFormatter` | 线程安全，替代 SimpleDateFormat |
| 集合中的数值元素 | 包装类型（自动装箱） | 泛型不支持基本类型 |
| 随机数 | `Random` / `ThreadLocalRandom` | 后者多线程性能更好 |

不适合的使用方式：高并发计数用 `AtomicLong` 而非包装类型（包装类型的 `++` 不是原子操作）；超过 19 位整数用 `BigInteger` 而非 BigDecimal；格式化以外的复杂时区转换用 `ZonedDateTime`；不可变键值对用 `record` 而非包装类型数组。

## 6. 代码示例

> 完整可运行文件见 [`examples/`](./examples/)，每个示例对应一个 `ex0*-*.java`，已在本环境用 OpenJDK 17.0.16 验证（编译零错误、输出符合预期）。

### 示例 1：字符串反转（利用 StringBuilder.reverse）

完整文件：`examples/ex01-StringReverse.java`

```java
public class StringReverse {
    public static String reverse(String s) {
        return new StringBuilder(s).reverse().toString();
    }

    public static void main(String[] args) {
        System.out.println(reverse("hello"));      // olleh
        System.out.println(reverse("Java"));       // avaJ
        System.out.println(reverse("上海自来水"));   // 水来自海上
    }
}
```

### 示例 2：字符频次统计（用数组做计数器）

完整文件：`examples/ex02-CharFrequency.java`

```java
public class CharFrequency {
    public static void main(String[] args) {
        String text = "hello world";
        int[] freq = new int[128]; // 覆盖 ASCII 范围

        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            if (ch < 128) {
                freq[ch]++;
            }
        }

        for (int i = 0; i < 128; i++) {
            if (freq[i] > 0) {
                System.out.println((char) i + " : " + freq[i]);
            }
        }
    }
}
```

### 示例 3：金额计算——浮点陷阱与 BigDecimal 正确用法

完整文件：`examples/ex03-MoneyCalc.java`

```java
import java.math.BigDecimal;
import java.math.RoundingMode;

public class MoneyCalc {
    public static void main(String[] args) {
        // 浮点陷阱：0.1 + 0.2 不等于 0.3
        double a = 0.1;
        double b = 0.2;
        System.out.println("浮点 0.1 + 0.2 = " + (a + b));
        // 输出：0.30000000000000004

        // BigDecimal 正确做法
        BigDecimal price = new BigDecimal("19.99");
        BigDecimal quantity = new BigDecimal("3");
        BigDecimal total = price.multiply(quantity);
        System.out.println("单价 19.99 x 3 = " + total);  // 59.97

        // 含税计算：保留两位小数，四舍五入
        BigDecimal withTax = total.multiply(new BigDecimal("1.13"))
                .setScale(2, RoundingMode.HALF_UP);
        System.out.println("含税(13%) = " + withTax);      // 67.77
    }
}
```

### 示例 4：日期格式化、计算与解析

完整文件：`examples/ex04-DateDemo.java`

```java
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;

public class DateDemo {
    public static void main(String[] args) {
        // 当前日期
        LocalDate today = LocalDate.now();
        System.out.println("今天: " + today);

        // 格式化
        DateTimeFormatter fmt = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");
        LocalDateTime now = LocalDateTime.now();
        System.out.println("当前时间: " + now.format(fmt));

        // 日期计算：7 天后送达
        LocalDate delivery = today.plusDays(7);
        long daysUntil = ChronoUnit.DAYS.between(today, delivery);
        System.out.println("预计送达: " + delivery + "（" + daysUntil + " 天后）");

        // 解析字符串
        LocalDate christmas = LocalDate.parse("2026-12-25");
        System.out.println("解析日期: " + christmas + " 是 " + christmas.getDayOfWeek());
    }
}
```

### 示例 5：验证码生成器 + Integer 缓存演示

完整文件：`examples/ex05-CaptchaDemo.java`

```java
import java.util.Random;

public class CaptchaDemo {
    // 生成指定长度的验证码（去除易混淆字符 I/O/0/1）
    public static String generate(int length) {
        String chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
        Random rand = new Random();
        StringBuilder sb = new StringBuilder(length);
        for (int i = 0; i < length; i++) {
            sb.append(chars.charAt(rand.nextInt(chars.length())));
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        // 自动装箱：int → Integer
        Integer count = 5;  // 等价 Integer.valueOf(5)

        System.out.println("生成 " + count + " 个验证码:");
        for (int i = 0; i < count; i++) {  // 自动拆箱
            System.out.println("  " + generate(6));
        }

        // Integer 缓存范围演示
        Integer a = 127, b = 127;
        Integer c = 128, d = 128;
        System.out.println("127 == 127: " + (a == b));          // true（命中缓存）
        System.out.println("128 == 128: " + (c == d));          // false（不同对象）
        System.out.println("128 equals 128: " + c.equals(d));   // true（内容比较）
    }
}
```

## 7. 总结

### 关键要点

1. **String 不可变**——每次"修改"返回新对象，循环拼接用 StringBuilder
2. **StringBuilder 高效可变**——同一缓冲区操作，支持链式 append，单线程首选
3. **StringBuffer 线程安全但不常用**——所有方法 synchronized，性能不及 StringBuilder
4. **Text Blocks 简化多行文本**——编译期自动去除公共前导空格，JDK 15+，`"""..."""`
5. **金额必须用 BigDecimal**——`new BigDecimal("0.1")`，禁止用浮点构造
6. **BigDecimal 除法必须指定精度**——`divide(value, scale, RoundingMode)`
7. **BigDecimal 比较用 compareTo**——`equals` 同时比较 scale，2.0 不等于 2.00
8. **日期时间用 java.time**——`LocalDate`/`LocalDateTime`/`DateTimeFormatter`，不可变、线程安全；禁止 `new Date()`
9. **包装类型用 equals 比较**——`Integer.valueOf` 缓存 -128~127，超出范围 `==` 失效
10. **自动装箱调的是 valueOf**——装箱 `Integer.valueOf(i)`，拆箱 `i.intValue()`；编译期语法糖

### 跨语言对比：字符串处理

| 需求 | Java | Go | Python | Rust |
|------|-----|----|--------|------|
| 不可变字符串 | `String` | `string` | `str` | `String` |
| 可变拼接 | `StringBuilder` | `strings.Builder` | `"".join()` / `io.StringIO` | `String::push_str` |
| 预分配容量 | `new StringBuilder(256)` | `var b strings.Builder; b.Grow(256)` | 不适用 | `String::with_capacity(256)` |
| 拼接风格 | `sb.append("x")` | `b.WriteString("x")` | `"-".join(parts)` | `s.push_str("x")` |
| 多行字符串 | `"""..."""`（JDK 15+） | 反引号 raw string | `"""..."""` | `r#"..."#` |

### 阶段验收清单

- [ ] 能正确选择 String/StringBuilder，解释不可变性的性能影响
- [ ] 能用 BigDecimal 做金额运算，理解浮点构造陷阱
- [ ] 能用 java.time 完成日期格式化与计算
- [ ] 能解释 Integer 缓存机制和 `==` vs `equals` 的区别
- [ ] 能用 Text Blocks 写多行文本（SQL/JSON 等）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：验证码生成器（可配置长度、字符集，批量生成）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[集合框架阶段](../ph04-collections/04-collections.md) — List、Set、Map、迭代器与排序。
