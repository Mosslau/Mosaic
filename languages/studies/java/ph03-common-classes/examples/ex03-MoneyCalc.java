/* examples/ex03-MoneyCalc.java —— 金额计算：浮点陷阱与 BigDecimal 正确用法
 * 验证环境：OpenJDK 17.0.16
 * 编译：javac ex03-MoneyCalc.java
 * 运行：java MoneyCalc
 * 已验证：本环境编译零错误，输出符合注释中的期望值
 */
import java.math.BigDecimal;
import java.math.RoundingMode;

class MoneyCalc {
    public static void main(String[] args) {
        // 浮点陷阱：0.1 + 0.2 不等于 0.3
        double a = 0.1;
        double b = 0.2;
        System.out.println("浮点 0.1 + 0.2 = " + (a + b));
        // 输出：0.30000000000000004

        // BigDecimal 正确做法
        BigDecimal price = new BigDecimal("19.99");
        BigDecimal quantity = new BigDecimal("3");
        BigDecimal total = price.multiply(quantity);
        System.out.println("单价 19.99 x 3 = " + total);  // 59.97

        // 含税计算：保留两位小数，四舍五入
        BigDecimal withTax = total.multiply(new BigDecimal("1.13"))
                .setScale(2, RoundingMode.HALF_UP);
        System.out.println("含税(13%) = " + withTax);      // 67.77
    }
}
