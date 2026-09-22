# ph06 异常处理 示例

> 每个示例是主文档「6. 代码示例」对应示例的完整可运行版。验证环境：OpenJDK 17.0.16。

## 类名与文件名说明

为保持 `ex0X-` 编号命名，文件名（`ex01-safe-division.java`）与类名（`SafeDivision`）不一致。因此这些示例**刻意不声明为 `public` 类**（Java 规定 public 类必须与文件名同名，非 public 类无此限制）。编译时用**文件名**，运行时用**类名**：

```bash
# 1. 编译
javac ex01-safe-division.java
# 2. 运行（注意是类名不是文件名）
java SafeDivision
```

## 示例列表

| 文件 | 类名 | 说明 | 编译 | 运行 |
|------|------|------|------|------|
| ex01-safe-division.java | SafeDivision | 安全除法：try/catch ArithmeticException，除零返回兜底值 | `javac ex01-safe-division.java` | `java SafeDivision` |
| ex02-file-read-demo.java | FileReadDemo | 文件读取异常：finally 手动关闭 vs try-with-resources 对比 | `javac ex02-file-read-demo.java` | `java FileReadDemo` |
| ex03-business-exception-demo.java | BusinessExceptionDemo | 自定义业务异常体系：错误码枚举 + 异常基类 + 异常链 | `javac ex03-business-exception-demo.java` | `java BusinessExceptionDemo` |
| ex04-login-demo.java | LoginDemo | 登录与参数校验：IllegalArgumentException vs 业务异常 | `javac ex04-login-demo.java` | `java LoginDemo` |
| ex05-exception-chain-demo.java | ExceptionChainDemo | 异常链保留根因：DAO 边界转换，`Caused by` 完整链路 | `javac ex05-exception-chain-demo.java` | `java ExceptionChainDemo` |

全部已在本环境用 OpenJDK 17.0.16 编译运行验证（零错误，输出符合注释中的期望值）。两点说明：

- `ex02-file-read-demo.java` 运行时会在当前目录生成 `demo.txt` 并自动删除，无需手动清理。
- 所有示例的类都不是 `public`——这是 kebab-case 文件名与 Java「public 类必须与文件名同名」约束协调的结果（详见上文说明），`java` 运行不要求主类为 public。
