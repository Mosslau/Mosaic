# Java IO 与文件操作阶段

> 面向企业级后端、微服务方向，读写文件并处理数据流——让配置、日志与数据的落地可靠、高效、不泄漏资源。

## 1. 概述

Java IO 与文件操作阶段的目标是：**能读写文件并处理数据流**——掌握 `File`、字节流（`InputStream`/`OutputStream`）与字符流（`Reader`/`Writer`）两套 API，用 `BufferedReader` 高效逐行处理文本，用 NIO 的 `Path`/`Files` 简化文件操作，并理解序列化与 CSV/JSON 数据文件的处理方式。本阶段是后续一切数据落地的基础：配置文件读取、日志分析、数据导入导出都从这里开始。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 文件与路径 | `File` 与 `Path`/`Files` 两代 API、目录遍历 |
| 字节流 | `InputStream`/`OutputStream`、二进制文件读写 |
| 字符流 | `Reader`/`Writer`、编码（Charset）与乱码 |
| 缓冲 | `BufferedReader`/`BufferedWriter`、`readLine` 逐行处理 |
| 资源管理 | try-with-resources 自动关闭流（衔接 ph06） |
| NIO 文件 API | `Files` 便捷方法、`Files.walk` 目录遍历 |
| 序列化 | `Serializable`、`transient`、`serialVersionUID` |
| 数据文件 | CSV 手写解析、JSON 第三方库了解 |

本阶段承接 ph06 异常处理阶段——IO 是受检异常（`IOException`）最主要的来源，流的关闭依赖 try-with-resources；不涉及 Lambda/Stream 流式处理（ph08）、网络编程（NIO 的 `Channel`/`Selector` 非阻塞模型在 ph14）、数据库访问（ph13）、以及 Jackson/Gson/Protobuf 等序列化框架（ph11 引入依赖后）。

## 2. 来源与演变

Java 1.0 的 `java.io` 包沿袭 C 语言 stdio 的思想——以**流（stream）**为抽象：数据像水流一样从源头流向目的地，读写双方只关心「流」而不关心底层介质是文件、内存还是网络。最初只有**字节流** `InputStream`/`OutputStream`（一切数据本质是字节），外加 `File` 类表达文件系统路径与元数据。1997 年 Java 1.1 引入**字符流** `Reader`/`Writer`：Java 的 `char` 是 16 位 Unicode 编码单元，直接用字节流读写文本会陷入编码转换的混乱，于是把「字节 → 字符的解码」封装进字符流内部，并同期加入对象**序列化**（`ObjectInputStream`/`ObjectOutputStream`）。

转折点在 Java 7（2011）：**NIO.2** 带来 `Path`/`Paths`/`Files` 三件套，弥补 `File` 类积累十几年的缺陷——方法混乱（`exists`/`isFile`/`isDirectory` 各自为政且不抛异常）、不支持符号链接、无法监听目录变化。同年 **try-with-resources** 成为语言机制，流关闭从「程序员自觉」变为「编译器保证」。Java 8 让 `Files.lines()`/`Files.walk()` 返回 `Stream`，把文件遍历接入函数式流水线，为 ph08 铺路。

此后演进趋于便利性：Java 11 的 `Path.of` 与 `Files.readString`/`writeString` 让最常用的文本读写缩成一行。但底层模型二十年未变——**字节流处理字节、字符流处理文本、NIO 提供现代文件 API**，三者并存至今，理解这一模型才能在读写、编码、性能、异常之间做出正确取舍。

| 版本 | 演进 |
|------|------|
| Java 1.0（1996） | `java.io` 字节流 `InputStream`/`OutputStream`、`File` 类 |
| Java 1.1（1997） | 字符流 `Reader`/`Writer`（Unicode 支持）、对象序列化 |
| Java 5（2004） | `java.util.Scanner`/`Formatter` 简化文本输入输出 |
| Java 7（2011） | NIO.2：`Path`/`Paths`/`Files`；try-with-resources 自动关闭 |
| Java 8（2014） | `Files.lines`/`Files.walk` 返回 `Stream`，与函数式结合 |
| Java 11（2018） | `Path.of`、`Files.readString`/`writeString` 简化文本读写 |

## 3. 语法与参数

### 3.1 File 与 Path/Files：两代文件 API

