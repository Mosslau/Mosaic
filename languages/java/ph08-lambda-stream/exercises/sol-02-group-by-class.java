// exercises/sol-02-group-by-class.java —— 练习 2 参考实现：按班级分组
// 验证环境：OpenJDK 17.0.18
// 编译：javac sol-02-group-by-class.java
// 运行：java GroupByClassSol（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
import java.util.*;
import java.util.stream.*;

class GroupByClassSol {
    public static void main(String[] args) {
        List<Student> students = Arrays.asList(
                new Student("一班", "Alice", 92), new Student("一班", "Bob", 58),
                new Student("二班", "Cary", 76), new Student("二班", "Dana", 88),
                new Student("三班", "Eve", 65));

        // 分组 + 下游收集器：一次遍历得到每班全部统计量
        Map<String, IntSummaryStatistics> stats = students.stream()
                .collect(Collectors.groupingBy(
                        s -> s.clazz,
                        Collectors.summarizingInt(s -> s.score)));

        stats.forEach((clazz, st) -> System.out.printf(
                "%s: 人数=%d 平均=%.1f 最高=%d 最低=%d%n",
                clazz, st.getCount(), st.getAverage(), st.getMax(), st.getMin()));

        // 按平均分从高到低排名（对 entrySet 流排序）
        System.out.println("按平均分排名:");
        stats.entrySet().stream()
                .sorted((a, b) -> Double.compare(
                        b.getValue().getAverage(), a.getValue().getAverage()))
                .forEach(e -> System.out.printf("  %s 平均 %.1f%n",
                        e.getKey(), e.getValue().getAverage()));

        // 加分项：groupingBy 嵌套 mapping + joining，把每班姓名串成一行
        Map<String, String> namesByClass = students.stream()
                .collect(Collectors.groupingBy(
                        s -> s.clazz,
                        Collectors.mapping(s -> s.name, Collectors.joining(", "))));
        namesByClass.forEach((clazz, names) ->
                System.out.println(clazz + " 名单: " + names));
    }

    static class Student {
        String clazz, name;
        int score;
        Student(String clazz, String name, int score) {
            this.clazz = clazz; this.name = name; this.score = score;
        }
    }
}
