// project/log-stats.java —— 阶段项目：日志过滤统计
// 对应 Roadmap「ph08 Lambda 与 Stream 阶段」推荐项目第一个「日志过滤统计」
// 读取日志文件（衔接 ph07 的 Files.lines），用 Stream 过滤 ERROR/WARN、清洗行内容、
// 按错误信息分组计数并输出 TopN；逐行处理保持内存恒定
// 验证环境：OpenJDK 17.0.18
// 编译：javac log-stats.java
// 运行：java LogStatsTool <日志文件> [级别]   或   java LogStatsTool（自测）
// 验证状态：已验证：OpenJDK 17.0.18
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.stream.*;

class LogStatsTool {

    // 日志行格式：`2026-01-01 10:00:01 ERROR 数据库连接超时`（日期 时间 级别 消息）
    // record 是不可变数据载体（Java 16+），比手写 POJO 少一屏样板
    record LogEntry(String level, String message) { }

    // ==================== 命令行入口 ====================
    public static void main(String[] args) throws IOException {
        if (args.length == 0) {
            selfTest();                            // 无参数：跑自测
            return;
        }
        Path log = Paths.get(args[0]);
        if (!Files.exists(log)) {
            System.err.println("日志文件不存在: " + log);
            System.exit(1);
        }
        printLevelCounts(log);
        printTopErrors(log, 5);

        // 可选第二参数：按级别过滤并打印原始行，如 `java LogStatsTool app.log ERROR`
        if (args.length >= 2) {
            String level = args[1].toUpperCase(Locale.ROOT);
            System.out.println("== 级别 " + level + " 的原始行 ==");
            try (Stream<String> lines = Files.lines(log, StandardCharsets.UTF_8)) {
                lines.filter(line -> parse(line).map(e -> e.level().equals(level)).orElse(false))
                     .forEach(System.out::println);
            }
        }
    }

    // ==================== 解析 ====================
    // 解析一行为 LogEntry；格式不合法返回 Optional.empty()——「可能没有」用 Optional 表达
    static Optional<LogEntry> parse(String line) {
        String[] parts = line.split("\\s+", 4);
        if (parts.length < 3) {
            return Optional.empty();
        }
        String message = parts.length == 4 ? parts[3] : "";
        return Optional.of(new LogEntry(parts[2], message));
    }

    // ==================== 统计逻辑 ====================
    // 各级别行数：filter 掉非法行 -> groupingBy + counting
    static Map<String, Long> countByLevel(Path log) throws IOException {
        try (Stream<String> lines = Files.lines(log, StandardCharsets.UTF_8)) {   // 流用完必须关闭
            return lines.map(LogStatsTool::parse)
                        .flatMap(Optional::stream)       // Optional 转 Stream，天然跳过非法行
                        .collect(Collectors.groupingBy(LogEntry::level, Collectors.counting()));
        }
    }

    // 错误信息 TopN：只留 ERROR -> 按消息分组计数 -> 降序排序 -> limit 截取
    static List<Map.Entry<String, Long>> topErrors(Path log, int n) throws IOException {
        try (Stream<String> lines = Files.lines(log, StandardCharsets.UTF_8)) {
            Map<String, Long> counts = lines.map(LogStatsTool::parse)
                    .flatMap(Optional::stream)
                    .filter(e -> e.level().equals("ERROR"))
                    .collect(Collectors.groupingBy(LogEntry::message, Collectors.counting()));
            return counts.entrySet().stream()
                    .sorted(Map.Entry.<String, Long>comparingByValue().reversed()
                            .thenComparing(Map.Entry.comparingByKey()))   // 次数相同按字典序，输出稳定
                    .limit(n)
                    .collect(Collectors.toList());
        }
    }

