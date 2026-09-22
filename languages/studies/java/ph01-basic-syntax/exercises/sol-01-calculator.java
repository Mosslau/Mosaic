// exercises/sol-01-calculator.java —— 练习 1 参考实现：命令行计算器
// 验证环境：OpenJDK 17.0.16（建议 JDK 17+）
// 编译：javac sol-01-calculator.java
// 运行：java Sol01Calculator   （然后输入如 3 + 4 回车）
// 说明：类名 Sol01Calculator 与文件名不同（非 public 类）
// 已验证：本环境编译运行通过，输入 3 + 4 输出 7.00，输入 1 / 0 提示除零，输入 5 ^ 2 提示不支持
import java.util.Scanner;

class Sol01Calculator {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);

        System.out.print("输入算式 (如 3 + 4): ");
        double a = scanner.nextDouble();
        String op = scanner.next();
        double b = scanner.nextDouble();

        // 不用 switch 表达式，用传统 switch 把错误分支分开写，便于看清三种处理
        switch (op) {
            case "+":
                System.out.printf("%.2f%n", a + b);
                break;
            case "-":
                System.out.printf("%.2f%n", a - b);
                break;
            case "*":
                System.out.printf("%.2f%n", a * b);
                break;
            case "/":
                if (b != 0) {
                    System.out.printf("%.2f%n", a / b);
                } else {
                    System.out.println("错误: 除数为零");
                }
                break;
            default:
                System.out.println("不支持的操作符: " + op);
                break;
        }
        scanner.close();
    }
}