`File`（Java 1.0）代表文件或目录的**路径抽象**：判断存在、创建/删除、列目录、获取元数据。但它 API 混乱且不能正确处理符号链接，Java 7 起新代码应使用 `Path` + `Files`（`File` 未删除，仅兼容遗留代码）。

```java
File dir = new File("data");
if (!dir.exists()) {
    dir.mkdirs();                        // 创建多级目录
}
File f = new File(dir, "config.properties");
System.out.println("存在: " + f.exists() + ", 大小: " + f.length());
System.out.println("绝对路径: " + f.getAbsolutePath());
String[] names = dir.list();             // 列目录
```

- `File` 的 `exists`/`isFile`/`isDirectory`/`length`/`renameTo`/`delete` 都**不抛异常**，失败仅返回 `false`——错误原因无从得知（这是它被取代的主因）
- 新代码优先用 `Path`/`Files`（见 3.6）；两者可互转：`file.toPath()`、`path.toFile()`

### 3.2 InputStream / OutputStream：字节流

字节流以**字节（byte）**为单位读写，处理任意二进制数据（图片、压缩包、class 文件）。`InputStream` 的核心是 `read()`（返回 -1 表示读到末尾），`OutputStream` 的核心是 `write(b)`。

```java
// 写：字节 -> 文件
try (FileOutputStream out = new FileOutputStream("bin.dat")) {
    out.write(new byte[]{0x48, 0x65, 0x6C, 0x6C, 0x6F});   // "Hello"
}
// 读：一次读一个字节，-1 表示流末尾
try (FileInputStream in = new FileInputStream("bin.dat")) {
    int b;
    while ((b = in.read()) != -1) {
        System.out.printf("%02X ", b);
    }
}
```

- **二进制文件必须用字节流**：用字符流读写图片会因编码转换损坏数据
- `read()` 返回 `int` 而非 `byte`：用 -1 标记流末尾，避免与合法字节值 `0xFF`（byte 的 -1）冲突
- 一次读一个字节效率低：用 `read(byte[])` 批量读，或加缓冲流（见 3.4）

### 3.3 Reader / Writer：字符流与编码

字符流以**字符（char）**为单位读写文本，内部负责把字节按**字符集（Charset）**解码为 Unicode 字符。`FileReader`/`FileWriter` 是最简入口，但**默认使用平台编码**——这正是跨平台乱码的根源。

```java
// 写：显式指定 UTF-8，杜绝乱码
try (Writer writer = new OutputStreamWriter(
        new FileOutputStream("note.txt"), "UTF-8")) {
    writer.write("你好，Java IO");
}
// 读：用相同编码读回
try (Reader reader = new InputStreamReader(
        new FileInputStream("note.txt"), "UTF-8")) {
    int ch;
    while ((ch = reader.read()) != -1) {
        System.out.print((char) ch);
    }
}
```

- **字符流默认编码 = 平台编码**（中文 Windows 是 GBK，Linux/macOS 是 UTF-8），跨机器读写文本会乱码——**必须显式指定编码**（Java 11+ 可用 `new FileReader(path, StandardCharsets.UTF_8)`）
- 编码不一致的经典症状：出现「锟斤拷」、`?` 或乱码字符；**写入端用什么编码，读取端必须用同一编码**
- UTF-8 下「字符数 ≠ 字节数」：汉字占 3 字节，「你」的 `getBytes("UTF-8").length` 为 3 而 `length()` 为 1

### 3.4 BufferedReader / BufferedWriter：缓冲与 readLine

`read()`/`write()` 每次都触发底层系统调用，开销极大。**缓冲流（buffered stream）**在内存中维护一块缓冲区（默认 8192 字节），攒满才真正读写底层，大幅减少系统调用次数。

```java
try (BufferedWriter writer = new BufferedWriter(
        new FileWriter("lines.txt"))) {
    writer.write("第一行");
    writer.newLine();              // 写平台换行符，比 "\n" 更可移植
    writer.write("第二行");
}
try (BufferedReader reader = new BufferedReader(
        new FileReader("lines.txt"))) {
    String line;
    while ((line = reader.readLine()) != null) {   // null 表示读完
        System.out.println("读到: " + line);
    }
}
```

