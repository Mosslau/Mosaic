// 来源：languages/java/ph02-oop/project/README.md
// 说明：班级类——组合一组学生，提供平均分统计与第一名查询
// 验证环境：OpenJDK 17.0.16
// 编译：javac *.java
// 运行：java Main
// 验证状态：已验证：OpenJDK 17.0.16
import java.util.ArrayList;
import java.util.List;

class CourseClass {
    private final String className;
    private final List<Student> students = new ArrayList<>();

    CourseClass(String className) {
        this.className = className;
    }

    void enroll(Student student) {
        students.add(student);
    }

    double averageScore() {
        if (students.isEmpty()) return 0.0;
        double sum = 0;
        for (Student s : students) sum += s.averageScore();
        return sum / students.size();
    }

    Student topStudent() {
        Student top = null;
        for (Student s : students) {
            if (top == null || s.averageScore() > top.averageScore()) {
                top = s;
            }
        }
        return top;
    }

    void printReport() {
        System.out.println("班级: " + className + "，人数: " + students.size());
        for (Student s : students) {
            System.out.println("  " + s);
        }
        System.out.printf("  班级平均分: %.2f%n", averageScore());
        System.out.println("  第一名: " + (topStudent() == null ? "无" : topStudent().getName()));
    }
}
