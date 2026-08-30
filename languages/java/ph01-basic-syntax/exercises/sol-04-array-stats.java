// exercises/sol-04-array-stats.java —— 练习 4 参考实现：数组最大值、最小值、平均值
// 验证环境：OpenJDK 17.0.16（建议 JDK 17+）
// 编译：javac sol-04-array-stats.java
// 运行：java Sol04ArrayStats
// 说明：类名 Sol04ArrayStats 与文件名不同（非 public 类）
// 已验证：本环境编译运行通过，对样例数组输出平均 81.33、最高 99、最低 63
class Sol04ArrayStats {
    public static void main(String[] args) {
        int[] scores = {78, 92, 85, 63, 99, 71};

        int sum = 0, max = scores[0], min = scores[0];
        for (int s : scores) {
            sum += s;
            if (s > max) max = s;
            if (s < min) min = s;
        }

        // 强转 double 是关键：sum / length 若都是 int 会做整数除法，小数部分被截断
        double avg = (double) sum / scores.length;
        System.out.printf("人数: %d%n", scores.length);
        System.out.printf("平均分: %.2f%n", avg);
        System.out.printf("最高分: %d%n", max);
        System.out.printf("最低分: %d%n", min);
    }
}
