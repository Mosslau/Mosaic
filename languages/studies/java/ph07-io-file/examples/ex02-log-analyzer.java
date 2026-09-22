// examples/ex02-log-analyzer.java —— 日志分析：BufferedReader 逐行 + 正则统计 ERROR 总数与各错误次数
// 对应主文档「6. 代码示例 / 示例 2」
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex02-log-analyzer.java
// 运行：java LogAnalyzer
// 验证状态：已验证：OpenJDK 17.0.16
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.regex.*;

class LogAnalyzer {
    public static void main(String[] args) throws IOException {
        Files.write(Paths.get("app.log"),
                Arrays.asList(
                        "2026-01-01 10:00:00 INFO 启动服务",
                        "2026-01-01 10:00:01 ERROR 数据库连接超时",
                        "2026-01-01 10:00:02 WARN 重试第 1 次",
                        "2026-01-01 10:00:03 ERROR 数据库连接超时",
                        "2026-01-01 10:00:04 ERROR 空指针: line 42"),
                StandardCharsets.UTF_8);
        Pattern errorPattern = Pattern.compile("ERROR (.+)$");  // 捕获错误信息
        Map<String, Integer> errorCount = new LinkedHashMap<>();
        int total = 0;

        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(
                        new FileInputStream("app.log"), "UTF-8"))) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.contains("ERROR")) {
                    total++;
                    Matcher m = errorPattern.matcher(line);
                    if (m.find()) {
                        errorCount.put(m.group(1),
                                errorCount.getOrDefault(m.group(1), 0) + 1);
                    }
                }
            }
        }

        System.out.println("ERROR 总数: " + total);
        for (Map.Entry<String, Integer> e : errorCount.entrySet()) {
            System.out.println("  " + e.getKey() + " x " + e.getValue());
        }
        Files.deleteIfExists(Paths.get("app.log"));
    }
}
