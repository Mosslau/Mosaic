# Java 异常处理阶段

> 面向企业级后端、微服务方向，写出稳定、可维护的错误处理代码——让异常路径行为可预期、资源不泄漏、根因可追溯。

## 1. 概述

Java 异常处理阶段的目标是：**能写出稳定、可维护的错误处理代码**——正确使用 `try/catch/finally` 捕获与传播异常，区分 checked exception 与 unchecked exception，设计语义清晰的业务异常体系，并优先用 `try-with-resources` 释放资源。同时掌握异常链（cause）与 `Optional` 的取舍，为 ph15 的统一异常处理框架打下语义基础。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 基本结构 | `try` / `catch` / `finally` 的语法与执行顺序 |
| 抛出与声明 | `throw` 主动抛异常、`throws` 声明受检异常、异常沿调用栈传播 |
| 异常分类 | checked exception（受检）与 unchecked exception（非受检）的强制规则 |
| 自定义异常 | 业务异常基类、错误码、构造器链设计 |
| 异常链 | `cause` 根因传递、`getCause()`、`printStackTrace()` 完整堆栈 |
| 资源管理 | try-with-resources（Java 7+）、`AutoCloseable`、multi-catch |
| 现代替代 | `Optional` 处理可空返回值，与异常互补 |

本阶段承接 ph05 泛型阶段（业务异常体系常与泛型 `Result<T>` 封装配合使用）；不涉及 IO 与文件操作的完整 API（ph07）、并发异常与线程中断（ph09）、微服务全局异常拦截与 `@RestControllerAdvice`（Spring，ph15）。

## 2. 来源与演变

异常处理思想源于 LISP 的 `handler-case` 与 C++ 的异常机制。Java 1.0 发布时即内置完整的异常体系，并做出一个影响深远的决定——**区分受检异常（checked exception）与非受检异常（unchecked exception）**：前者由编译器强制处理，后者仅出现在运行时。这一设计此后成为语言设计界最富争议的话题之一：支持者认为它让「失败是可能发生的」成为方法签名的一部分，调用方无法视而不见；反对者认为它导致接口污染与被迫的 catch/throws 样板代码。Java 官方在 Java 8 引入 `Optional` 后，checked exception 的使用场景被进一步收窄，但机制本身保留至今。

Java 异常机制在后来的版本中持续演进：**Java 7** 引入 **try-with-resources** 与 **multi-catch**，从语法层面消灭了资源泄漏与 catch 样板代码；**Java 8** 引入 **Optional**，提供「结果可能为空」的声明式方案，与异常形成互补；**Java 14+** 起 JVM 为 `NullPointerException` 生成更详细的提示信息，帮助快速定位空指针根因。

本文示例以 **Java 17** 为基线（try-with-resources 自 7 起、multi-catch 自 7 起），验证工具链 OpenJDK 17.0.16。

| 版本 | 演进 |
|------|------|
| Java 1.0（1996） | 引入完整异常体系：`throw`/`throws`、`try`/`catch`/`finally`、`Error`/`Exception`/`RuntimeException` 层次 |
| Java 1.4（2002） | 链式异常 API：`initCause`、`getCause`、`printStackTrace(PrintWriter)` |
| Java 7（2011） | try-with-resources、multi-catch、更精确的重抛异常类型 |
| Java 8（2014） | `Optional` 声明式处理可空返回值 |
| Java 9（2017） | try-with-resources 支持 effectively final 变量 |
| Java 14+（2020） | 更友好的 `NullPointerException` 提示消息（helpful NPE） |

## 3. 语法与参数

### 3.1 try / catch / finally 基本结构

`try` 块包裹可能抛出异常的代码；`catch` 捕获并处理特定异常；`finally` 无论是否抛出异常都会执行，传统上用于释放资源。

```java
try {
    int result = 100 / divisor;          // divisor 为 0 时抛 ArithmeticException
    System.out.println("结果: " + result);
} catch (ArithmeticException e) {
    System.out.println("除数不能为 0: " + e.getMessage());
} finally {
    System.out.println("无论成功失败都会执行");
}
```

- `try` 必须至少搭配一个 `catch` 或 `finally`；`catch` 可以有多个，按声明顺序匹配**第一个**匹配的类型
- `finally` 中**不要** `return` 或再抛异常——它会覆盖 try/catch 中的返回值与异常，掩盖真实错误

### 3.2 throw 与 throws：抛出与声明

