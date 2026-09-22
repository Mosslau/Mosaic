// exercises/sol-03-executable-jar.java —— 练习 3 参考实现：shade 打可执行 fat jar
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12（本机离线模式 mvn -o）
// 验证状态：已验证（下述 pom 与源码放入临时工程后实测, 数字见下）
// ---------------------------------------------------------------------------
// 本练习的 pom.xml：在 sol-02 的 pom 基础上加 <build> 块（gson 依赖保留）:
//
//   <build>
//     <finalName>cli-tool</finalName>
//     <plugins>
//       <plugin>
//         <groupId>org.apache.maven.plugins</groupId>
//         <artifactId>maven-shade-plugin</artifactId>
//         <version>3.5.1</version>
//         <executions>
//           <execution>
//             <phase>package</phase>
//             <goals><goal>shade</goal></goals>
//             <configuration>
//               <transformers>
//                 <transformer implementation="org.apache.maven.plugins.shade.resource.ManifestResourceTransformer">
//                   <mainClass>com.example.CliTool</mainClass>
//                 </transformer>
//               </transformers>
//             </configuration>
//           </execution>
//         </executions>
//       </plugin>
//     </plugins>
//   </build>
//
// 目录结构：本文件内容放 src/main/java/com/example/CliTool.java
// 编译/运行命令（工程根目录）:
//   1. mvn clean package
//       # 实测: BUILD SUCCESS; target/cli-tool.jar 286933 字节（≈280KB, 含 gson）
//       #       target/original-cli-tool.jar 2857 字节（薄 jar, 不含依赖）——体积差即「依赖合并」证据
// 说明: examples/ex05-maven-fatjar 同样内容带 XML 注释头实测 287538/3462 字节——jar 内嵌 pom 所致, 不影响功能
//   2. printf 'line1\nline2\nline3\n' > demo.txt
//      java -jar target/cli-tool.jar demo.txt
//       # 实测输出: {"file":"demo.txt","lines":3,"chars":18}
//   3. java -jar target/cli-tool.jar        # 实测: stderr 打印用法, 退出码 2
// 要点：shade 把依赖类重打包进同一 jar 并写 Main-Class（ManifestResourceTransformer）;
//       行数用 lines().count()（与 wc -l 一致）——初版用 split("\n", -1) 对结尾换行会多算一行, 已修正
// ---------------------------------------------------------------------------
package com.example;

import com.google.gson.Gson;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

public class CliTool {
    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("用法: java -jar cli-tool.jar <文件路径>");
            System.exit(2);
        }
        Path file = Path.of(args[0]);
        String content = Files.readString(file);
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("file", file.toString());
        data.put("lines", content.lines().count());
        data.put("chars", content.length());
        System.out.println(new Gson().toJson(data));
    }
}
