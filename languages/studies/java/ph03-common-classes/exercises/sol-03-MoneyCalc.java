/* exercises/sol-03-MoneyCalc.java —— 练习 3 金额计算参考实现
 * 验证环境：OpenJDK 17.0.16
 * 编译：javac sol-03-MoneyCalc.java
 * 运行：java MoneyCalc
 * 已验证：本环境编译零错误，输出符合注释中的期望值
 */
import java.math.BigDecimal;
import java.math.RoundingMode;

class MoneyCalc {
    // 计算含税金额：price × quantity × (1 + taxRate)，保留两位小数，四舍五入
    static String withTax(String price, String quantity, String taxRate) {
        BigDecimal p = new BigDecimal(price);          // 字符串构造，避免浮点陷阱
        BigDecimal q = new BigDecimal(quantity);
        BigDecimal rate = new BigDecimal(taxRate);
        return p.multiply(q)
                .multiply(BigDecimal.ONE.add(rate))
                .setScale(2, RoundingMode.HALF_UP)
                .toString();
    }

    public static void main(String[] args) {
        System.out.println(withTax("19.99", "3", "0.13"));  // 67.77
        System.out.println(withTax("0.1", "3", "0.0"));     // 0.30
    }
}
