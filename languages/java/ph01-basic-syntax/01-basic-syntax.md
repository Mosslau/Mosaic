# Java 基础语法阶段

> 面向企业级后端、微服务、高并发系统方向，从 JDK/JRE/JVM、静态类型和 Java 程序结构起步。

## 1. 概述

Java 基础语法阶段的目标是：**能写简单 Java 程序，理解 JDK、JRE、JVM 和 Java 程序结构**。与其他语言不同，Java 的入门涉及三个关键概念——JDK（开发工具包）、JRE（运行环境）和 JVM（虚拟机），以及"万物皆在类中"的组织方式。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 平台 | JDK / JRE / JVM 三者关系 |
| 程序结构 | `class`、`main` 方法、`System.out.println` |
| 数据 | 变量、常量、基本类型（Primitive Type）vs 引用类型（Reference Type） |
| 控制流 | 运算符、`if`/`switch`、`for`/`while` |
| 数组 | 固定长度数组、遍历、边界检查 |

Java 基础语法阶段是进入 OOP（面向对象编程）之前的必要铺垫——你写的第一行 Java 代码就已经在 `class` 里面了。

## 2. 来源与演变

Java 由 James Gosling 于 1995 年在 Sun Microsystems 发布，最初的设计目标是为消费电子设备创建一种**可移植、安全**的编程语言。其核心理念"Write Once, Run Anywhere"（一次编写，到处运行）影响了整个软件开发产业。

| 版本 | 年份 | 标志性变化 |
|------|------|-----------|
| Java 1.0 | 1996 | JDK 1.0，Applet、AWT |
| Java 5 | 2004 | 泛型、注解、增强 for、自动装箱 |
| Java 8 | 2014 | **Lambda**、Stream API、Optional、新的日期时间 API |
| Java 10 | 2018 | `var` 局部变量类型推导（JEP 286） |
| Java 11 | 2018 | **LTS**，新发布节奏下首个长期支持版，HttpClient 标准化 |
| Java 17 | 2021 | **LTS**，Records、Sealed Classes、Pattern Matching |
| Java 21 | 2023 | **LTS**，Virtual Threads、Record Patterns、Sequenced Collections |

> **LTS（长期支持版本）**：Java 8、11、17、21 是 LTS 版本，生产环境首选。基础语法与版本关系不大，但建议使用 Java 17+ 以获得更好的开发体验。

## 3. 语法与参数

### 3.1 程序结构：万物皆在类中

```java
// Main.java — 文件名必须与 public class 名一致
public class Main {                          // 类定义
    public static void main(String[] args) { // 程序入口
        System.out.println("Hello, Java");   // 控制台输出
    }
}
```

编译和运行：

```bash
javac Main.java    # 编译 → 生成 Main.class（字节码）
java Main          # 在 JVM 上运行
```

**关键概念**：
- Java 代码**先编译成字节码（Bytecode）再在 JVM 上运行**——这不同于 C 的直接编译或 Python 的直接解释
- `main` 方法签名是固定的：`public static void main(String[] args)`
- 源文件名必须与 `public class` 名一致

**`public static void main` 各关键字含义**：

| 关键字 | 含义 | 为什么 |
|--------|------|--------|
| `public` | 公开可见 | JVM 需要从类外部调用 `main`，必须是 `public` |
| `static` | 属于类而非实例 | JVM 调用 `main` 时还没有创建任何对象，只能通过类名调用静态方法 |
| `void` | 无返回值 | `main` 结束时程序即退出，通过 `System.exit(0)` 或异常码传递状态 |
| `String[] args` | 命令行参数数组 | 接收用户在命令行传入的参数 |

初学者不用深究，记住这是一个固定模板即可。OOP 阶段会逐一理解每个关键字。

### 3.2 JDK、JRE、JVM

| 组件 | 全称 | 职责 |
|------|------|------|
| **JVM** | Java Virtual Machine | 执行字节码，提供内存管理和 JIT 编译 |
| **JRE** | Java Runtime Environment | JVM + 标准库，用于运行 Java 程序 |
| **JDK** | Java Development Kit | JRE + 编译器（`javac`）+ 开发工具，用于开发 Java 程序 |

**JDK ⊃ JRE ⊃ JVM**。开发只需要安装 JDK，它包含 JRE。

### 3.3 变量与基本类型

Java 是**静态类型**语言——**每个变量都必须声明类型**，类型在编译时确定。

