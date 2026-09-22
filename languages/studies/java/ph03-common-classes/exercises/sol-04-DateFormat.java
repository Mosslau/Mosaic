/* exercises/sol-04-DateFormat.java —— 练习 4 日期格式化参考实现
 * 验证环境：OpenJDK 17.0.16
 * 编译：javac sol-04-DateFormat.java
 * 运行：java DateFormat
 * 已验证：本环境编译零错误，输出符合注释中的期望值
 */
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

class DateFormat {
    private static final DateTimeFormatter FMT =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    static String format(LocalDateTime dt) {
        return dt.format(FMT);
    }

    static LocalDateTime parse(String s) {
        return LocalDateTime.parse(s, FMT);
    }

    public static void main(String[] args) {
        System.out.println(format(LocalDateTime.of(2026, 8, 8, 14, 30)));  // 2026-08-08 14:30
        System.out.println(parse("2026-08-08 14:30"));                      // 2026-08-08T14:30
    }
}