`throw` 主动抛出一个异常对象（抛出的是对象，不是类型）；`throws` 在方法签名上声明该方法可能抛出的受检异常，把处理责任交给调用方。

```java
public void withdraw(double amount) {
    if (amount > balance) {
        throw new IllegalStateException("余额不足，当前余额: " + balance);
    }
    balance -= amount;
}

public List<String> readConfig() throws IOException {
    return Files.readAllLines(Paths.get("app.properties"));
}
```

- 异常沿调用栈**向上传播**：被某个 `catch` 捕获则处理，一路无人处理则到达 `main`，最终由 JVM 打印堆栈并终止线程
- `throws` 只能声明受检异常；`RuntimeException` 及其子类无需声明

### 3.3 checked exception 与 unchecked exception

| 维度 | checked（受检） | unchecked（非受检） |
|------|----------------|--------------------|
| 直接父类 | `Exception`（除 `RuntimeException` 分支） | `RuntimeException` 或 `Error` |
| 编译期强制 | 必须 catch 或 throws，否则编译失败 | 不强制，仅运行期出现 |
| 典型代表 | `IOException`、`SQLException`、`FileNotFoundException` | `NullPointerException`、`IllegalArgumentException`、`ArithmeticException` |
| 语义 | 可预期的外部失败（文件、网络、数据库） | 编程错误或状态错误（bug、非法入参） |
| 处理者 | 调用方被迫面对 | 由程序作者保证不发生 |

**判别原则**：失败是「外部环境可预期、调用方可以恢复」的 → 设计为 checked；失败是「程序员写错了」→ 设计为 unchecked。企业业务代码中，业务异常几乎总是继承 `RuntimeException`（unchecked），避免污染每一层接口签名。

### 3.4 自定义异常与异常链（cause）

自定义异常继承 `Exception`（受检）或 `RuntimeException`（非受检），标准写法是提供 message、cause、message+cause 三个构造器：

```java
public class OrderException extends RuntimeException {
    public OrderException(String message) { super(message); }
    public OrderException(String message, Throwable cause) { super(message, cause); }
}

// 使用：包装底层异常，保留根因
try {
    paymentGateway.charge(order);
} catch (PaymentException e) {
    throw new OrderException("订单支付失败", e);   // 异常链
}
```

- **异常链（exception chaining）**：包装异常时把原始异常作为 `cause` 传入，`getCause()` 可逐层取回根因，`printStackTrace()` 会以 `Caused by:` 打印完整链路
- 业务异常应携带**清晰语义**：错误码、可读消息、上下文（订单号、用户 ID 等），而不是只传一句英文底层报错

### 3.5 try-with-resources（Java 7+）

资源（实现了 `AutoCloseable` 的对象）在 try 头声明，无论正常返回还是抛异常，JVM 都会自动调用 `close()`，且**先关闭依赖资源（后声明的先关）**：

```java
try (FileReader reader = new FileReader("data.txt");
     BufferedReader br = new BufferedReader(reader)) {
    System.out.println(br.readLine());
} catch (IOException e) {
    e.printStackTrace();
}
```

- 相比 `finally` 手动关闭：不用判空、不用嵌套 try/catch、不会漏关——**资源释放优先用 try-with-resources**
- 关闭本身抛出的异常会被**抑制**（suppressed），可通过 `e.getSuppressed()` 查看
- Java 9+ 支持在 try 头直接使用已有的 effectively final 变量：`try (reader) { ... }`

### 3.6 multi-catch 与 final 变量

多个**互不相关**的异常需要同样处理时，用 `|` 合并为单个 catch：

```java
try {
    parseConfig();        // 可能抛 ParseException
    loadRemoteData();     // 可能抛 IOException
} catch (ParseException | IOException e) {
    // 变量 e 隐含 final：不能重新赋值，避免掩盖真实异常
    System.err.println("配置或远程数据加载失败: " + e.getMessage());
    e.printStackTrace();
}
```

- 合并的异常类型之间**不能有继承关系**——子类是父类的子类型时子类分支不可达，编译器直接报错
- catch 变量隐含 `final`，无法 `e = new XxxException(...)`，防止掩盖原始异常
- 需要按类型分别处理时仍拆成多个 catch，且**子类在前、父类在后**，否则子类分支永远匹配不到

### 3.7 Optional 与异常的取舍

`Optional`（Java 8）表达「结果可能为空」的**正常路径**；异常表达「不该发生或需要特殊处理」的**失败路径**。两者互补而非替代：

