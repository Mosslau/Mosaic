// exercises/sol-02-log-analyzer.java —— 练习 2 参考实现：日志分析（逐行读取 + 级别计数 + ERROR 消息降序）
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-02-log-analyzer.java
// 运行：java LogAnalyzerSol
// 验证状态：已验证：OpenJDK 17.0.16
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.regex.*;
import java.util.stream.*;

class LogAnalyzerSol {
    public static void main(String[] args) throws IOException {
        Path p = Paths.get("app.log");
        Files.write(p, Arrays.asList(
                "2026-01-01 10:00:00 INFO 启动服务",
                "2026-01-01 10:00:01 ERROR 数据库连接超时",
                "2026-01-01 10:00:02 WARN 重试第 1 次",
                "2026-01-01 10:00:03 ERROR 数据库连接超时",
                "2026-01-01 10:00:04 INFO 收到请求 /api/user",
                "2026-01-01 10:00:05 ERROR 空指针: line 42",
                "2026-01-01 10:00:06 WARN 内存使用率 85%",
                "2026-01-01 10:00:07 ERROR 请求超时"), StandardCharsets.UTF_8);

        Map<String, Integer> levelCount = new LinkedHashMap<>();
        Map<String, Integer> errorMsg = new HashMap<>();
        int keywordLines = 0;
        Pattern errorPattern = Pattern.compile("ERROR (.+)$");

        // 逐行读取：大文件内存占用恒定，禁止 readAllLines
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(new FileInputStream(p.toFile()), "UTF-8"))) {
            String line;
            while ((line = reader.readLine()) != null) {
                for (String level : new String[]{"INFO", "WARN", "ERROR"}) {
                    if (line.contains(" " + level + " ")) {
                        levelCount.merge(level, 1, Integer::sum);
                        break;
                    }
                }
                if (line.contains("超时")) {
                    keywordLines++;
                }
                Matcher m = errorPattern.matcher(line);
                if (m.find()) {
                    errorMsg.merge(m.group(1), 1, Integer::sum);
                }
            }
        }

        System.out.println("级别统计: " + levelCount);
        System.out.println("含「超时」的行: " + keywordLines);
        System.out.println("ERROR 消息（按次数降序）:");
        errorMsg.entrySet().stream()
                .sorted(Map.Entry.<String, Integer>comparingByValue().reversed()
                        .thenComparing(Map.Entry.comparingByKey()))
                .forEach(e -> System.out.println("  " + e.getKey() + " x " + e.getValue()));

        Files.deleteIfExists(p);
    }
}
