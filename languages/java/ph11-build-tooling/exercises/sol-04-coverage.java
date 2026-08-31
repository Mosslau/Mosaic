// exercises/sol-04-coverage.java —— 练习 4 参考实现：JaCoCo 覆盖率接入
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12（本机离线模式 mvn -o）
// 验证状态：已验证（下述 pom 与源码放入临时工程后 mvn -o clean test, BUILD SUCCESS）
// ---------------------------------------------------------------------------
// 本练习的 pom.xml（建工程时写入根目录 pom.xml; 本练习不需要 sol-01 的可执行 jar 配置）:
//
//   <project xmlns="http://maven.apache.org/POM/4.0.0">
//     <modelVersion>4.0.0</modelVersion>
//     <groupId>com.example</groupId>
//     <artifactId>coverage-demo</artifactId>
//     <version>1.0-SNAPSHOT</version>
//     <properties>
//       <maven.compiler.release>17</maven.compiler.release>
//       <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
//     </properties>
//     <dependencies>
//       <dependency>
//         <groupId>junit</groupId>
//         <artifactId>junit</artifactId>
//         <version>4.13.2</version>
//         <scope>test</scope>
//       </dependency>
//     </dependencies>
//     <build>
//       <plugins>
//         <plugin>
//           <groupId>org.jacoco</groupId>
//           <artifactId>jacoco-maven-plugin</artifactId>
//           <version>0.8.11</version>
//           <executions>
//             <execution>
//               <goals><goal>prepare-agent</goal></goals>
//             </execution>
//             <execution>
//               <id>report</id>
//               <phase>test</phase>
//               <goals><goal>report</goal></goals>
//             </execution>
//           </executions>
//         </plugin>
//       </plugins>
//     </build>
//   </project>
//
// 测试类（src/test/java/com/example/CalculatorTest.java）:
//
//   package com.example;
//   import static org.junit.Assert.assertEquals;
//   import org.junit.Test;
//   public class CalculatorTest {
//       @Test
//       public void testAdd() {
//           assertEquals(3, new Calculator().add(1, 2));
//       }
//   }
//
// 目录结构：本文件内容放 src/main/java/com/example/Calculator.java（测试类见上）
// 编译/运行命令（工程根目录）:
//   1. mvn clean test
//       # 实测: Tests run: 1, Failures: 0, Errors: 0, Skipped: 0
//       #       jacoco:report 生成 target/site/jacoco/index.html
//   2. open target/site/jacoco/index.html   # 浏览器打开覆盖率报告
// 实测数字（target/site/jacoco/jacoco.csv 中 Calculator 一行, 只测 add 不测 divide）:
//   - 指令覆盖率 7/11（63.6%）——add 的指令被覆盖, divide 没有
//   - 行覆盖率 2/3、方法覆盖率 2/3
//   - 把 divide 补一个测试后三类数字变 100%（可自行验证）
// 要点：JaCoCo 的 prepare-agent 给 surefire 注入 javaagent（mvn 输出里可见 argLine set to -javaagent:...）,
//       测试执行时记录字节码覆盖数据到 target/jacoco.exec, report 再渲染成 HTML/CSV;
//       覆盖率只是结果, 测试设计才是源头——JUnit 的深入编写在 ph12 单元测试与工程质量阶段
// ---------------------------------------------------------------------------
package com.example;

/** 被测类：只测 add 不测 divide, 覆盖率应 < 100% */
public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }

    public int divide(int a, int b) {
        return a / b;
    }
}