```java
Optional<User> user = userRepository.findById(userId);
User u = user.orElseThrow(() -> new UserNotFoundException("用户不存在: " + userId));
```

- 查找类方法返回 `Optional`，把「没查到」变成值的一部分，避免调用方收到 `null` 后 NPE
- `Optional.of(null)` 会抛 `NullPointerException`；可能为 null 时用 `Optional.ofNullable(x)`
- 不要用 `Optional` 作为字段、方法参数或集合元素（仅用于**返回值**），也不要用它包装异常信息——失败路径一律用异常（或 `Result<T>` 封装，见 ph05 示例 6）

## 4. 底层原理

### 4.1 JVM 异常表（exception table）与字节码层的 try/catch

javac 编译 `try/catch` 时并不生成跳转分支，而是为方法附加一张**异常表**（exception table），JVM 抛出异常时按表查找处理位置：

| 列 | 含义 |
|----|------|
| start_pc / end_pc | try 块覆盖的字节码范围 `[start, end)` |
| handler_pc | 异常处理器（catch 或 finally 代码）的字节码偏移 |
| catch_type | 捕获的异常类型；`any` 表示所有异常（finally 使用） |

```java
// javap -c 反编译后，方法上附带的异常表示意：
// Exception table:
//    from    to  target type
//       0     7     8   Class java/lang/ArithmeticException
//       0     7    18   any
```

方法执行中若在 `[start_pc, end_pc)` 内抛出匹配 `catch_type` 的异常，JVM 跳转到 `handler_pc` 执行处理器；找不到匹配则沿调用栈向上传播，逐帧重复该查找过程。**finally 的实现**：现代 javac 不再使用 jsr/ret 指令，而是把 finally 代码**内联复制**到 try 正常出口、每个 catch 出口以及异常路径，保证任何出口都会执行——代价是 finally 代码会被复制多份。

### 4.2 异常对象的创建开销与栈回溯（fillInStackTrace）

`new ArithmeticException()` 远比 `new Object()` 昂贵，主要开销在**栈回溯**：

1. 异常构造器调用 native 方法 `Throwable.fillInStackTrace()`
2. 遍历当前线程调用栈，为每一帧生成一个 `StackTraceElement`（类名、方法名、文件名、行号），存入 `StackTraceElement[] stackTrace` 字段，供 `printStackTrace()` 与日志框架输出

因此：

- 抛异常路径可能比正常路径慢**几个数量级**——**绝不要用异常控制正常流程**（如用 catch 终止循环、用异常做分支判断）
- 正常路径上的 try 块本身几乎没有成本（异常表查找只在抛出时发生），可以放心用 try 包裹
- `Throwable` 四参构造 `new Exception(message, cause, enableSuppression, writableStackTrace)`，传 `false, false` 可跳过栈回溯；仅用于确认不需要堆栈的性能敏感场景，业务代码不推荐

### 4.3 checked 异常在编译期的强制

编译器对 checked exception 做**静态分析**：方法体内可能抛出的受检异常，要么在方法内被 `catch`，要么在 `throws` 中声明，否则编译失败。强制规则：

| 规则 | 说明 |
|------|------|
| 捕获或声明 | 受检异常必须 catch 或 throws，二选一 |
| 子类同受检 | 受检异常的子类仍是受检异常，同样必须处理 |
| throws 可宽 | 方法可声明异常本身或其父类（更宽） |
| 重写限制 | 重写方法不能声明比父类更宽的受检异常（可更窄或省略） |

这条规则把「外部失败是可能发生的」写进了类型签名：调用 `Files.readAllLines(...)` 时，编译器强迫你面对 `IOException`。代价是 checked 异常沿多层调用栈传播时会污染每一层签名——因此企业实践常用「**边界转换**」模式：底层受检异常在 DAO/Service 边界被捕获并包装为 unchecked 的业务异常（见示例 5）。

### 4.4 异常链的实现（initCause 与构造器链）

`Throwable` 内部维护一个 `cause` 字段（类型为 `Throwable`），包装异常时通过构造器链完成赋值：

```java
public class OrderException extends Exception {
    public OrderException(String message, Throwable cause) {
        super(message, cause);   // Throwable 构造器内部调用 initCause(cause)
    }
}
```

