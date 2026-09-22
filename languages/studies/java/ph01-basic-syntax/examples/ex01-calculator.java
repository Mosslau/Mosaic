// examples/ex01-calculator.java —— 命令行计算器：读算式求值，处理除零与未知运算符
// 对应主文档「6. 代码示例 / 示例 1」
// 验证环境：OpenJDK 17.0.16（建议 JDK 17+）
// 编译：javac ex01-calculator.java
// 运行：java Calculator   （然后输入如 3 + 4 回车）
// 说明：类名 Calculator 与文件名不同（非 public 类），不能用 java ex01-calculator 运行
// 已验证：本环境编译通过，输入 3 + 4 输出 3.00 + 4.00 = 7.00，输入 1 / 0 输出 NaN
import java.util.Scanner;

class Calculator {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);

        System.out.print("输入算式 (如 3 + 4): ");
        double a = scanner.nextDouble();
        String op = scanner.next();
        double b = scanner.nextDouble();

        // switch 表达式（Java 14+）：直接产出值，箭头语法无需 break
        double result = switch (op) {
            case "+" -> a + b;
            case "-" -> a - b;
            case "*" -> a * b;
            case "/" -> b != 0 ? a / b : Double.NaN;  // 除零输出 NaN 而不是崩溃
            default -> {
                System.out.println("不支持的操作符");
                yield 0;
            }
        };

        System.out.printf("%.2f %s %.2f = %.2f%n", a, op, b, result);
        scanner.close();
    }
}