- `readLine()` 返回**不含行尾符**的字符串，读到末尾返回 `null`（不是空串）——循环条件别写错
- 包装模式：`new BufferedReader(new FileReader(path))`——内层负责字节→字符解码，外层负责缓冲与按行读取；需指定编码时改为 `new BufferedReader(new InputStreamReader(new FileInputStream(path), "UTF-8"))`
- 写完必须 `flush()` 或关闭流，否则缓冲区内容可能未落盘（try-with-resources 关闭时自动 flush）

### 3.5 try-with-resources：自动关闭资源

所有 IO 资源都实现了 `AutoCloseable`。ph06 强调的资源释放原则在本阶段是硬性要求：**每个打开的流都必须关闭**，否则文件句柄（file descriptor）泄漏，句柄耗尽时进程直接崩溃。

```java
// 错误示范：读完后不关流 —— 泄漏一个文件描述符
FileInputStream in = new FileInputStream("a.dat");
while (in.read() != -1) { /* 处理字节 */ }
// in 没有关闭

// 正确：try-with-resources，无论正常返回还是抛异常都自动关闭
try (FileInputStream in = new FileInputStream("a.dat")) {
    while (in.read() != -1) { /* 处理字节 */ }
}   // 离开 try 块即自动关闭，无需 finally
```

- 多个资源在 try 头用分号分隔，**关闭顺序与声明顺序相反**（后声明的先关，保证依赖方先于被依赖方释放）
- 关闭发生在 `catch` 之前；关闭自身抛出的异常被**抑制**（suppressed），可用 `e.getSuppressed()` 查看
- 手动 `finally` 关闭的繁琐写法见 ph06 示例 2，对照即可体会 try-with-resources 的价值

### 3.6 NIO 核心：Path、Paths、Files、walk

Java 7 的 NIO.2 提供现代文件 API：`Path` 表示路径（不可变），`Paths.get(...)` 创建，`Files` 提供全部静态操作——一次调用完成读写、复制、移动、遍历。

```java
Path dir = Paths.get("data");
Files.createDirectories(dir);              // 不存在则创建目录
Path p = dir.resolve("app.properties");    // 平台无关的路径拼接
Files.write(p, Arrays.asList("timeout=30", "retry=3"), StandardCharsets.UTF_8);
for (String line : Files.readAllLines(p, StandardCharsets.UTF_8)) {
    System.out.println(line);
}
Files.move(p, dir.resolve("app.bak"), StandardCopyOption.REPLACE_EXISTING);
Files.deleteIfExists(p);
System.out.println("是否存在: " + Files.exists(p));
```

