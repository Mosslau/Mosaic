// examples/ex01-safe-division.java —— 安全除法：try/catch ArithmeticException 捕获除零，返回兜底值
// 对应主文档「6. 代码示例 / 示例 1」
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex01-safe-division.java
// 运行：java SafeDivision
// 验证状态：已验证：OpenJDK 17.0.16
class SafeDivision {
    // 防御性除法：除零时返回 0 并记录原因
    public static int safeDivide(int a, int b) {
        try {
            return a / b;
        } catch (ArithmeticException e) {
            System.out.println("除数为 0，返回兜底值: " + e.getMessage());
            return 0;
        }
    }

    public static void main(String[] args) {
        System.out.println("10 / 2 = " + safeDivide(10, 2));
        System.out.println("10 / 0 = " + safeDivide(10, 0));
        System.out.println("10 / 3 = " + safeDivide(10, 3));
    }
}
