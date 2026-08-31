// exercises/sol-01-create-maven-project.java —— 练习 1 参考实现：最小 Maven 工程
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12（本机 mvn -version → 3.9.12, 离线模式 mvn -o）
// 验证状态：已验证（下述 pom 与源码放入临时工程后 mvn -o clean package, BUILD SUCCESS）
// ---------------------------------------------------------------------------
// 本练习的 pom.xml（建工程时写入根目录 pom.xml）:
//
//   <project xmlns="http://maven.apache.org/POM/4.0.0">
//     <modelVersion>4.0.0</modelVersion>
//     <groupId>com.example</groupId>
//     <artifactId>hello-maven</artifactId>
//     <version>1.0-SNAPSHOT</version>
//     <properties>
//       <maven.compiler.release>17</maven.compiler.release>
//       <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
//     </properties>
//     <build>
//       <finalName>hello-maven</finalName>
//       <plugins>
//         <plugin>
//           <groupId>org.apache.maven.plugins</groupId>
//           <artifactId>maven-jar-plugin</artifactId>
//           <version>3.4.1</version>
//           <configuration>
//             <archive><manifest><mainClass>com.example.HelloMaven</mainClass></manifest></archive>
//           </configuration>
//         </plugin>
//       </plugins>
//     </build>
//   </project>
//
// 目录结构（Maven 的约定）：本文件内容放 src/main/java/com/example/HelloMaven.java
// 编译/运行命令（工程根目录）:
//   1. mvn clean package                    # 实测: BUILD SUCCESS, 产物 target/hello-maven.jar（2140 字节）
// 说明: examples/ex04-maven-minimal 同样内容带 XML 注释头实测 2552 字节——maven-jar-plugin 默认把 pom.xml
//       嵌进 jar 的 META-INF/maven/ 下, 体积含 pom 本身, 数字差异不影响功能
//   2. java -jar target/hello-maven.jar     # 实测输出: hello maven
//   3. unzip -p target/hello-maven.jar META-INF/MANIFEST.MF   # 实测含 "Main-Class: com.example.HelloMaven"
// 要点：不写 archive/manifest 配置时打出的 jar 没有 Main-Class, java -jar 报「中没有主清单属性」（对照 examples/ex02）
// ---------------------------------------------------------------------------
package com.example;

public class HelloMaven {
    public static void main(String[] args) {
        System.out.println("hello maven");
    }
}
