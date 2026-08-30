// exercises/sol-04-batch-rename.java —— 练习 4 参考实现：批量重命名（Files.walk + 加前缀 + 改扩展名 + 容错计数）
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-04-batch-rename.java
// 运行：java BatchRenameSol
// 验证状态：已验证：OpenJDK 17.0.16
import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.stream.*;

class BatchRenameSol {
    public static void main(String[] args) throws IOException {
        // 自造测试目录树：子目录 + 非 .log 文件
        Path root = Paths.get("logs");
        Files.createDirectories(root.resolve("sub"));
        Files.write(root.resolve("a.log"), "a".getBytes());
        Files.write(root.resolve("keep.md"), "k".getBytes());      // 不受影响
        Files.write(root.resolve("sub").resolve("c.log"), "c".getBytes());

        // 先收集目标列表再执行：避免在遍历流上边遍历边修改同一目录
        List<Path> targets;
        try (Stream<Path> paths = Files.walk(root)) {              // 流必须关闭
            targets = paths.filter(Files::isRegularFile)
                           .filter(p -> p.toString().endsWith(".log"))
                           .collect(Collectors.toList());
        }

        int ok = 0;
        int fail = 0;
        for (Path p : targets) {
            String name = p.getFileName().toString();
            String newName = "backup-" + name.substring(0, name.length() - 4) + ".txt";
            try {
                Files.move(p, p.resolveSibling(newName), StandardCopyOption.REPLACE_EXISTING);
                System.out.println(p + " -> " + newName);
                ok++;
            } catch (IOException e) {
                System.err.println("重命名失败: " + p + " (" + e.getMessage() + ")");
                fail++;
            }
        }
        System.out.println("成功 " + ok + " 个，失败 " + fail + " 个");

        // 清理整棵目录树
        try (Stream<Path> paths = Files.walk(root)) {
            paths.sorted(Comparator.reverseOrder())
                 .forEach(p -> {
                     try { Files.deleteIfExists(p); } catch (IOException ignored) { }
                 });
        }
    }
}
