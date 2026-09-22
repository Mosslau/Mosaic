/* exercises/sol-05-DateUtil.java —— 练习 5 日期计算工具参考实现
 * 验证环境：OpenJDK 17.0.16
 * 编译：javac sol-05-DateUtil.java
 * 运行：java DateUtil
 * 已验证：本环境编译零错误，输出符合注释中的期望值
 */
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;

class DateUtil {
    static long daysBetween(LocalDate from, LocalDate to) {
        return ChronoUnit.DAYS.between(from, to);
    }

    // 工作日 = 周一至周五（不含法定节假日）
    static boolean isWorkday(LocalDate date) {
        DayOfWeek dow = date.getDayOfWeek();
        return dow != DayOfWeek.SATURDAY && dow != DayOfWeek.SUNDAY;
    }

    public static void main(String[] args) {
        System.out.println(daysBetween(
                LocalDate.of(2026, 8, 1), LocalDate.of(2026, 8, 30)));  // 29
        System.out.println(isWorkday(LocalDate.of(2026, 8, 30)));        // false（周日）
        System.out.println(isWorkday(LocalDate.of(2026, 8, 28)));        // true（周五）
    }
}
