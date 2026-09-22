// examples/ex03-array-stats.java —— 数组统计：最大值、最小值、平均值
// 对应主文档「6. 代码示例 / 示例 3」
// 验证环境：OpenJDK 17.0.16（建议 JDK 17+）
// 编译：javac ex03-array-stats.java
// 运行：java ArrayStats
// 说明：类名 ArrayStats 与文件名不同（非 public 类）
// 已验证：本环境编译运行通过，对样例数组输出平均 81.33、最高 99、最低 63
class ArrayStats {
    public static void main(String[] args) {
        int[] scores = {78, 92, 85, 63, 99, 71};

        // 一次增强 for 循环同时求出和、最大值、最小值
        int sum = 0, max = scores[0], min = scores[0];
        for (int s : scores) {
            sum += s;
            if (s > max) max = s;
            if (s < min) min = s;
        }

        double avg = (double) sum / scores.length;  // 强转 double 避免整数除法截断
        System.out.printf("人数: %d%n", scores.length);
        System.out.printf("平均分: %.2f%n", avg);
        System.out.printf("最高: %d, 最低: %d%n", max, min);
    }
}