- 两参/三参构造器内部调用 `initCause(cause)`；`getCause()` 取回根因
- `printStackTrace()` 输出时自动追加 `Caused by: ...`，逐层打印整条异常链
- 若构造器未传 cause，可事后调用 `initCause` 补充，但**只能调用一次**，重复调用抛 `IllegalStateException`

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 数值运算防御（除零、溢出） | `ArithmeticException` 捕获与兜底值 |
| 方法入参校验 | `IllegalArgumentException`（unchecked） |
| 文件/网络/数据库操作 | checked `IOException` 等 + try-with-resources |
| 业务规则失败（余额不足、重复下单） | 自定义业务异常 + 错误码 |
| 底层失败向上传递 | 异常链：包装异常并保留 `cause` |
| 多个无关异常统一处理 | multi-catch |
| 查找类方法返回可空结果 | `Optional` 与异常互补 |

**不适合**此阶段的事项：

- 用异常控制正常流程——`try/catch` 做循环终止、分支判断（性能差且语义错误）
- 在 catch 中「吞掉」异常——只打注释或空 catch，无日志、无包装、无重抛
- 微服务全局异常拦截、`@RestControllerAdvice` 统一响应体（ph15 Spring 阶段）
- 用 checked 异常跨层污染接口签名——应使用边界转换模式包装为业务异常

## 6. 代码示例

> 本节每个示例的完整可运行文件在 [`examples/`](./examples/) 目录，验证环境 OpenJDK 17.0.16，编译命令统一 `javac <文件名>.java`（命令见 examples/README.md）。示例文件用**非 public 类**——Java 规定 public 类必须与文件名同名，kebab-case 文件名无法匹配大驼峰类名，非 public 类无此限制；因此编译用文件名、运行用类名（如 `javac ex01-safe-division.java` + `java SafeDivision`）。

### 示例 1：安全除法（try/catch ArithmeticException）

对应 roadmap 练习「安全除法」：除零不再崩溃，而是返回兜底值。

```java
public class SafeDivision {
    // 防御性除法：除零时返回 0 并记录原因
    public static int safeDivide(int a, int b) {
        try {
            return a / b;
        } catch (ArithmeticException e) {
            System.out.println("除数为 0，返回兜底值: " + e.getMessage());
            return 0;
        }
    }

    public static void main(String[] args) {
        System.out.println("10 / 2 = " + safeDivide(10, 2));
        System.out.println("10 / 0 = " + safeDivide(10, 0));
        System.out.println("10 / 3 = " + safeDivide(10, 3));
    }
}
```

完整文件：`examples/ex01-safe-division.java`

### 示例 2：文件读取异常处理（finally 关闭 → try-with-resources）

对应 roadmap 练习「文件读取异常」：先展示 finally 手动关闭的繁琐与易错，再展示 try-with-resources 的等价写法。

```java
import java.io.*;

public class FileReadDemo {
    // 方式一：try/catch/finally 手动关闭资源
    public static String readWithFinally(String path) {
        FileReader reader = null;
        try {
            reader = new FileReader(path);
            StringBuilder sb = new StringBuilder();
            int ch;
            while ((ch = reader.read()) != -1) {
                sb.append((char) ch);
            }
            return sb.toString();
        } catch (FileNotFoundException e) {
            System.out.println("文件不存在: " + path);
            return null;
        } catch (IOException e) {
            System.out.println("读取失败: " + e.getMessage());
            return null;
        } finally {
            if (reader != null) {
                try {
                    reader.close();
                } catch (IOException e) {
                    System.out.println("关闭资源失败: " + e.getMessage());
                }
            }
        }
    }

    // 方式二：try-with-resources 自动关闭（推荐）
    public static String readWithTryWithResources(String path) {
        try (FileReader reader = new FileReader(path)) {
            StringBuilder sb = new StringBuilder();
            int ch;
            while ((ch = reader.read()) != -1) {
                sb.append((char) ch);
            }
            return sb.toString();
        } catch (IOException e) {
            System.out.println("读取失败: " + e.getMessage());
            return null;
        }
    }

    public static void main(String[] args) throws IOException {
        try (FileWriter writer = new FileWriter("demo.txt")) {
            writer.write("Hello Exception Stage");
        }
        System.out.println("finally 版: " + readWithFinally("demo.txt"));
        System.out.println("twr 版:     " + readWithTryWithResources("demo.txt"));
        System.out.println("不存在:     " + readWithTryWithResources("no-such-file.txt"));
        new File("demo.txt").delete();
    }
}
```

完整文件：`examples/ex02-file-read-demo.java`（运行生成 demo.txt，验证后清理）

