// examples/ex04-log-stream.java —— 日志过滤统计：Files.lines + Stream 流水线（衔接 ph07）
// 对应主文档 6. 示例 4：逐行读入，Stream 过滤、清洗、分组计数
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex04-log-stream.java
// 运行：java LogStream（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.stream.*;

class LogStream {
    public static void main(String[] args) throws IOException {
        Path log = Paths.get("app.log");
        Files.write(log, Arrays.asList(
                "2026-01-01 10:00:00 INFO 启动服务",
                "2026-01-01 10:00:01 ERROR 数据库连接超时",
                "2026-01-01 10:00:02 WARN 重试第 1 次",
                "2026-01-01 10:00:03 ERROR 数据库连接超时",
                "2026-01-01 10:00:04 ERROR 空指针: line 42"),
                StandardCharsets.UTF_8);

        try (Stream<String> lines = Files.lines(log, StandardCharsets.UTF_8)) {
            long errorCount = lines
                    .filter(line -> line.contains("ERROR"))
                    .count();
            System.out.println("ERROR 行数: " + errorCount);
        }   // Files.lines 的流用完必须关闭（同 ph07）

        try (Stream<String> lines = Files.lines(log, StandardCharsets.UTF_8)) {
            Map<String, Long> errors = lines
                    .filter(line -> line.contains("ERROR"))
                    .map(line -> line.replaceFirst("^.*ERROR ", ""))  // 清洗时间戳前缀
                    .collect(Collectors.groupingBy(msg -> msg, Collectors.counting()));
            errors.forEach((msg, n) -> System.out.println("  " + msg + " x " + n));
        }
        Files.deleteIfExists(log);
    }
}
