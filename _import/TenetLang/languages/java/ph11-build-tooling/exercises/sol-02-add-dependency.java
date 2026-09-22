// exercises/sol-02-add-dependency.java —— 练习 2 参考实现：声明 gson 依赖并在代码中使用
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12（本机离线模式 mvn -o）
// 验证状态：已验证（下述 pom 与源码放入临时工程后实测, 数字见下）
// ---------------------------------------------------------------------------
// 本练习的 pom.xml：在 sol-01 的 pom 基础上加 dependencies 块（不需要 build 块也能编译打包）:
//
//   <project xmlns="http://maven.apache.org/POM/4.0.0">
//     <modelVersion>4.0.0</modelVersion>
//     <groupId>com.example</groupId>
//     <artifactId>json-tool</artifactId>
//     <version>1.0-SNAPSHOT</version>
//     <properties>
//       <maven.compiler.release>17</maven.compiler.release>
//       <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
//     </properties>
//     <dependencies>
//       <dependency>
//         <groupId>com.google.code.gson</groupId>
//         <artifactId>gson</artifactId>
//         <version>2.10.1</version>
//       </dependency>
//     </dependencies>
//   </project>
//
// 目录结构：本文件内容放 src/main/java/com/example/JsonTool.java
// 编译/运行命令（工程根目录）:
//   1. mvn clean package                    # 实测: BUILD SUCCESS, 产物 target/json-tool-1.0-SNAPSHOT.jar（2279 字节, 薄 jar）
//   2. mvn dependency:tree                  # 实测: \- com.google.code.gson:gson:jar:2.10.1:compile（gson 无传递依赖）
//   3. java -jar target/json-tool-1.0-SNAPSHOT.jar
//       # 实测报错: target/json-tool-1.0-SNAPSHOT.jar中没有主清单属性（薄 jar 没有 Main-Class, 属预期）
//   4. 手工拼 classpath 运行（薄 jar + 依赖 jar 都要在 classpath 上）:
//      默认本地仓库为 ~/.m2/repository; 本环境沙箱禁写 ~/.m2, 实测用 -Dmaven.repo.local 指向可写克隆
//      （repository-mvn 路径即该沙箱特例）, 正常环境直接用下面命令的默认路径即可
//      java -cp "target/json-tool-1.0-SNAPSHOT.jar:$HOME/.m2/repository/com/google/code/gson/gson/2.10.1/gson-2.10.1.jar" com.example.JsonTool
//       # 实测输出: {"name":"Java","phase":11,"tool":"Maven"}
// 要点：坐标声明依赖后直接 import 使用; 薄 jar 不含依赖类, 运行必须拼 classpath——练习 3 的 fat jar 就是来解决这个的
// ---------------------------------------------------------------------------
package com.example;

import com.google.gson.Gson;
import java.util.LinkedHashMap;
import java.util.Map;

public class JsonTool {
    public static void main(String[] args) {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("name", "Java");
        data.put("phase", 11);
        data.put("tool", "Maven");
        System.out.println(new Gson().toJson(data));
    }
}
