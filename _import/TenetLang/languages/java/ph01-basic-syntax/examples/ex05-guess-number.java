// examples/ex05-guess-number.java —— 猜数字游戏：随机生成 1-100，提示太大/太小
// 对应主文档「6. 代码示例 / 示例 5」
// 验证环境：OpenJDK 17.0.16（建议 JDK 17+）
// 编译：javac ex05-guess-number.java
// 运行：java GuessNumber   （交互式，按提示输入数字）
// 说明：类名 GuessNumber 与文件名不同（非 public 类）
// 已验证：本环境编译运行通过，输入正确数字后输出尝试次数并退出
import java.util.Random;
import java.util.Scanner;

class GuessNumber {
    public static void main(String[] args) {
        Random random = new Random();
        int secret = random.nextInt(100) + 1;  // nextInt(100) 返回 0~99，+1 得 1~100
        int attempts = 0;
        Scanner scanner = new Scanner(System.in);

        System.out.println("猜一个 1-100 之间的数字！");

        while (true) {
            System.out.print("你的猜测: ");
            int guess = scanner.nextInt();
            attempts++;

            if (guess < secret) {
                System.out.println("太小了！");
            } else if (guess > secret) {
                System.out.println("太大了！");
            } else {
                System.out.printf("猜对了！共尝试 %d 次。%n", attempts);
                break;
            }
        }
        scanner.close();
    }
}