- `Path` 是**不可变**的路径抽象：`resolve`（拼接）、`getParent`、`getFileName`、`normalize`（消除 `..`）
- `Files` 的静态方法都抛 `IOException`（受检）——异常信息远比 `File` 的布尔返回值明确
- **遍历目录树**用 `Files.walk(path)`（Java 8+）：返回深度优先的 `Stream<Path>`；它是流，**用完必须关闭**（try-with-resources）
- `Paths.get` 是 Java 7 写法，与 Java 11+ 的 `Path.of` 等价（roadmap 示例中的 `Path.of` 即此）
- 路径平台差异：Windows 用 `\`，Linux/macOS 用 `/`——**不要写死分隔符**，用 `Paths.get` 拼接或 `File.separator`

### 3.7 对象序列化：Serializable

序列化（serialization）把**内存中的对象图**转成字节流，可写文件、可传网络；反序列化（deserialization）再还原。Java 原生机制：实现 `java.io.Serializable` **标记接口**（不含任何方法）即可。

```java
static class User implements Serializable {
    private static final long serialVersionUID = 1L;  // 版本号，务必显式声明
    String name;
    transient String password;   // 不参与序列化（敏感字段）
    int age;
}
try (ObjectOutputStream out = new ObjectOutputStream(   // 序列化：对象 -> 字节流
        new FileOutputStream("user.ser"))) {
    out.writeObject(new User("Alice", "secret", 20));
}
try (ObjectInputStream in = new ObjectInputStream(      // 反序列化：字节流 -> 对象
        new FileInputStream("user.ser"))) {
    User u = (User) in.readObject();   // 返回 Object，需强转
    System.out.println(u.name + " / " + u.password + " / " + u.age);
    // 输出: Alice / null / 20 —— password 未序列化
}
```

- **`serialVersionUID` 必须显式声明**：不声明则 JVM 按类结构自动计算；类一旦增删字段，新旧版本 UID 不一致，反序列化抛 `InvalidClassException`——序列化最经典的坑
- `transient` 字段跳过序列化，反序列化后为默认值（引用类型 `null`、基本类型 0）
- 所有字段的类型也必须可序列化，否则抛 `NotSerializableException`
- 生产环境慎用 Java 原生序列化（跨语言不兼容、性能差、有安全风险），更常用 JSON/Protobuf；但理解 `Serializable` 是阅读框架源码（如 HttpSession 持久化）的前提

### 3.8 CSV 与 JSON 文件处理

CSV（逗号分隔值）是最简单的表格文本格式，本阶段用手写解析；JSON 是后端数据交换的事实标准，本阶段只做了解，正式解析交给第三方库。

```java
// Scanner 按行读取 + split 切分字段（Java 5+）
try (Scanner scanner = new Scanner(new File("score.csv"), "UTF-8")) {
    while (scanner.hasNextLine()) {
        String[] fields = scanner.nextLine().split(",");
        System.out.println(Arrays.toString(fields));
    }
}
```

JSON 解析**不要手写**（字符串转义、嵌套结构极易出错），生产环境用第三方库，ph11 学习引入依赖：Jackson 用 `new ObjectMapper().readValue(new File("user.json"), User.class)`，Gson 用 `new Gson().fromJson(new FileReader("user.json"), User.class)`。CSV 的值**没有类型**，数字、日期都要自己解析校验；字段**含逗号**时（如 `"Doe, John"`）`split(",")` 会把一个字段拆成多个——简单场景可先去掉首尾引号，工业级解析用 OpenCSV / Apache Commons CSV。

### 3.9 本阶段高频坑一览

| 坑 | 症状 | 对策 |
|----|------|------|
| 编码不一致 | 中文乱码（锟斤拷 / `?`） | 读写两端显式指定同一 Charset，统一 UTF-8 |
| 流未关闭 | 文件句柄泄漏，进程内文件数爆满 | 一律 try-with-resources |
| `Files.readAllLines` 读大文件 | 整个文件进内存，几百 MB 日志直接 OOM | 大文件用 `BufferedReader` 逐行 |
| 路径写死分隔符 | Windows `\` vs Linux `/`，程序不可移植 | `Paths.get` 拼接 / `File.separator` |
| 未声明 `serialVersionUID` | 类结构变化后 `InvalidClassException` | 显式声明版本号 |
| `File.exists()` 不抛异常 | 失败原因无从得知 | 改用 `Files` API，读 `IOException` |

## 4. 底层原理

### 4.1 字节流 vs 字符流的解码模型（Charset、UTF-8 多字节）

磁盘上只有字节，**文本 = 字节 + 编码**。字符流本质是字节流加一层**解码器（decoder）**：`FileInputStream`（字节）→ `InputStreamReader`（按 Charset 解码成 char）→ `BufferedReader`（缓冲 + 按行）。解码器的核心是变长编码的**字符边界判断**：UTF-8 按首字节的高位模式确定字符占几个字节——`0xxxxxxx` 为 1 字节（ASCII），`110xxxxx` 为 2 字节，`1110xxxx` 为 3 字节，`11110xxx` 为 4 字节。

| 字符 | Unicode 码点 | UTF-8 编码（十六进制） | Java char 表示 |
|------|--------------|----------------------|----------------|
| A | U+0041 | 41 | `'\u0041'` |
| 你 | U+4F60 | E4 BD A0 | `'\u4F60'` |
| 🚗 | U+1F697 | F0 9F 9A 97 | `'\uD83D'` + `'\uDE17'`（代理对） |

- 乱码根因：用错 Charset 时解码器把字节序列拆错，产生替换符 `�`（U+FFFD）或错位字符；中文场景最典型的是 GBK 与 UTF-8 互读
- Java 的 `char` 是 **UTF-16 编码单元**而非完整码点：emoji 等超出 BMP 的字符占 2 个 char（代理对 surrogate pair），`length()` 计数会「偏多」

### 4.2 缓冲流的内部缓冲与性能

`BufferedInputStream`/`BufferedReader` 内部维护一块缓冲区（默认 8192 字节/字符）：首次 `read()` 触发一次底层读**填满缓冲区**，后续 read 直接取内存数据；只有缓冲区耗尽才再次进入内核。`readLine()` 也只是在缓冲区里扫描换行符，不产生逐字符系统调用。这使系统调用次数从「字节数」降到「字节数 / 8192」：

| 读取方式 | 系统调用次数（约 1MB 文件） | 说明 |
|---------|---------------------------|------|
| 逐字节 `read()` | ~100 万次 | 每次进入内核，最慢 |
| `read(byte[8192])` 批量 | ~128 次 | 无缓冲但批量读 |
| `BufferedInputStream` + 逐字节读 | ~128 次 | 缓冲吞掉逐字节开销 |

`flush()` 把缓冲区内积压的数据强制写到底层；`close()` 前会自动 flush。结论：**任何流式 IO 都套缓冲**，除非场景要求实时性（如写日志后立刻断电恢复）。

### 4.3 File 与文件描述符的关系

打开文件的本质是进程向操作系统申请一个**文件描述符（file descriptor, fd）**——内核打开文件表中的索引。Java 的 `FileInputStream` 构造成功后，JVM 通过 native 调用 `open()` 拿到 fd 并封装在对象内部；`File` 类对象只是路径/元数据的门面，**不占用 fd**。

- 未关闭的流 = fd 泄漏：每个进程有 fd 上限（Linux 默认软限制通常为 1024），泄漏到上限后 `open()` 失败，抛 `IOException: Too many open files`
- **不要依赖 GC 回收句柄**：`finalize()` 已弃用且时机不可控——这就是必须 try-with-resources 的根本原因
- 平台差异：Unix 语义下删除的是目录项，**已打开的 fd 仍可读写**（inode 引用计数）；Windows 则直接失败（文件被占用）——删不掉文件时先怀疑是否有流未关闭

### 4.4 NIO 与阻塞 IO 的区别（为 ph14 网络铺垫）

本阶段的「NIO」指 NIO.2 的**文件 API**（Path/Files），与网络无关；真正的非阻塞新 IO 是 `java.nio.channels` 包：`Channel` + `Buffer` + `Selector` 模型。本阶段掌握阻塞文件 IO + NIO 文件 API 即可，网络非阻塞编程留到 ph14（网络编程）与 ph20（Netty）。

- **阻塞 IO（java.io）**：每个 `read`/`write` 调用阻塞当前线程直到完成；多连接需要多线程（一连接一线程），线程开销大
- **非阻塞 IO（NIO channels）**：一个线程用 `Selector` 同时监听大量 Channel 的就绪事件，**只读就绪的、跳过未就绪的**——适合高并发连接，是 Netty 的基础
- 文件 IO 层面的 NIO 优化：`FileChannel.transferTo`/`transferFrom` 支持**零拷贝**（Linux 上由 `sendfile` 完成，数据不经用户态内存）；`Files.copy` 的实现就会尝试走这条通道

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 读写配置文件（key=value） | `Files.readAllLines` / `Properties` + 异常处理 |
| 日志文件逐行分析 | `BufferedReader.readLine` + 正则 / `contains` |
| 二进制文件（图片、class、压缩包） | `FileInputStream`/`FileOutputStream` 字节流 |
| 大文件处理（几百 MB 日志） | 缓冲流逐行处理，避免整读内存 |
| 目录遍历与批量操作（重命名、统计） | `Files.walk` + `Files.move` |
| 对象持久化（缓存、会话） | `Serializable` + `ObjectOutputStream` |
| CSV 表格数据导入导出 | Scanner / 字符流 + `split` 解析 |

**不适合**此阶段的事项：

- Lambda/Stream 流式处理——`Files.lines` 的流水线写法留到 ph08
- NIO 网络编程（`Channel`/`Selector` 非阻塞模型）——ph14
- ORM 与 JDBC——数据库读写不归文件 IO，ph13
- JSON/XML 深度解析与序列化框架（Jackson/Gson/Protobuf）——ph11 引入依赖后再系统使用

## 6. 代码示例

### 示例 1：读取配置文件（Files.readAllLines + 解析 key=value）

对应 roadmap 练习「读取配置文件」：解析 `key=value` 格式，忽略空行与 `#` 注释。

