# ph05 泛型 示例

> 每个示例是主文档「6. 代码示例」对应示例的完整可运行版。验证环境：OpenJDK 17.0.16。

## 类名与文件名说明

为保持 `ex0X-` 编号命名，文件名（`ex01-generic-box.java`）与类名（`GenericBox`）不一致。因此这些示例**刻意不声明为 `public` 类**（Java 规定 public 类必须与文件名同名，非 public 类无此限制）。编译时用**文件名**，运行时用**类名**：

```bash
# 1. 编译
javac ex01-generic-box.java
# 2. 运行（注意是类名不是文件名）
java GenericBox
```

## 示例列表

| 文件 | 类名 | 说明 | 编译 | 运行 |
|------|------|------|------|------|
| ex01-generic-box.java | GenericBox | 泛型 Box：单类型参数 set/get/isEmpty + 运行时 Class 相同验证 | `javac ex01-generic-box.java` | `java GenericBox` |
| ex02-generic-pair.java | GenericPair | 泛型 Pair：双类型参数 K/V + 泛型方法 swapValues | `javac ex02-generic-pair.java` | `java GenericPair` |
| ex03-generic-stack.java | GenericStack | 泛型 Stack：Object[] 规避泛型数组 + pop 强转 + 防泄漏置空 | `javac ex03-generic-stack.java` | `java GenericStack` |
| ex04-generic-repository.java | GenericRepository | 泛型 Repository：泛型接口契约 + UserRepository 绑定具体类型 | `javac ex04-generic-repository.java` | `java GenericRepository` |
| ex05-pecs-demo.java | PecsDemo | PECS 演示：`? extends` 只读 / `? super` 只写 / copyAll 组合 | `javac ex05-pecs-demo.java` | `java PecsDemo` |
| ex06-result-demo.java | ResultDemo | 泛型 Result 封装：success/failure + map 变换 | `javac ex06-result-demo.java` | `java ResultDemo` |

全部已在本环境用 OpenJDK 17.0.16 编译运行验证（零错误，输出符合注释中的期望值）。两点说明：

- `ex04-generic-repository.java` 的「全部用户」按 `HashMap` 内部顺序打印，运行结果顺序可能与注释展示不同，属正常现象；只有「查找 u2」与「删除后」的成员可断言。
- 所有示例的类都不是 `public`——这是 kebab-case 文件名与 Java「public 类必须与文件名同名」约束协调的结果（详见上文说明），`java` 运行不要求主类为 public。
