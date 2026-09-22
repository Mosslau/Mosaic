# ph01 基础语法 示例

> 每个示例是主文档「6. 代码示例」对应示例的完整可运行版。验证环境：OpenJDK 17.0.16（建议 JDK 17+）。

| 文件 | 类名 | 说明 | 编译 | 运行 |
|------|------|------|------|------|
| ex01-calculator.java | `Calculator` | 命令行计算器：读算式求值，处理除零 | `javac ex01-calculator.java` | `java Calculator` |
| ex02-prime-check.java | `PrimeCheck` | 判断素数：打印 1~100 内全部素数 | `javac ex02-prime-check.java` | `java PrimeCheck` |
| ex03-array-stats.java | `ArrayStats` | 数组统计：最大值、最小值、平均值 | `javac ex03-array-stats.java` | `java ArrayStats` |
| ex04-multiplication-table.java | `MultiplicationTable` | 九九乘法表 | `javac ex04-multiplication-table.java` | `java MultiplicationTable` |
| ex05-guess-number.java | `GuessNumber` | 猜数字游戏（交互式） | `javac ex05-guess-number.java` | `java GuessNumber` |

**为什么类名和文件名不一样**：Java 只强制 `public class` 名与文件名一致；这些示例的类都不带 `public`，编译照常通过，运行时指定**类名**（不是文件名）即可。这是为保持示例命名统一（`exNN-主题`），日常开发仍建议一类一文件、文件名与类名一致。

ex01 用到 switch 表达式（Java 14+），需 JDK 14 以上编译；其余示例在 JDK 8 上也可编译运行。全部已在本环境（OpenJDK 17.0.16）编译运行验证。