| 类型 | 大小 | 范围 | 默认值 |
|------|------|------|--------|
| `byte` | 1 字节 | -128 ~ 127 | 0 |
| `short` | 2 字节 | -32768 ~ 32767 | 0 |
| `int` | 4 字节 | -2³¹ ~ 2³¹-1 | 0 |
| `long` | 8 字节 | -2⁶³ ~ 2⁶³-1 | 0L |
| `float` | 4 字节 | ~6-7 位精度 | 0.0f |
| `double` | 8 字节 | ~15 位精度 | 0.0d |
| `boolean` | 未定义 | `true` / `false` | `false` |
| `char` | 2 字节 | 0 ~ 65535 (Unicode) | `'\u0000'` |

```java
int age = 25;                 // 基本类型
long big = 100_000_000_000L;  // long 字面量加 L
double pi = 3.14159;
boolean flag = true;
char letter = 'A';

// 常量
final int MAX_SIZE = 100;

// Java 10+ 局部变量类型推导
var name = "Java";    // 编译器推导为 String
var count = 42;       // 推导为 int
// var 只能用于局部变量，且必须初始化
```

### 3.4 运算符

| 类别 | 运算符 | 示例 |
|------|--------|------|
| 算术 | `+ - * / %` | `a + b`, `x % 2` |
| 关系 | `== != < > <= >=` | `a == b`（基本类型比较值） |
| 逻辑 | `&& \|\| !` | `a > 0 && b > 0`（短路求值） |
| 赋值 | `= += -= *= /=` | `x += 1` |
| 自增自减 | `++ --` | `i++`（后置）, `++i`（前置） |
| 三元 | `? :` | `max = a > b ? a : b` |
| 位运算 | `& \| ^ ~ << >>` | `n & 1`（判断奇偶） |

> **`==` 陷阱**：对于基本类型 `==` 比较值，对于引用类型（String、数组等）`==` 比较的是内存地址。**比较对象内容永远用 `.equals()`**。

### 3.5 基本类型 vs 引用类型

```java
// 基本类型（Primitive Type）：直接存值
int a = 10;
int b = a;      // b = 10，是值的拷贝
a = 20;         // b 仍然是 10

// 引用类型（Reference Type）：存的是对象地址
int[] arr1 = {1, 2, 3};
int[] arr2 = arr1;   // arr2 指向同一个数组对象
arr1[0] = 99;        // arr2[0] 也变成 99
```

| 特性 | 基本类型 | 引用类型 |
|------|---------|---------|
| 存储 | 直接存值（栈） | 存对象地址（对象在堆） |
| 传参 | 传值拷贝 | 传引用的拷贝 |
| 默认值 | 有定义（如 0, false） | `null` |
| 比较 | `==` 比较值 | `==` 比较地址，`equals()` 比较内容 |

### 3.6 控制流

```java
// if/else — 与 C 语法一致
if (score >= 90) {
    System.out.println("A");
} else if (score >= 60) {
    System.out.println("Pass");
} else {
    System.out.println("Fail");
}

// switch — Java 14+ 支持箭头语法
switch (day) {
    case 1 -> System.out.println("Monday");
    case 2 -> System.out.println("Tuesday");
    default -> System.out.println("Other");
}

// for — 与 C 语法一致
for (int i = 0; i < 5; i++) {
    System.out.println(i);
}

// 增强 for（for-each）— Java 5+
int[] nums = {1, 2, 3, 4};
for (int n : nums) {
    System.out.println(n);
}

// while
int n = 5;
while (n > 0) {
    System.out.println(n--);
}

// do-while — 至少执行一次
int m = 0;
do {
    System.out.println("执行一次");
} while (m > 0);
```

### 3.7 数组

```java
// 声明和初始化
int[] nums = new int[5];           // 默认值为 0
int[] scores = {90, 85, 78, 92};  // 直接初始化

// 二维数组
int[][] matrix = {
    {1, 2, 3},
    {4, 5, 6}
};

// 遍历
for (int i = 0; i < scores.length; i++) {
    System.out.println(scores[i]);
}

// for-each 遍历
for (int s : scores) {
    System.out.println(s);
}

// 数组工具方法（需 import java.util.Arrays;）
int[] copied = Arrays.copyOf(scores, scores.length);
Arrays.sort(scores);
System.out.println(Arrays.toString(scores));
```