```java
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

public class ReadConfig {
    public static Map<String, String> load(String path) throws IOException {
        Map<String, String> config = new HashMap<>();
        for (String line : Files.readAllLines(Paths.get(path), StandardCharsets.UTF_8)) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) {
                continue;                        // 跳过空行和注释
            }
            int idx = line.indexOf('=');
            if (idx > 0) {
                config.put(line.substring(0, idx).trim(),
                        line.substring(idx + 1).trim());
            }
        }
        return config;
    }

    public static void main(String[] args) throws IOException {
        Files.write(Paths.get("app.properties"),
                Arrays.asList(
                        "# 数据库配置",
                        "db.url=jdbc:mysql://localhost:3306/app",
                        "timeout=30"),
                StandardCharsets.UTF_8);
        Map<String, String> config = load("app.properties");
        System.out.println("timeout = " + config.get("timeout"));
        System.out.println("db.url  = " + config.get("db.url"));
        Files.deleteIfExists(Paths.get("app.properties"));
    }
}
```

提示：JDK 自带 `java.util.Properties` 也支持 key=value 解析（`props.load(reader)`），但建议先手写一遍，理解「读行 → 切分 → 清理」的解析逻辑；配置文件通常很小，`Files.readAllLines` 完全够用。

### 示例 2：日志分析（BufferedReader 逐行 + 正则/contains 统计）

