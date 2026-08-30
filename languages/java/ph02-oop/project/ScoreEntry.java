// 来源：languages/java/ph02-oop/project/README.md
// 说明：成绩快照 record——subject + score，不可变，自动生成构造/访问器/equals/hashCode/toString
// 验证环境：OpenJDK 17.0.16
// 编译：javac *.java
// 运行：java Main
// 验证状态：已验证：OpenJDK 17.0.16
record ScoreEntry(String subject, double score) {
    ScoreEntry {
        if (score < 0 || score > 100) {
            throw new IllegalArgumentException("分数必须在 0-100 之间: " + score);
        }
    }
}
