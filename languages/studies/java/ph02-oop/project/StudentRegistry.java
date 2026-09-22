// 来源：languages/java/ph02-oop/project/README.md
// 说明：学生注册表——按 id 注册/查找/删除，重复 id 拒绝注册
// 验证环境：OpenJDK 17.0.16
// 编译：javac *.java
// 运行：java Main
// 验证状态：已验证：OpenJDK 17.0.16
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

class StudentRegistry {
    private final Map<String, Student> students = new HashMap<>();

    boolean register(Student student) {
        if (students.containsKey(student.getId())) {
            System.out.println("拒绝注册：id 已存在 " + student.getId());
            return false;
        }
        students.put(student.getId(), student);
        return true;
    }

    Optional<Student> find(String id) {
        return Optional.ofNullable(students.get(id));
    }

    boolean remove(String id) {
        return students.remove(id) != null;
    }

    int size() {
        return students.size();
    }
}
