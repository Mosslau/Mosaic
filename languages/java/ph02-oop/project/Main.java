// 来源：languages/java/ph02-oop/project/README.md
// 说明：入口——注册 3 名学生、录入成绩、演示重复注册拦截与班级统计
// 验证环境：OpenJDK 17.0.16
// 编译：javac *.java
// 运行：java Main
// 验证状态：已验证：OpenJDK 17.0.16
class Main {
    public static void main(String[] args) {
        StudentRegistry registry = new StudentRegistry();

        Student alice = new Student("S001", "Alice", 20);
        Student bob = new Student("S002", "Bob", 21);
        Student carol = new Student("S003", "Carol", 19);

        registry.register(alice);
        registry.register(bob);
        registry.register(carol);
        registry.register(new Student("S001", "Alice Clone", 22));  // 重复 id，应被拒绝
        System.out.println("注册表人数: " + registry.size());

        alice.addScore("数学", 92.5);
        alice.addScore("英语", 88.0);
        bob.addScore("数学", 85.0);
        carol.addScore("数学", 78.0);

        try {
            bob.addScore("英语", 120);  // 越界，应抛异常
        } catch (IllegalArgumentException e) {
            System.out.println("校验拦截: " + e.getMessage());
        }

        // 不可变视图：外部 add 应抛 UnsupportedOperationException
        try {
            alice.getScores().add(new ScoreEntry("物理", 100));
        } catch (UnsupportedOperationException e) {
            System.out.println("成绩列表为不可变视图，外部修改被拦截");
        }

        CourseClass cls = new CourseClass("2026 级 1 班");
        cls.enroll(alice);
        cls.enroll(bob);
        cls.enroll(carol);
        cls.printReport();

        registry.find("S002").ifPresent(s ->
                System.out.println("查找 S002: " + s.getName()));
        registry.remove("S003");
        System.out.println("删除 S003 后人数: " + registry.size());
    }
}
