// project/GradeStats.java —— ph01 阶段项目：成绩统计工具
// 需求：录入多个成绩，统计平均分、最高分、最低分和等级分布（A/B/C/D/F）
// 验证环境：OpenJDK 17.0.16（建议 JDK 17+）
// 编译：javac GradeStats.java
// 运行：java GradeStats   （交互式，先输入成绩个数，再逐个输入 0~100 的成绩）
// 已验证：本环境编译运行通过；样例 5 个成绩 90 85 78 62 55 输出平均 74.00、
//         最高 90、最低 55，等级分布 A=1 B=1 C=1 D=1 F=1
import java.util.Scanner;

public class GradeStats {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);

        System.out.print("要录入多少个成绩？ ");
        int count = scanner.nextInt();
        int[] scores = new int[count];

        // 逐个读入成绩，非法输入（超出 0~100）要求重新输入
        for (int i = 0; i < count; i++) {
            System.out.printf("第 %d 个成绩 (0-100): ", i + 1);
            int score = scanner.nextInt();
            if (score < 0 || score > 100) {
                System.out.println("成绩必须在 0~100 之间，请重新输入");
                i--;  // 本次作废，重读这个下标
                continue;
            }
            scores[i] = score;
        }

        // 一次循环同时求出和、最大值、最小值
        int sum = 0, max = scores[0], min = scores[0];
        for (int s : scores) {
            sum += s;
            if (s > max) max = s;
            if (s < min) min = s;
        }
        double avg = (double) sum / count;  // 强转 double，避免整数除法截断

        // 等级分布：gradeCounts[0]=A, [1]=B, [2]=C, [3]=D, [4]=F
        int[] gradeCounts = new int[5];
        for (int s : scores) {
            int index = switch (s / 10) {
                case 9, 10 -> 0;  // 90~100 为 A
                case 8 -> 1;
                case 7 -> 2;
                case 6 -> 3;
                default -> 4;     // 0~59 为 F
            };
            gradeCounts[index]++;
        }

        System.out.println("\n===== 成绩统计 =====");
        System.out.printf("人数: %d%n", count);
        System.out.printf("平均分: %.2f%n", avg);
        System.out.printf("最高分: %d%n", max);
        System.out.printf("最低分: %d%n", min);
        char[] grades = {'A', 'B', 'C', 'D', 'F'};
        for (int i = 0; i < grades.length; i++) {
            System.out.printf("%c 等级: %d 人%n", grades[i], gradeCounts[i]);
        }

        scanner.close();
    }
}
