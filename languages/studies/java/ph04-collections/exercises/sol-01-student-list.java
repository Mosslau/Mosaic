// exercises/sol-01-student-list.java —— 练习 1 List 管理学生参考实现
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-01-student-list.java
// 运行：java StudentList
// 验证状态：已验证：OpenJDK 17.0.16
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

class StudentList {
    public static void main(String[] args) {
        // List.of 返回不可变列表，包一层 ArrayList 才能 add/remove
        List<String> students = new ArrayList<>(List.of("Alice", "Bob", "Charlie", "David"));

        students.add("Eve");
        System.out.println("添加 Eve 后: " + students);          // [Alice, Bob, Charlie, David, Eve]

        students.remove("Bob");
        System.out.println("移除 Bob 后: " + students);          // [Alice, Charlie, David, Eve]

        System.out.println("David 的位置: " + students.indexOf("David"));  // 2

        students.sort(Comparator.naturalOrder());
        System.out.println("排序后: " + students);               // [Alice, Charlie, David, Eve]

        // 遍历中安全删除：removeIf（for-each 里直接 remove 会抛 ConcurrentModificationException）
        students.removeIf(s -> s.startsWith("C"));
        System.out.println("删除 C 开头后: " + students);        // [Alice, David, Eve]
    }
}
