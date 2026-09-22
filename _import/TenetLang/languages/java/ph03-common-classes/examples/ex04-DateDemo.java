/* examples/ex04-DateDemo.java —— 日期格式化、计算与解析（java.time）
 * 验证环境：OpenJDK 17.0.16
 * 编译：javac ex04-DateDemo.java
 * 运行：java DateDemo
 * 已验证：本环境编译零错误，输出为当天日期 + 固定推导结果（当天/7 天后/解析日期随运行日期变化）
 */
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;

class DateDemo {
    public static void main(String[] args) {
        // 当前日期
        LocalDate today = LocalDate.now();
        System.out.println("今天: " + today);

        // 格式化
        DateTimeFormatter fmt = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");
        LocalDateTime now = LocalDateTime.now();
        System.out.println("当前时间: " + now.format(fmt));

        // 日期计算：7 天后送达
        LocalDate delivery = today.plusDays(7);
        long daysUntil = ChronoUnit.DAYS.between(today, delivery);
        System.out.println("预计送达: " + delivery + "（" + daysUntil + " 天后）");

        // 解析字符串
        LocalDate christmas = LocalDate.parse("2026-12-25");
        System.out.println("解析日期: " + christmas + " 是 " + christmas.getDayOfWeek());
    }
}