对应 roadmap 练习「日志分析」：统计 ERROR 总数与各错误信息的出现次数，逐行处理保证大日志文件内存占用恒定。

```java
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.regex.*;

public class LogAnalyzer {
    public static void main(String[] args) throws IOException {
        Files.write(Paths.get("app.log"),
                Arrays.asList(
                        "2026-01-01 10:00:00 INFO 启动服务",
                        "2026-01-01 10:00:01 ERROR 数据库连接超时",
                        "2026-01-01 10:00:02 WARN 重试第 1 次",
                        "2026-01-01 10:00:03 ERROR 数据库连接超时",
                        "2026-01-01 10:00:04 ERROR 空指针: line 42"),
                StandardCharsets.UTF_8);
        Pattern errorPattern = Pattern.compile("ERROR (.+)$");  // 捕获错误信息
        Map<String, Integer> errorCount = new LinkedHashMap<>();
        int total = 0;

        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(
                        new FileInputStream("app.log"), "UTF-8"))) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.contains("ERROR")) {
                    total++;
                    Matcher m = errorPattern.matcher(line);
                    if (m.find()) {
                        errorCount.put(m.group(1),
                                errorCount.getOrDefault(m.group(1), 0) + 1);
                    }
                }
            }
        }

        System.out.println("ERROR 总数: " + total);
        for (Map.Entry<String, Integer> e : errorCount.entrySet()) {
            System.out.println("  " + e.getKey() + " x " + e.getValue());
        }
        Files.deleteIfExists(Paths.get("app.log"));
    }
}
```

### 示例 3：CSV 解析（Scanner 按行 + split，处理引号简单情况）

对应 roadmap 练习「CSV 解析」：解析学生成绩表并计算平均分，简单处理引号字段。

```java
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

public class CsvParser {
    public static void main(String[] args) throws IOException {
        // 样例数据：引号仅作装饰（字段内不含逗号）
        Files.write(Paths.get("scores.csv"),
                Arrays.asList(
                        "name,class,score",
                        "\"Alice\",一班,90",
                        "Bob,一班,85",
                        "Cary,二班,78"),
                StandardCharsets.UTF_8);
        List<String[]> rows = new ArrayList<>();
        try (Scanner scanner = new Scanner(new File("scores.csv"), "UTF-8")) {
            while (scanner.hasNextLine()) {
                rows.add(parseLine(scanner.nextLine()));
            }
        }
        int total = 0;
        for (int i = 1; i < rows.size(); i++) {          // 跳过表头
            total += Integer.parseInt(rows.get(i)[2]);
        }
        System.out.println("平均分: " + (total / (rows.size() - 1)));

        for (String[] row : rows) {
            System.out.println(Arrays.toString(row));
        }
        Files.deleteIfExists(Paths.get("scores.csv"));
    }

    // 简单引号处理：切分后去除字段首尾引号；
    // 字段内含逗号（如 "Doe, John"）时 split 会拆错，需 OpenCSV 等专业库
    static String[] parseLine(String line) {
        String[] fields = line.split(",");
        for (int i = 0; i < fields.length; i++) {
            fields[i] = fields[i].trim().replace("\"", "");
        }
        return fields;
    }
}
```

### 示例 4：批量重命名（Files.walk + move）

