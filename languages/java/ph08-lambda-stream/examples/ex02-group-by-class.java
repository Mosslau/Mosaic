// examples/ex02-group-by-class.java —— 按班级分组统计：groupingBy + summarizingInt
// 对应主文档 6. 示例 2：分组 + 下游收集器一次算出各班全部统计量
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex02-group-by-class.java
// 运行：java GroupByClass（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
import java.util.*;
import java.util.stream.*;

class GroupByClass {
    public static void main(String[] args) {
        List<Student> students = Arrays.asList(
                new Student("一班", "Alice", 92), new Student("一班", "Bob", 58),
                new Student("二班", "Cary", 76), new Student("二班", "Dana", 88),
                new Student("三班", "Eve", 65));

        Map<String, IntSummaryStatistics> stats = students.stream()
                .collect(Collectors.groupingBy(
                        s -> s.clazz,
                        Collectors.summarizingInt(s -> s.score)));

        stats.forEach((clazz, st) -> System.out.printf(
                "%s: 人数=%d 平均=%.1f 最高=%d 最低=%d%n",
                clazz, st.getCount(), st.getAverage(), st.getMax(), st.getMin()));

        System.out.println("按平均分排名:");
        stats.entrySet().stream()
                .sorted((a, b) -> Double.compare(
                        b.getValue().getAverage(), a.getValue().getAverage()))
                .forEach(e -> System.out.println("  " + e.getKey()
                        + " 平均 " + e.getValue().getAverage()));
    }

    static class Student {
        String clazz, name;
        int score;
        Student(String clazz, String name, int score) {
            this.clazz = clazz; this.name = name; this.score = score;
        }
    }
}
