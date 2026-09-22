// examples/ex01-student-manager.java —— List 管理学生：增删改查、排序、遍历中安全删除（removeIf）
// 对应主文档「6. 代码示例 / 示例 1」
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex01-student-manager.java
// 运行：java StudentManager
// 已验证：本环境编译零错误，运行输出符合注释中的期望值
import java.util.*;

class StudentManager {
    public static void main(String[] args) {
        List<String> students = new ArrayList<>();
        students.add("Alice");
        students.add("Bob");
        students.add("Charlie");

        System.out.println("学生列表: " + students);          // [Alice, Bob, Charlie]
        System.out.println("总人数: " + students.size());     // 3
        System.out.println("第一位: " + students.get(0));     // Alice

        // 删除指定元素
        students.remove("Bob");
        System.out.println("删除 Bob 后: " + students);       // [Alice, Charlie]

        // 排序
        students.sort(Comparator.naturalOrder());
        System.out.println("按字母排序后:");
        for (String s : students) {
            System.out.println("  - " + s);                   // - Alice / - Charlie
        }

        // 安全删除：removeIf — 遍历中修改不会抛 ConcurrentModificationException
        students.add("Alex");
        students.removeIf(s -> s.startsWith("A"));
        System.out.println("删除 A 开头后: " + students);      // [Charlie]
    }
}