对应 roadmap 练习「批量重命名」：把目录树中所有 `.log` 文件改名为 `.txt`，展示 NIO 遍历 + 移动的写法。

```java
import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.stream.*;

public class BatchRename {
    public static void main(String[] args) throws IOException {
        // 准备测试目录树
        Path root = Paths.get("logs");
        Files.createDirectories(root);
        Files.write(root.resolve("a.log"), "a".getBytes());
        Files.write(root.resolve("b.log"), "b".getBytes());
        Files.createDirectories(root.resolve("sub"));
        Files.write(root.resolve("sub").resolve("c.log"), "c".getBytes());
        // 遍历整棵目录树，重命名所有 .log（renameToTxt 会打印结果）
        try (Stream<Path> paths = Files.walk(root)) {     // 流用完必须关闭
            paths.filter(Files::isRegularFile)
                 .filter(p -> p.toString().endsWith(".log"))
                 .forEach(BatchRename::renameToTxt);
        }
        deleteTree(root);
    }

    static void renameToTxt(Path p) {
        try {
            String name = p.getFileName().toString();
            Path target = p.resolveSibling(
                    name.substring(0, name.length() - 4) + ".txt");
            Files.move(p, target, StandardCopyOption.REPLACE_EXISTING);
            System.out.println(p + " -> " + target);
        } catch (IOException e) {
            System.err.println("重命名失败: " + p + " (" + e.getMessage() + ")");
        }
    }

    // 自底向上删除目录树：先删子节点，再删目录本身
    static void deleteTree(Path root) throws IOException {
        try (Stream<Path> paths = Files.walk(root)) {
            paths.sorted(Comparator.reverseOrder())
                 .forEach(p -> {
                     try { Files.deleteIfExists(p); } catch (IOException ignored) { }
                 });
        }
    }
}
```

提示：这里用到的 `filter`/`forEach` 只是 `Files.walk` 返回 `Stream` 的配套用法，Stream 的完整能力（map/reduce/collect）将在 ph08 系统学习。

### 示例 5：对象序列化与反序列化（Serializable + ObjectOutputStream）

对应 roadmap 学习内容「序列化」：保存/恢复用户对象，演示 `transient` 与版本号。

```java
import java.io.*;

public class ObjectSerialization {
    // 必须实现 Serializable；显式声明版本号，防止类结构变化后无法反序列化
    static class User implements Serializable {
        private static final long serialVersionUID = 1L;
        String name;
        int age;
        transient String password;    // 敏感字段不落盘

        User(String name, int age, String password) {
            this.name = name;
            this.age = age;
            this.password = password;
        }

        @Override
        public String toString() {
            return "User{name='" + name + "', age=" + age
                    + ", password='" + password + "'}";
        }
    }

    public static void main(String[] args) {
        String file = "user.ser";
        try {
            // 序列化：对象 -> 字节流
            try (ObjectOutputStream out = new ObjectOutputStream(
                    new FileOutputStream(file))) {
                out.writeObject(new User("Alice", 20, "secret"));
            }
            // 反序列化：字节流 -> 对象
            try (ObjectInputStream in = new ObjectInputStream(
                    new FileInputStream(file))) {
                User u = (User) in.readObject();
                System.out.println("恢复: " + u);   // password 为 null
            }
            new File(file).delete();
        } catch (IOException | ClassNotFoundException e) {
            System.err.println("序列化失败: " + e.getMessage());
        }
    }
}
```

提示：反序列化**不调用构造器**，直接按字段赋值（`transient` 字段为默认值）；后续类增加字段时，只要 `serialVersionUID` 不变，旧数据仍可读取，新字段取默认值。

## 7. 总结

### 关键要点

1. **字节流处理二进制，字符流处理文本**——`InputStream`/`OutputStream` 按字节，`Reader`/`Writer` 按字符并负责编码转换
2. **IO 必须处理异常**——所有文件操作都可能抛 `IOException`（受检），配合 try-with-resources 保证资源释放
3. **编码必须显式指定**——读写两端同一 Charset，中文场景统一 UTF-8，否则乱码
4. **缓冲能提升 IO 性能**——`BufferedReader`/`BufferedInputStream` 把系统调用次数降几个数量级，大文件逐行处理
5. **文件路径要考虑平台差异**——用 `Paths.get` 拼接、不写死分隔符；Windows 与 Unix 的删除/占用语义也不同
6. **NIO 简化文件操作**——`Files` 一行完成读写/复制/移动/遍历，异常信息明确，取代 `File` 的布尔返回值
7. **序列化必须显式声明 `serialVersionUID`**——否则类结构一变化就 `InvalidClassException`
8. **大文件禁止整体读入内存**——`Files.readAllLines` 只适合小文件，几百 MB 日志用缓冲流逐行
9. **`Files.walk` 返回的流用完必须关闭**——目录遍历同样要 try-with-resources

