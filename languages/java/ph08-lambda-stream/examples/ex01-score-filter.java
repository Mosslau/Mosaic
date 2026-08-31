// examples/ex01-score-filter.java —— 过滤学生成绩：filter + map + 统计
// 对应主文档 6. 示例 1：过滤及格、映射姓名、统计平均分与及格率
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex01-score-filter.java
// 运行：java ScoreFilter（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
import java.util.*;
import java.util.stream.*;

class ScoreFilter {
    public static void main(String[] args) {
        List<Student> students = Arrays.asList(
                new Student("Alice", 92), new Student("Bob", 58),
                new Student("Cary", 76), new Student("Dana", 45));

        // filter 过滤 -> map 取姓名 -> collect 收集
        List<String> passed = students.stream()
                .filter(s -> s.score >= 60)
                .map(s -> s.name)
                .collect(Collectors.toList());
        System.out.println("及格名单: " + passed);

        double avg = students.stream().mapToInt(s -> s.score)
                .average().orElse(0);
        int max = students.stream().mapToInt(s -> s.score)
                .max().orElse(0);
        long passedCount = students.stream()
                .filter(s -> s.score >= 60).count();
        System.out.printf("平均分: %.1f, 最高分: %d, 及格率: %.0f%%%n",
                avg, max, passedCount * 100.0 / students.size());
    }

    // 教学简化：为聚焦 Stream 主题，字段未做封装（省略 private + getter）
    static class Student {
        String name;
        int score;
        Student(String name, int score) { this.name = name; this.score = score; }
    }
}
