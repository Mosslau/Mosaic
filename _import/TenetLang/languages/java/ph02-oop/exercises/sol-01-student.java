// 来源：languages/java/ph02-oop/exercises/README.md 练习 1
// 说明：学生类建模——private 字段 + 构造初始化 + setScore 校验 + 重写 toString
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-01-student.java
// 运行：java StudentMain
// 验证状态：已验证：OpenJDK 17.0.16
class Student {
    private String name;
    private int age;
    private double score;

    Student(String name, int age) {
        this.name = name;
        this.age = age;
    }

    public String getName() { return name; }
    public int getAge() { return age; }
    public double getScore() { return score; }

    public void setScore(double score) {
        if (score < 0 || score > 100) {
            throw new IllegalArgumentException("分数必须在 0-100 之间: " + score);
        }
        this.score = score;
    }

    @Override
    public String toString() {
        return "Student{name='" + name + "', age=" + age + ", score=" + score + "}";
    }
}

class StudentMain {
    public static void main(String[] args) {
        Student s = new Student("Alice", 20);
        s.setScore(92.5);
        System.out.println(s);

        try {
            s.setScore(120);
        } catch (IllegalArgumentException e) {
            System.out.println("校验拦截: " + e.getMessage());
        }
    }
}
