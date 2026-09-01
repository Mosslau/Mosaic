// exercises/sol-04-parameterized-coverage.java —— 练习 4 参考实现：参数化测试 + JaCoCo 覆盖率
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + JUnit Jupiter 5.10.1 + jacoco-maven-plugin 0.8.11（本机离线模式 mvn -o）
// 验证状态：已验证（pom 与本文件内容放入临时工程后 mvn -o clean test, BUILD SUCCESS）
// 实测结果：Tests run: 9, Failures: 0, Errors: 0, Skipped: 0
// 实测覆盖率（target/site/jacoco/jacoco.csv 中 NumberUtils 一行，故意不测 daysInFebruary）:
//   - 指令覆盖率 24/31（77.4%）—— isLeapYear 全测，daysInFebruary 未测
//   - 行覆盖率 3/4、方法覆盖率 1/2、分支覆盖率 8/10
//   - 补一个 daysInFebruary 的测试后覆盖率变化可自行验证（把缺口补上就是 100% 的过程）
// ---------------------------------------------------------------------------
// 本练习的 pom.xml（写入工程根目录 pom.xml）:
//
//   <project xmlns="http://maven.apache.org/POM/4.0.0">
//     <modelVersion>4.0.0</modelVersion>
//     <groupId>com.example</groupId>
//     <artifactId>sol04-param-coverage</artifactId>
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
//         <plugin>
//           <groupId>org.jacoco</groupId>
//           <artifactId>jacoco-maven-plugin</artifactId>
//           <version>0.8.11</version>
//           <executions>
//             <execution><goals><goal>prepare-agent</goal></goals></execution>
//             <execution><id>report</id><phase>test</phase><goals><goal>report</goal></goals></execution>
//           </executions>
//         </plugin>
//       </plugins>
//     </build>
//   </project>
//
// 测试类（src/test/java/com/example/NumberUtilsParamTest.java）:
//
//   package com.example;
//   import org.junit.jupiter.params.ParameterizedTest;
//   import org.junit.jupiter.params.provider.Arguments;
//   import org.junit.jupiter.params.provider.CsvSource;
//   import org.junit.jupiter.params.provider.MethodSource;
//   import java.util.stream.Stream;
//   import static org.junit.jupiter.api.Assertions.assertEquals;
//   import static org.junit.jupiter.api.Assertions.assertThrows;
//
//   class NumberUtilsParamTest {
//       // 一行一组「输入,预期」—— 一张表代替 6 个几乎相同的测试方法
//       @ParameterizedTest
//       @CsvSource({
//               "2024,true",
//               "2023,false",
//               "1900,false",
//               "2000,true",
//               "1,false",
//               "400,true"
//       })
//       void isLeapYear_cases(int year, boolean expected) {
//           assertEquals(expected, NumberUtils.isLeapYear(year), "isLeapYear(" + year + ")");
//       }
//
//       // MethodSource 工厂方法返回的 Arguments 流表达「输入 + 预期异常」更清晰
//       @ParameterizedTest
//       @MethodSource("invalidYears")
//       void isLeapYear_rejectsNonPositiveYear(int year) {
//           assertThrows(IllegalArgumentException.class, () -> NumberUtils.isLeapYear(year));
//       }
//
//       static Stream<Arguments> invalidYears() {
//           return Stream.of(
//                   Arguments.of(0),
//                   Arguments.of(-4),
//                   Arguments.of(-100));
//       }
//   }
//
// 目录结构：本文件内容放 src/main/java/com/example/NumberUtils.java
// 编译/运行命令（工程根目录）:
//   1. mvn clean test
//       # 实测: Tests run: 9（参数化把 6 行 CsvSource + 3 个非法年份各算一次执行）, Failures: 0
//   2. open target/site/jacoco/index.html   # 浏览器打开覆盖率报告；或看 target/site/jacoco/jacoco.csv
// 要点：
//   - 参数化测试把「一组输入一组预期」收敛成一张表，加用例只加一行，不再复制测试方法
//   - surefire 把每次参数执行计为一个测试（所以 Tests run: 9 而不是 2 个方法）
//   - 覆盖率 = 测到的 ÷ 全部：报告里 daysInFebruary 是红色（未覆盖），补上它的测试后数字变化
//   - 覆盖率是结果不是目标：先把测试设计好（正常/边界/错误路径），再看报告找遗漏分支
// ---------------------------------------------------------------------------
package com.example;

/** 工具类：闰年判定与二月天数。daysInFebruary 故意不测（练习要求），看覆盖率缺口。 */
public final class NumberUtils {
    private NumberUtils() {
    }

    public static boolean isLeapYear(int year) {
        if (year <= 0) {
            throw new IllegalArgumentException("年份必须为正: " + year);
        }
        return (year % 4 == 0 && year % 100 != 0) || year % 400 == 0;
    }

    public static int daysInFebruary(int year) {
        return isLeapYear(year) ? 29 : 28;
    }
}
