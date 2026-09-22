// examples/ex04-batch-rename.java —— 批量重命名：Files.walk 遍历目录树，把所有 .log 改名为 .txt
// 对应主文档「6. 代码示例 / 示例 4」
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex04-batch-rename.java
// 运行：java BatchRename
// 验证状态：已验证：OpenJDK 17.0.16
import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.stream.*;

class BatchRename {
    public static void main(String[] args) throws IOException {
        // 准备测试目录树
        Path root = Paths.get("logs");
        Files.createDirectories(root);
        Files.write(root.resolve("a.log"), "a".getBytes());
        Files.write(root.resolve("b.log"), "b".getBytes());
        Files.createDirectories(root.resolve("sub"));
        Files.write(root.resolve("sub").resolve("c.log"), "c".getBytes());
        // 遍历整棵目录树，重命名所有 .log（renameToTxt 会打印结果）
        try (Stream<Path> paths = Files.walk(root)) {     // 流用完必须关闭
            paths.filter(Files::isRegularFile)
                 .filter(p -> p.toString().endsWith(".log"))
                 .forEach(BatchRename::renameToTxt);
        }
        deleteTree(root);
    }

    static void renameToTxt(Path p) {
        try {
            String name = p.getFileName().toString();
            Path target = p.resolveSibling(
                    name.substring(0, name.length() - 4) + ".txt");
            Files.move(p, target, StandardCopyOption.REPLACE_EXISTING);
            System.out.println(p + " -> " + target);
        } catch (IOException e) {
            System.err.println("重命名失败: " + p + " (" + e.getMessage() + ")");
        }
    }

    // 自底向上删除目录树：先删子节点，再删目录本身
    static void deleteTree(Path root) throws IOException {
        try (Stream<Path> paths = Files.walk(root)) {
            paths.sorted(Comparator.reverseOrder())
                 .forEach(p -> {
                     try { Files.deleteIfExists(p); } catch (IOException ignored) { }
                 });
        }
    }
}