### 示例 3：自定义业务异常体系（基类 + 错误码 + 异常链）

对应 roadmap 必会概念「业务异常要有清晰语义」与推荐项目「业务错误码体系」。

```java
public class BusinessExceptionDemo {
    // 错误码枚举：集中管理业务错误语义
    enum ErrorCode {
        INVALID_PARAM(1001, "参数不合法"),
        USER_NOT_FOUND(1002, "用户不存在"),
        LOGIN_FAILED(1003, "登录失败"),
        INSUFFICIENT_BALANCE(2001, "余额不足");

        final int code;
        final String message;

        ErrorCode(int code, String message) {
            this.code = code;
            this.message = message;
        }
    }

    // 业务异常基类：unchecked + 错误码 + 异常链
    static class BusinessException extends RuntimeException {
        private final ErrorCode errorCode;

        BusinessException(ErrorCode errorCode) {
            super(errorCode.message);
            this.errorCode = errorCode;
        }

        BusinessException(ErrorCode errorCode, Throwable cause) {
            super(errorCode.message, cause);   // 保留根因
            this.errorCode = errorCode;
        }

        public ErrorCode getErrorCode() { return errorCode; }
    }

    // 账户服务：余额不足时抛业务异常，并附上根因
    static class AccountService {
        private final double balance;

        AccountService(double balance) { this.balance = balance; }

        void transfer(double amount) {
            if (amount <= 0) {
                throw new BusinessException(ErrorCode.INVALID_PARAM);
            }
            if (balance < amount) {
                throw new BusinessException(ErrorCode.INSUFFICIENT_BALANCE,
                        new IllegalArgumentException(
                                "余额 " + balance + " 小于转账金额 " + amount));
            }
            System.out.println("转账成功: " + amount);
        }
    }

    public static void main(String[] args) {
        AccountService service = new AccountService(100.0);
        try {
            service.transfer(500.0);
        } catch (BusinessException e) {
            System.out.println("错误码: " + e.getErrorCode().code
                    + ", 信息: " + e.getMessage());
            e.printStackTrace();   // 生产环境应交给日志框架
        }
    }
}
```

完整文件：`examples/ex03-business-exception-demo.java`

### 示例 4：登录与参数校验异常（IllegalArgumentException vs 业务异常）

对应 roadmap 练习「登录异常」「参数校验异常」：区分「调用方写错」（unchecked 参数异常）与「用户输入不满足业务规则」（业务异常）。

```java
public class LoginDemo {
    // 参数校验：调用方错误 -> IllegalArgumentException
    static void requireNonEmpty(String value, String field) {
        if (value == null || value.trim().isEmpty()) {
            throw new IllegalArgumentException(field + " 不能为空");
        }
    }

    // 业务异常：业务规则失败
    static class LoginException extends RuntimeException {
        LoginException(String message) { super(message); }
    }

    static String login(String username, String password) {
        requireNonEmpty(username, "用户名");
        requireNonEmpty(password, "密码");
        if (!"admin".equals(username) || !"123456".equals(password)) {
            throw new LoginException("用户名或密码错误");
        }
        return "登录成功，欢迎 " + username;
    }

    public static void main(String[] args) {
        try {
            System.out.println(login("admin", "123456"));
        } catch (LoginException e) {
            System.out.println("业务失败: " + e.getMessage());
        }

        try {
            System.out.println(login("admin", "wrong"));
        } catch (LoginException e) {
            System.out.println("业务失败: " + e.getMessage());
        }

        // 参数为空 -> IllegalArgumentException，由调用方修正
        try {
            System.out.println(login("", "123456"));
        } catch (IllegalArgumentException e) {
            System.out.println("参数错误: " + e.getMessage());
        }
    }
}
```

完整文件：`examples/ex04-login-demo.java`

### 示例 5：异常链保留根因（cause 传递，日志打印完整堆栈）

对应 roadmap 必会概念「异常信息要保留上下文」：底层受检异常在 DAO 边界转 unchecked，逐层包装，顶层看到完整 `Caused by:` 链路。