**关键概念**：
- Java 数组是**对象**，`length` 是属性（不是方法）
- 数组一旦创建，长度就**不可改变**
- 数组越界抛出 `ArrayIndexOutOfBoundsException`（而不是像 C 那样导致 UB）

### 3.8 String（引用类型中的特例）

```java
String s1 = "hello";
String s2 = "hello";          // 字符串池（String Pool）复用
String s3 = new String("hello");  // 强制创建新对象

// 常用方法
int len = s1.length();
String upper = s1.toUpperCase();
String sub = s1.substring(1, 4);  // "ell"
boolean eq = s1.equals(s2);       // true（内容比较）
boolean same = (s1 == s2);        // true（地址比较，池中同一对象）
boolean diff = (s1 == s3);        // false（不同对象）

// 拼接
String full = s1 + " world";
String formatted = String.format("Name: %s, Age: %d", "Alice", 30);
// Java 15+ 文本块
String json = """
    {
        "name": "Java",
        "version": 21
    }
    """;
```

**重要**：比较字符串内容用 `equals()`，**永远不要用 `==`** 比较字符串内容（`==` 比较的是引用地址）。

### 3.9 输入输出

```java
import java.util.Scanner;

Scanner scanner = new Scanner(System.in);
System.out.print("Enter name: ");
String name = scanner.nextLine();
System.out.print("Enter age: ");
int age = scanner.nextInt();
System.out.printf("Name: %s, Age: %d%n", name, age);
scanner.close();
```

> **常见坑**：`nextInt()` / `nextDouble()` 只读取数字，不消费行尾的换行符。如果紧接着用 `nextLine()`，会直接读到空行。解决方法：在数字输入后额外加一行 `scanner.nextLine();` 消费换行符。

## 4. 底层原理

### 4.1 Java 程序的执行流程

```
Main.java  ──javac(编译)──▶  Main.class（字节码）
    ↓                              ↓
  Java 源码                   JVM 加载执行
                              ↓
                    解释执行 + JIT 编译 → 本地机器码
```

**JIT（Just-In-Time）编译器**：JVM 在运行时将频繁执行的热点代码（Hotspot）编译为本地机器码，让 Java 程序达到接近 C/C++ 的性能。

### 4.2 基本类型为什么存在

```java
int a = 42;          // 栈上直接存值，无需对象开销
Integer b = 42;      // 堆上分配对象（自动装箱 Auto-boxing）
```

基本类型（Primitive Type）的存在是为了**性能**——避免每次使用整数都要在堆上创建对象。Java 为每个基本类型提供了对应的**包装类**（Wrapper Class）：`Integer`、`Double`、`Boolean` 等，用于需要对象的场景（如泛型容器）。

### 4.3 字符串池（String Pool）

```java
String a = "hello";   // 从字符串常量池中获取
String b = "hello";   // 复用池中已有的 "hello"
String c = new String("hello");  // 在堆上新创建，绕过池
```

字符串池是 JVM 内部的一个特殊内存区域，用于缓存字符串字面量。这是 `String` 不可变（Immutable）的一个重要原因——不可变才能安全共享。

### 4.4 JVM 内存区域基础

JVM 运行时主要分为两大区域：**堆**（Heap，存放所有对象实例）和**虚拟机栈**（VM Stack，存放局部变量和方法调用帧）。基础语法阶段只需要记住：**对象在堆上分配，局部变量在栈上**。方法区（存储类信息）和垃圾回收（GC）等细节在后续阶段深入。

## 5. 使用场景

基础语法阶段适合解决的问题：

| 场景 | 涉及知识点 |
|------|-----------|
| 计算器 | 变量、switch、Scanner 输入 |
| 素数判断 | 循环、条件分支 |
| 数组统计 | 数组定义、遍历、最值/均值 |
| 九九乘法表 | 嵌套循环、格式化输出 |
| 成绩统计 | 数组、条件分支 |

## 6. 代码示例

> **说明**：示例 2 起会用到自定义静态方法——方法将在下一阶段（ph02 面向对象 OOP）详解，此处模仿写法即可。

### 示例 1：命令行计算器

```java
import java.util.Scanner;

public class Calculator {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);

        System.out.print("输入算式 (如 3 + 4): ");
        double a = scanner.nextDouble();
        String op = scanner.next();
        double b = scanner.nextDouble();

        double result = switch (op) {
            case "+" -> a + b;
            case "-" -> a - b;
            case "*" -> a * b;
            case "/" -> b != 0 ? a / b : Double.NaN;
            default -> {
                System.out.println("不支持的操作符");
                yield 0;
            }
        };

        System.out.printf("%.2f %s %.2f = %.2f%n", a, op, b, result);
        scanner.close();
    }
}
```

