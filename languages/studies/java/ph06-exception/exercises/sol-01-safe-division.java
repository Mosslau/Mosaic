// exercises/sol-01-safe-division.java —— 练习 1 安全除法参考实现
// 在示例 ex01 基础上新增：自定义兜底值重载 + 字符串解析容错（NumberFormatException）
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-01-safe-division.java
// 运行：java SafeDivisionSol
// 验证状态：已验证：OpenJDK 17.0.16
class SafeDivisionSol {
    // 防御性除法：除零时返回兜底值 0 并记录原因
    public static int safeDivide(int a, int b) {
        return safeDivide(a, b, 0);
    }

    // 重载：允许调用方自定义兜底值（如业务上「除零当作 1」）
    public static int safeDivide(int a, int b, int fallback) {
        try {
            return a / b;
        } catch (ArithmeticException e) {
            System.out.println("除数为 0，返回兜底值 " + fallback + ": " + e.getMessage());
            return fallback;
        }
    }

    // 字符串参数解析：NumberFormatException 与 ArithmeticException 单独捕获
    public static int parseAndDivide(String aStr, String bStr) {
        try {
            int a = Integer.parseInt(aStr);
            int b = Integer.parseInt(bStr);
            return safeDivide(a, b);
        } catch (NumberFormatException e) {
            System.out.println("非法数字格式，返回兜底值 0: " + e.getMessage());
            return 0;
        }
        // 说明：为什么 10 / 0 抛 ArithmeticException 而不是返回特殊值？
        // Java 整数除法在除数为 0 时无法表示「无穷/NaN」（那是浮点语义），
        // 语言选择把这种情况定义为异常路径——调用方必须显式处理。
    }

    public static void main(String[] args) {
        System.out.println("10 / 2 = " + safeDivide(10, 2));
        System.out.println("10 / 0 = " + safeDivide(10, 0));
        System.out.println("10 / 0 自定义兜底 -1 = " + safeDivide(10, 0, -1));
        System.out.println("abc / 2 = " + parseAndDivide("abc", "2"));
        System.out.println("10 / 0 = " + parseAndDivide("10", "0"));
    }
}
