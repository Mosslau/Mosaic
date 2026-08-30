// 来源：languages/java/ph02-oop/project/README.md
// 说明：学生类——private 字段 + 成绩列表（对外暴露不可变视图）+ 平均分计算
// 验证环境：OpenJDK 17.0.16
// 编译：javac *.java
// 运行：java Main
// 验证状态：已验证：OpenJDK 17.0.16
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

class Student {
    private final String id;
    private String name;
    private int age;
    private final List<ScoreEntry> scores = new ArrayList<>();

    Student(String id, String name, int age) {
        this.id = id;
        this.name = name;
        this.age = age;
    }

    public String getId() { return id; }
    public String getName() { return name; }
    public int getAge() { return age; }

    public void addScore(String subject, double score) {
        scores.add(new ScoreEntry(subject, score));  // 校验在 record 构造器中
    }

    public List<ScoreEntry> getScores() {
        return Collections.unmodifiableList(scores);  // 不可变视图，外部无法篡改
    }

    public double averageScore() {
        if (scores.isEmpty()) return 0.0;
        double sum = 0;
        for (ScoreEntry e : scores) sum += e.score();
        return sum / scores.size();
    }

    @Override
    public String toString() {
        return "Student{id='" + id + "', name='" + name + "', age=" + age
                + ", avg=" + String.format("%.2f", averageScore()) + "}";
    }
}