### 跨语言对比：IO 抽象

| 维度 | Java | C（FILE*） | Go（os.File） | Python（open） | Rust（File） |
|------|------|-----------|---------------|----------------|--------------|
| 打开文件 | `FileInputStream` / `Files.newBufferedReader` | `fopen(path, "r")` | `os.Open(path)` | `open(path)` | `File::open(path)` |
| 逐行读取 | `BufferedReader.readLine()` | `fgets(buf, n, fp)` | `bufio.Scanner` | `for line in f:` | `BufReader::read_line` |
| 错误处理 | checked `IOException`（编译期强制） | 返回 `NULL` + `errno` | 返回 `error` 值（显式检查） | 抛 `OSError` | `Result<T, io::Error>` |
| 资源释放 | try-with-resources 自动关闭 | `fclose(fp)` 手动 | `defer f.Close()` | `with` 语句自动关闭 | Drop 作用域结束自动释放 |
| 路径表示 | `Path`（NIO.2） | 字符串 + 平台分隔符 | `filepath` 包 | `pathlib.Path` | `PathBuf` |
| 二进制支持 | 字节流原生支持 | 原生（FILE 即字节流） | `[]byte` 切片 | `open(path, "rb")` | `Vec<u8>` |

对比结论：所有语言都把「文件 = 字节序列 + 句柄 + 释放时机」抽象成类似模型，差异在错误处理与资源释放机制——C 最原始（手动 `fclose` + `errno`），Go/Rust 把错误当**值**显式返回，Java 用受检异常在编译期强制处理，Python 靠异常与 `with` 约定；而字符流的**编码显式化**是 Java 的特色（Go/Python 默认 UTF-8，C/Rust 编码完全自理）。

### 阶段验收标准

- 能读写文本文件：字符流 + 缓冲 + 显式 UTF-8 编码，读回内容与写入一致
- 能处理文件异常：`IOException` 的捕获与传播，try-with-resources 保证流不泄漏
- 能用 NIO 简化文件操作：用 `Files` 读写/复制/移动/遍历替代手工流
- 能区分字节流与字符流：二进制文件用字节流，文本用字符流，并解释编码转换过程
- 能完成对象序列化与反序列化：`Serializable` + `transient` + `serialVersionUID`

### 进入下一阶段前

确保能完成以下练习：

- **读取配置文件**：解析 `key=value`，忽略空行与 `#` 注释（提示：先用 `Files.readAllLines` 读入，再手写「去空白 → 跳过注释 → 按 `=` 切分」；也可对比 `Properties.load` 的写法）
- **日志分析**：统计 ERROR/WARN 行数与关键词出现次数（提示：`BufferedReader.readLine` 逐行 + `contains`/正则提取信息，输出排序后的统计结果）
- **CSV 解析**：解析成绩表，计算平均分、按列筛选（提示：Scanner 或字符流按行 + `split(",")`；字段含逗号时了解 OpenCSV 即可，不必深究）
- **批量重命名**：目录树中所有 `.log` 改为 `.txt`，或批量加前缀/序号（提示：`Files.walk` + `Files.move(REPLACE_EXISTING)`，注意流关闭与重名覆盖）

### 推荐项目

- **文件复制工具**：支持文件/目录复制、按字节数显示进度、覆盖确认；用字节流 + 缓冲实现复制逻辑，再对比 `Files.copy` 的写法，统计耗时与复制字节数
- **目录统计工具**：递归统计目录下的文件总数、总大小、各扩展名数量与占比；用 `Files.walk` 遍历 + `Files.size` 汇总，输出表格形式的统计报告

### 下一阶段

**Lambda 与 Stream 阶段**（`ph08-lambda-stream`，文档规划中）—— 函数式接口、lambda 表达式、Stream API 与 Optional 链式处理。