    // ==================== 报表输出 ====================
    static void printLevelCounts(Path log) throws IOException {
        Map<String, Long> counts = countByLevel(log);
        long total = counts.values().stream().mapToLong(Long::longValue).sum();
        System.out.println("== 级别统计（共 " + total + " 行有效日志）==");
        // 固定顺序输出常见级别，其余级别排在后面
        Stream.concat(
                        Stream.of("INFO", "WARN", "ERROR").filter(counts::containsKey),
                        counts.keySet().stream().filter(l -> !List.of("INFO", "WARN", "ERROR").contains(l)).sorted())
                .forEach(level -> System.out.printf("  %-5s %d 行（%.1f%%）%n",
                        level, counts.get(level), counts.get(level) * 100.0 / total));
    }

    static void printTopErrors(Path log, int n) throws IOException {
        List<Map.Entry<String, Long>> top = topErrors(log, n);
        System.out.println("== ERROR Top" + n + " ==");
        if (top.isEmpty()) {
            System.out.println("  （无 ERROR 日志）");
            return;
        }
        // joining 把 TopN 拼成一段报表文本
        String report = top.stream()
                .map(e -> "  " + e.getKey() + " x " + e.getValue())
                .collect(Collectors.joining("\n"));
        System.out.println(report);
        // Optional 表达「最高频错误可能没有」
        top.stream().findFirst()
                .map(e -> e.getKey())
                .ifPresent(msg -> System.out.println("最高频错误: " + msg));
    }

    // ==================== 自测 ====================
    static void selfTest() throws IOException {
        Path log = Paths.get("log-stats-test.log");
        Files.write(log, Arrays.asList(
                "2026-01-01 10:00:00 INFO 启动服务",
                "2026-01-01 10:00:01 ERROR 数据库连接超时",
                "2026-01-01 10:00:02 WARN 重试第 1 次",
                "2026-01-01 10:00:03 ERROR 数据库连接超时",
                "2026-01-01 10:00:04 ERROR 空指针: line 42",
                "2026-01-01 10:00:05 INFO 请求完成 200",
                "这是一行格式不合法的日志",
                "2026-01-01 10:00:06 ERROR 数据库连接超时"),
                StandardCharsets.UTF_8);
        try {
            // 1. 级别计数：INFO 2、WARN 1、ERROR 4（超时 x3 + 空指针 x1），非法行被跳过
            Map<String, Long> counts = countByLevel(log);
            assertTrue(counts.get("INFO") == 2, "INFO 应为 2，实际 " + counts.get("INFO"));
            assertTrue(counts.get("WARN") == 1, "WARN 应为 1，实际 " + counts.get("WARN"));
            assertTrue(counts.get("ERROR") == 4, "ERROR 应为 4，实际 " + counts.get("ERROR"));
            assertTrue(counts.size() == 3, "非法行不应产生级别，实际级别数 " + counts.size());

            // 2. TopN：数据库连接超时 x3 排第一，空指针 x1 排第二
            List<Map.Entry<String, Long>> top = topErrors(log, 5);
            assertTrue(top.size() == 2, "ERROR 种类应为 2，实际 " + top.size());
            assertTrue(top.get(0).getKey().equals("数据库连接超时") && top.get(0).getValue() == 3,
                    "Top1 应为「数据库连接超时 x3」");
            assertTrue(top.get(1).getKey().equals("空指针: line 42") && top.get(1).getValue() == 1,
                    "Top2 应为「空指针 x1」");

            // 3. 报表输出走一遍（人工目检格式）
            printLevelCounts(log);
            printTopErrors(log, 5);

            // 4. 无 ERROR 的日志：TopN 输出「无 ERROR 日志」而不抛异常
            Path emptyLog = Paths.get("log-stats-empty.log");
            Files.write(emptyLog, Arrays.asList("2026-01-01 10:00:00 INFO 只有 INFO"),
                    StandardCharsets.UTF_8);
            assertTrue(topErrors(emptyLog, 5).isEmpty(), "无 ERROR 时 TopN 应为空列表");
            Files.deleteIfExists(emptyLog);
        } finally {
            Files.deleteIfExists(log);
        }
        System.out.println("全部自测通过");
    }

    // 自测断言：失败即抛 AssertionError，不静默
    static void assertTrue(boolean cond, String msg) {
        if (!cond) {
            throw new AssertionError(msg);
        }
    }
}
