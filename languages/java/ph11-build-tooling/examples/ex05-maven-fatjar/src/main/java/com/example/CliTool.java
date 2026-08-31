// examples/ex05-maven-fatjar/src/main/java/com/example/CliTool.java —— CLI 小工具：统计文本文件并输出 JSON
// 演示点：声明 gson 依赖后直接 import 使用（依赖管理）、shade 打 fat jar 后 java -jar 单命令运行
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12；验证状态：已验证
// 编译/运行命令（工程根目录 examples/ex05-maven-fatjar/）:
//   1. mvn clean package
//   2. printf 'line1\nline2\nline3\n' > demo.txt
//      java -jar target/cli-tool.jar demo.txt
//      # 实测输出: {"file":"demo.txt","lines":3,"chars":18}
//   3. 不带参数: java -jar target/cli-tool.jar   # 实测: stderr 打印用法, 退出码 2
//   4. 体积对比: ls -la target/cli-tool.jar target/original-cli-tool.jar（fat ≈280KB vs 薄 2.8KB）
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
        // lines() 按换行符计数, 与 wc -l 语义一致（初版用 split("\n", -1) 对结尾换行会多算一行, 已修正）
        data.put("lines", content.lines().count());
        data.put("chars", content.length());
        System.out.println(new Gson().toJson(data));
    }
}