```java
public class ExceptionChainDemo {
    static class DaoException extends RuntimeException {
        DaoException(String message, Throwable cause) { super(message, cause); }
    }

    static class ServiceException extends RuntimeException {
        ServiceException(String message, Throwable cause) { super(message, cause); }
    }

    // 最底层：数据库驱动抛出的受检异常
    static void dbQuery() throws Exception {
        throw new Exception("数据库连接超时");
    }

    // DAO 层：边界转换——受检异常包装为 unchecked DaoException，保留 cause
    static void findUser() {
        try {
            dbQuery();
        } catch (Exception e) {
            throw new DaoException("查询用户失败", e);
        }
    }

    // Service 层：继续包装，根因逐层传递
    static void getUserInfo() {
        try {
            findUser();
        } catch (DaoException e) {
            throw new ServiceException("获取用户信息失败", e);
        }
    }

    public static void main(String[] args) {
        try {
            getUserInfo();
        } catch (ServiceException e) {
            System.out.println("顶层捕获: " + e.getMessage());
            System.out.println("---- 完整堆栈（含根因）----");
            e.printStackTrace();   // 打印 ServiceException -> DaoException -> Exception
            System.out.println("根因信息: "
                    + e.getCause().getCause().getMessage());
        }
    }
}
```

完整文件：`examples/ex05-exception-chain-demo.java`

## 7. 总结

### 关键要点

1. **异常只用于异常路径**——try/catch 控制正常流程既语义错误又性能差：异常创建会调用 `fillInStackTrace()` 遍历调用栈，热路径频繁抛异常会拖慢系统
2. **绝不吞异常**——catch 后必须至少做三件事之一：记录日志、包装重抛、恢复后继续
3. **catch 顺序从具体到抽象**——子类在前、父类在后，否则子类分支不可达（编译错误）
4. **资源释放优先 try-with-resources**——finally 手动关闭易漏、需判空、关闭还可能抛异常
5. **业务异常要有清晰语义**——错误码 + 可读消息 + 上下文（订单号、用户 ID）
6. **checked 与 unchecked 分工**——外部可预期失败用 checked；编程错误（非法入参等）用 unchecked
7. **Optional 与异常互补**——可空返回值用 `Optional`，失败路径用异常，各司其职

### 跨语言对比：错误处理

| 维度 | Java | C++ | Go | Python | Rust |
|------|------|-----|----|--------|------|
| 错误表示 | 异常对象（checked/unchecked） | 异常对象（任意类型可抛） | `error` 接口值（显式返回） | 异常对象（一切皆可抛） | `Result<T, E>` 枚举 |
| 是否强制处理 | checked 编译期强制，unchecked 不强制 | 不强制 | 强制检查（`err != nil`） | 不强制 | 必须显式处理（`must_use`） |
| 资源清理 | try-with-resources / finally | RAII（析构函数自动释放） | `defer` | `with` / try-finally | Drop trait（作用域结束自动释放） |
| 传播方式 | 沿调用栈自动传播 | 沿调用栈自动传播 | 手动逐层返回 | 沿调用栈自动传播 | 手动 `?` 运算符传播 |
| 性能特征 | 抛异常成本高 | 零开销（未抛时），抛出成本高 | 无异常机制，纯值传递 | 抛异常成本高 | 零运行时开销（编译期展开） |

对比结论：Java 的 checked exception 是「编译期强制 + 运行期传播」的独特折中；Go 与 Rust 把错误当**值**显式传递，强制程度最高但代码更啰嗦；C++/Python 依赖运行时机制与程序员自律。企业级 Java 实践最终收敛为「边界转换 + 业务异常 + 全局处理」的模式。

### 阶段验收清单

- [ ] 能设计业务异常体系：异常基类 + 错误码 + message/cause 构造器链
- [ ] 能正确释放资源：优先 try-with-resources，理解 finally 的手动关闭缺陷
- [ ] 能区分 checked/unchecked exception，并解释编译期强制机制与重写限制
- [ ] 能用异常链保留根因（cause），日志打印完整堆栈
- [ ] 能用 `Optional` 处理可空返回值，避免 `NullPointerException`

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：安全除法、文件读取异常、登录异常、参数校验异常共 4 题。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**统一异常处理 demo**（Controller/Service/DAO 三层各自抛出不同异常，顶层统一分类处理，把业务异常转换为错误码 + 统一响应结构）。Roadmap 推荐的另一个项目「业务错误码体系」不再单独立项——错误码枚举 + 业务异常基类正是本项目的前置组件，已一并落地。建议完成练习后再动手。

- [ ] 完成 exercises 全部练习并复盘
- [ ] 独立完成 project（通过 README 验收标准）

### 下一阶段

[IO 与文件操作阶段](../ph07-io-file/07-io-file.md) —— InputStream/OutputStream、Reader/Writer、NIO 基础、序列化。
