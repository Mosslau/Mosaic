# ph03 常用类 示例

> 每个示例是主文档第 6 章对应示例的完整可运行版。验证环境：OpenJDK 17.0.16。

## 类名与文件名说明

为保持 `ex0X-` 编号命名，文件名（`ex01-StringReverse.java`）与类名（`StringReverse`）不一致。因此这些示例**刻意不声明为 `public` 类**（Java 规定 public 类必须与文件名同名，非 public 类无此限制）。编译时用**文件名**，运行时用**类名**：

```bash
javac ex01-StringReverse.java   # 编译，生成 StringReverse.class
java StringReverse              # 运行，注意是类名不是文件名
```

| 文件 | 类名 | 说明 | 编译 | 运行 |
|------|------|------|------|------|
| ex01-StringReverse.java | StringReverse | 字符串反转（StringBuilder.reverse） | `javac ex01-StringReverse.java` | `java StringReverse` |
| ex02-CharFrequency.java | CharFrequency | 字符频次统计（int[] 计数器） | `javac ex02-CharFrequency.java` | `java CharFrequency` |
| ex03-MoneyCalc.java | MoneyCalc | 金额计算（浮点陷阱 + BigDecimal） | `javac ex03-MoneyCalc.java` | `java MoneyCalc` |
| ex04-DateDemo.java | DateDemo | 日期格式化、计算与解析（java.time） | `javac ex04-DateDemo.java` | `java DateDemo` |
| ex05-CaptchaDemo.java | CaptchaDemo | 验证码生成器 + Integer 缓存演示 | `javac ex05-CaptchaDemo.java` | `java CaptchaDemo` |

全部已在本环境用 OpenJDK 17.0.16 编译运行验证（零错误，输出符合注释中的期望值）。ex04 的「今天 / 当前时间 / 预计送达」随运行日期变化，属正常现象。
