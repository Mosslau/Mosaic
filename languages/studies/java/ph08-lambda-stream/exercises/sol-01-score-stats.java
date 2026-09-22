// exercises/sol-01-score-stats.java —— 练习 1 参考实现：过滤学生成绩并统计平均分
// 验证环境：OpenJDK 17.0.18
// 编译：javac sol-01-score-stats.java
// 运行：java ScoreStatsSol（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
import java.util.*;
import java.util.stream.*;

class ScoreStatsSol {
    public static void main(String[] args) {
        List<Student> students = Arrays.asList(
                new Student("Alice", 92), new Student("Bob", 58),
                new Student("Cary", 76), new Student("Dana", 45));

        // 过滤及格 -> 映射姓名 -> 收集（全程无 for 循环）
        List<String> passed = students.stream()
                .filter(s -> s.score >= 60)
                .map(s -> s.name)
                .collect(Collectors.toList());
        System.out.println("及格名单: " + passed);

        // 数值统计：mapToInt 避免装箱；average 返回 OptionalDouble，空集合用 orElse(0) 兜底
        double avg = students.stream().mapToInt(s -> s.score).average().orElse(0);
        int max = students.stream().mapToInt(s -> s.score).max().orElse(0);
        int min = students.stream().mapToInt(s -> s.score).min().orElse(0);
        long passedCount = students.stream().filter(s -> s.score >= 60).count();
        System.out.printf("平均分: %.1f, 最高分: %d, 最低分: %d, 及格率: %.0f%%%n",
                avg, max, min, passedCount * 100.0 / students.size());

        // 空集合验收：不抛异常，平均分输出 0
        List<Student> empty = Collections.emptyList();
        System.out.println("空集合平均分: " + empty.stream()
                .mapToInt(s -> s.score).average().orElse(0));
    }

    static class Student {
        String name;
        int score;
        Student(String name, int score) { this.name = name; this.score = score; }
    }
}