### 示例 2：判断素数

```java
public class PrimeCheck {
    static boolean isPrime(int n) {
        if (n < 2) return false;
        for (int i = 2; i * i <= n; i++) {
            if (n % i == 0) return false;
        }
        return true;
    }

    public static void main(String[] args) {
        System.out.print("1-100 的素数: ");
        for (int i = 1; i <= 100; i++) {
            if (isPrime(i)) {
                System.out.print(i + " ");
            }
        }
        System.out.println();
    }
}
```

### 示例 3：数组统计

```java
public class ArrayStats {
    public static void main(String[] args) {
        int[] scores = {78, 92, 85, 63, 99, 71};

        int sum = 0, max = scores[0], min = scores[0];
        for (int s : scores) {
            sum += s;
            if (s > max) max = s;
            if (s < min) min = s;
        }

        double avg = (double) sum / scores.length;
        System.out.printf("人数: %d%n", scores.length);
        System.out.printf("平均分: %.2f%n", avg);
        System.out.printf("最高: %d, 最低: %d%n", max, min);
    }
}
```

### 示例 4：九九乘法表

```java
public class MultiplicationTable {
    public static void main(String[] args) {
        for (int i = 1; i <= 9; i++) {
            for (int j = 1; j <= i; j++) {
                System.out.printf("%d×%d=%-2d  ", j, i, i * j);
            }
            System.out.println();
        }
    }
}
```

### 示例 5：猜数字游戏

```java
import java.util.Random;
import java.util.Scanner;

public class GuessNumber {
    public static void main(String[] args) {
        Random random = new Random();
        int secret = random.nextInt(100) + 1;
        int attempts = 0;
        Scanner scanner = new Scanner(System.in);

        System.out.println("猜一个 1-100 之间的数字！");

        while (true) {
            System.out.print("你的猜测: ");
            int guess = scanner.nextInt();
            attempts++;

            if (guess < secret) {
                System.out.println("太小了！");
            } else if (guess > secret) {
                System.out.println("太大了！");
            } else {
                System.out.printf("猜对了！共尝试 %d 次。%n", attempts);
                break;
            }
        }
        scanner.close();
    }
}
```

## 7. 总结

### 关键要点

1. **Java 代码先编译成字节码再在 JVM 上运行** — 编译和运行的分离是 Java 的核心特征
2. **基本类型和引用类型不同** — 基本类型存值，引用类型存地址
3. **`main` 是程序入口** — 签名固定：`public static void main(String[] args)`
4. **数组长度固定且会做边界检查** — `ArrayIndexOutOfBoundsException` 保护你不受越界影响
5. **字符串比较用 `equals()`** 而不是 `==`
6. **万物皆在类中** — 即使是最简单的程序也需要 `class`

### 跨语言对比：基础语法

| 特性 | C | C++ | Java |
|------|---|-----|------|
| 执行方式 | 编译为机器码 | 编译为机器码 | 编译为字节码 + JVM |
| 程序入口 | `int main()` | `int main()` | `public static void main(String[])` |
| 空值 | `NULL` | `nullptr` | `null` |
| 数组 | `int a[5]` | `int a[5]` 或 `std::array` | `int[] a = new int[5]` |
| 字符串 | `char*` | `std::string` | `String` |
| 边界检查 | 无 | 无（裸数组） | 有，抛异常 |
| 代码组织 | 函数 | 函数 + 类 | 强制在类中 |

### 阶段验收标准

- 能编译并运行单文件 Java 程序（`javac` + `java`）
- 能解释 JDK、JRE、JVM 的区别
- 能用循环和数组完成基础练习
- 能区分基本类型和引用类型的行为差异

### 进入下一阶段前

确保能完成以下练习：
- 计算器（支持 `+ - * /`）
- 判断素数
- 九九乘法表
- 数组最大值、最小值、平均值

### 推荐项目

- **成绩统计工具**：录入多个成绩，计算平均分、最高分、最低分和等级分布
- **猜数字游戏**：随机生成 1-100 的数字，提示"太大"/"太小"

### 下一阶段

[面向对象 OOP 阶段](../ph02-oop/02-oop.md) — 深入 class、对象、封装、继承、多态和接口。
