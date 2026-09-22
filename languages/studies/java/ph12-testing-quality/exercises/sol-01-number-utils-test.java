// exercises/sol-01-number-utils-test.java —— 练习 1 参考实现：工具类测试（JUnit 5）
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + JUnit Jupiter 5.10.1（本机离线模式 mvn -o）
// 验证状态：已验证（pom 与本文件内容放入临时工程后 mvn -o clean test, BUILD SUCCESS）
// ---------------------------------------------------------------------------
// 本练习的 pom.xml（写入工程根目录 pom.xml）:
//
//   <project xmlns="http://maven.apache.org/POM/4.0.0">
//     <modelVersion>4.0.0</modelVersion>
//     <groupId>com.example</groupId>
//     <artifactId>sol01-number-utils</artifactId>
//     <version>1.0-SNAPSHOT</version>
//     <properties>
//       <maven.compiler.release>17</maven.compiler.release>
//       <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
//     </properties>
//     <dependencies>
//       <dependency>
//         <groupId>org.junit.jupiter</groupId>
//         <artifactId>junit-jupiter</artifactId>
//         <version>5.10.1</version>
//         <scope>test</scope>
//       </dependency>
//     </dependencies>
//     <build>
//       <plugins>
//         <plugin>
//           <groupId>org.apache.maven.plugins</groupId>
//           <artifactId>maven-surefire-plugin</artifactId>
//           <version>3.2.5</version>
//         </plugin>
//       </plugins>
//     </build>
//   </project>
//
// 测试类（src/test/java/com/example/NumberUtilsTest.java）:
//
//   package com.example;
//   import org.junit.jupiter.api.Test;
//   import static org.junit.jupiter.api.Assertions.assertFalse;
//   import static org.junit.jupiter.api.Assertions.assertThrows;
//   import static org.junit.jupiter.api.Assertions.assertTrue;
//
//   class NumberUtilsTest {
//       @Test void leapYearDivisibleBy4() { assertTrue(NumberUtils.isLeapYear(2024)); }
//       @Test void commonYearNotDivisibleBy4() { assertFalse(NumberUtils.isLeapYear(2023)); }
//       @Test void centuryYearNotLeapUnlessDivisibleBy400() { assertFalse(NumberUtils.isLeapYear(1900)); }
//       @Test void yearDivisibleBy400IsLeap() { assertTrue(NumberUtils.isLeapYear(2000)); }
//       @Test void boundaryYear1IsNotLeap() { assertFalse(NumberUtils.isLeapYear(1)); }
//       @Test void nonPositiveYearThrows() {
//           assertThrows(IllegalArgumentException.class, () -> NumberUtils.isLeapYear(-4));
//       }
//   }
//
// 目录结构：本文件内容放 src/main/java/com/example/NumberUtils.java
// 编译/运行命令（工程根目录）:
//   1. mvn clean test
//       # 实测: Tests run: 6, Failures: 0, Errors: 0, Skipped: 0
// 要点：
//   - 一个测试方法只验证一个行为；命名用「被测方法_场景_预期」读起来像句子
//   - 边界值（year=1）、错误路径（负数）与正常路径同样重要 —— 覆盖率不是唯一指标，测试设计才是源头
//   - 纯函数（无状态、无 I/O）是单元测试最舒服的对象；带依赖的类见练习 2/3
// ---------------------------------------------------------------------------
package com.example;

/** 工具类：闰年判定。纯函数，最适合单元测试。 */
public final class NumberUtils {
    private NumberUtils() {
    }

    /** 公历闰年：能被 4 整除且不能被 100 整除，或能被 400 整除；year <= 0 抛异常。 */
    public static boolean isLeapYear(int year) {
        if (year <= 0) {
            throw new IllegalArgumentException("年份必须为正: " + year);
        }
        return (year % 4 == 0 && year % 100 != 0) || year % 400 == 0;
    }
}
