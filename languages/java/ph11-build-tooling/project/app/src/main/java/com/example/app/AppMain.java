// project/app/src/main/java/com/example/app/AppMain.java —— 业务模块入口：文本统计 CLI
// 依赖 common 模块（单向）+ gson（版本由父工程 dependencyManagement 提供）; 产物为可执行 fat jar
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12；验证状态：已验证
// 运行（在 project/ 根目录执行构建后）:
//   java -jar app/target/app-1.0-SNAPSHOT.jar demo.txt
//   实测输出: {"file":"demo.txt","lines":2,"words":3,"chars":21}
package com.example.app;

import com.example.common.TextStats;
import com.google.gson.Gson;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

public class AppMain {
    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("用法: java -jar app-1.0-SNAPSHOT.jar <文件路径>");
            System.exit(2);
        }
        Path file = Path.of(args[0]);
        String content = Files.readString(file);
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("file", file.toString());
        data.put("lines", TextStats.countLines(content));
        data.put("words", TextStats.countWords(content));
        data.put("chars", TextStats.countChars(content));
        System.out.println(new Gson().toJson(data));
    }
}
