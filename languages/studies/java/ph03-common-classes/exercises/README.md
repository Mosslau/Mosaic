# ph03 常用类 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：OpenJDK 17.0.16。参考实现均用非 public 类（文件名 `sol-0X-*.java` 与类名不同），编译用文件名、运行用类名，如 `javac sol-01-StringReverse.java` + `java StringReverse`。

## 练习 1：字符串反转（★）

**目标**：掌握 StringBuilder 的 `reverse()` 方法。
**要求**：实现方法 `static String reverse(String s)`；禁止用循环逐字符反转，必须用 `StringBuilder.reverse()`。
**验收**：`reverse("hello")` 返回 `"olleh"`；`reverse("上海自来水")` 返回 `"水来自海上"`；`reverse("")` 返回 `""`。

## 练习 2：字符频次统计（★★）

**目标**：掌握用 `int[]` 数组做计数器统计字符出现次数。
**要求**：实现方法 `static int[] count(String text)`，返回长度 128 的计数数组（只统计 ASCII 范围内的字符，忽略其余）；再写 main 遍历输出「出现过的字符 + 次数」。
**验收**：对 `"hello world"`，`l` 计 3 次、`o` 计 2 次、空格计 1 次；对 `"aaa"`，`a` 计 3 次。

## 练习 3：金额计算（★★）

**目标**：掌握 BigDecimal 的精确运算，识别 double 浮点陷阱。
**要求**：实现方法 `static String withTax(String price, String quantity, String taxRate)`，计算 `price × quantity × (1 + taxRate)`，结果保留两位小数、四舍五入（`RoundingMode.HALF_UP`），以字符串返回；禁止用 `double` 参与金额计算、禁止用浮点构造 `BigDecimal`。
**验收**：`withTax("19.99", "3", "0.13")` 返回 `"67.77"`；`withTax("0.1", "3", "0.0")` 返回 `"0.30"`（不能用 `0.30000000000000004`）。

## 练习 4：日期格式化（★★）

**目标**：掌握 `DateTimeFormatter` 的格式化与解析。
**要求**：实现两个方法——`static String format(LocalDateTime dt)`（pattern 固定 `"yyyy-MM-dd HH:mm"`）和 `static LocalDateTime parse(String s)`（用同一 pattern 解析）。
**验收**：`format(LocalDateTime.of(2026, 8, 8, 14, 30))` 返回 `"2026-08-08 14:30"`；`parse("2026-08-08 14:30")` 等于 `LocalDateTime.of(2026, 8, 8, 14, 30)`。

## 练习 5：日期计算工具（★★★）

**目标**：综合运用 `LocalDate` 做日期区间计算与星期判断。
**要求**：实现两个方法——`static long daysBetween(LocalDate from, LocalDate to)`（`to` 与 `from` 的天数差，用 `ChronoUnit.DAYS`）和 `static boolean isWorkday(LocalDate date)`（工作日 = 周一至周五，不含法定节假日）。
**验收**：`daysBetween(LocalDate.of(2026, 8, 1), LocalDate.of(2026, 8, 30))` 返回 `29`；`isWorkday(LocalDate.of(2026, 8, 30))`（周日）返回 `false`；`isWorkday(LocalDate.of(2026, 8, 28))`（周五）返回 `true`。
