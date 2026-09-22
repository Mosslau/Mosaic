// project/file-copy-tool.java —— 阶段项目：文件复制工具（文件/目录复制 + 进度显示 + 覆盖确认 + 耗时统计）
// 对应 Roadmap「ph07 IO 与文件操作阶段」推荐项目第一个「文件复制工具」
// 用字节流 + 缓冲实现复制逻辑，与 Files.copy 对比耗时与字节数；无参数时运行自测
// 验证环境：OpenJDK 17.0.16
// 编译：javac file-copy-tool.java
// 运行：java FileCopyTool [选项] <源> <目标>   或   java FileCopyTool（自测）
// 验证状态：已验证：OpenJDK 17.0.16
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.stream.*;

class FileCopyTool {
    private static final int BUFFER_SIZE = 8192;   // 与 BufferedInputStream 默认缓冲一致

    // ==================== 命令行入口 ====================
    public static void main(String[] args) throws IOException {
        if (args.length == 0) {
            selfTest();                            // 无参数：跑自测
            return;
        }
        boolean overwrite = false;
        List<String> paths = new ArrayList<>();
        for (String a : args) {
            if (a.equals("-f")) {
                overwrite = true;                  // -f：覆盖已存在的目标
            } else {
                paths.add(a);
            }
        }
        if (paths.size() != 2) {
            System.err.println("用法: java FileCopyTool [-f] <源文件|源目录> <目标>");
            System.exit(1);
        }
        Path src = Paths.get(paths.get(0));
        Path dst = Paths.get(paths.get(1));
        if (!Files.exists(src)) {
            System.err.println("源不存在: " + src);
            System.exit(1);
        }
        long[] stat = copy(src, dst, overwrite);   // [0]=字节数 [1]=文件数
        System.out.printf("完成：复制 %d 个文件，共 %d 字节%n", stat[1], stat[0]);
    }

    // ==================== 复制逻辑 ====================
    // 入口分发：文件走 copyFile，目录走 copyDirectory
    static long[] copy(Path src, Path dst, boolean overwrite) throws IOException {
        if (Files.isDirectory(src)) {
            return copyDirectory(src, dst, overwrite);
        }
        long bytes = copyFile(src, dst, overwrite);
        return new long[]{bytes, 1};
    }

    // 目录复制：walk 收集全部条目，先建目录再逐个复制文件
    static long[] copyDirectory(Path srcDir, Path dstDir, boolean overwrite) throws IOException {
        List<Path> entries;
        try (Stream<Path> walk = Files.walk(srcDir)) {       // 流用完必须关闭
            entries = walk.collect(Collectors.toList());
        }
        long totalBytes = 0;
        long fileCount = 0;
        for (Path entry : entries) {
            Path target = dstDir.resolve(srcDir.relativize(entry).toString());
            if (Files.isDirectory(entry)) {
                Files.createDirectories(target);
            } else {
                Files.createDirectories(target.getParent());
                totalBytes += copyFile(entry, target, overwrite);
                fileCount++;
            }
        }
        return new long[]{totalBytes, fileCount};
    }

    // 文件复制：字节流 + 缓冲，逐块读写并按百分比打印进度
    static long copyFile(Path src, Path dst, boolean overwrite) throws IOException {
        if (Files.exists(dst) && !overwrite) {
            throw new IOException("目标已存在（用 -f 覆盖）: " + dst);
        }
        long total = Files.size(src);
        long copied = 0;
        int lastPercent = -1;
        try (InputStream in = new BufferedInputStream(new FileInputStream(src.toFile()));
             OutputStream out = new BufferedOutputStream(new FileOutputStream(dst.toFile()))) {
            byte[] buf = new byte[BUFFER_SIZE];
            int n;
            while ((n = in.read(buf)) != -1) {
                out.write(buf, 0, n);
                copied += n;
                if (total > 0) {
                    int percent = (int) (copied * 100 / total);
                    if (percent != lastPercent && percent % 10 == 0) {   // 每 10% 打一次
                        System.out.printf("  %s: %d%%%n", src.getFileName(), percent);
                        lastPercent = percent;
                    }
                }
            }
        }
        return copied;
    }

    // ==================== 自测 ====================
    static void selfTest() throws IOException {
        Path dir = Paths.get("copy-test");
        Path src = dir.resolve("src");
        Path dst = dir.resolve("dst");
        deleteTree(dir);
        Files.createDirectories(src.resolve("sub"));

        // 造 3 个文件：文本、含中文、伪二进制（256KB，足够触发多次进度打印）
        Files.write(src.resolve("a.txt"), "hello io".getBytes("UTF-8"));
        Files.write(src.resolve("中文.txt"), "中文内容".getBytes("UTF-8"));
        byte[] big = new byte[256 * 1024];
        new Random(42).nextBytes(big);
        Files.write(src.resolve("sub").resolve("big.bin"), big);

        // 1. 目录复制 + 进度 + 字节数核对
        long t0 = System.nanoTime();
        long[] stat = copy(src, dst, false);
        long t1 = System.nanoTime();
        assertTrue(stat[1] == 3, "文件数应为 3，实际 " + stat[1]);
        assertTrue(Files.readAllBytes(dst.resolve("sub").resolve("big.bin")).length == big.length,
                "big.bin 大小不一致");
        assertTrue(Files.readString(dst.resolve("中文.txt")).equals("中文内容"),
                "中文文件内容不一致");

        // 2. Files.copy 对比耗时（同一源复制到 dst2）
        Path dst2 = dir.resolve("dst2");
        long t2 = System.nanoTime();
        Files.createDirectories(dst2.resolve("sub"));
        Files.copy(src.resolve("a.txt"), dst2.resolve("a.txt"));
        Files.copy(src.resolve("中文.txt"), dst2.resolve("中文.txt"));
        Files.copy(src.resolve("sub").resolve("big.bin"), dst2.resolve("sub").resolve("big.bin"));
        long t3 = System.nanoTime();
        System.out.printf("字节流+缓冲: %.2f ms / Files.copy: %.2f ms（%d 字节）%n",
                (t1 - t0) / 1e6, (t3 - t2) / 1e6, stat[0]);

        // 3. 覆盖确认：不加 -f 必须抛异常，加 -f 成功
        boolean rejected = false;
        try {
            copy(src.resolve("a.txt"), dst.resolve("a.txt"), false);
        } catch (IOException e) {
            rejected = true;
            System.out.println("覆盖确认生效: " + e.getMessage());
        }
        assertTrue(rejected, "目标已存在且未指定 -f 时必须拒绝");
        copy(src.resolve("a.txt"), dst.resolve("a.txt"), true);

        deleteTree(dir);
        System.out.println("全部自测通过");
    }

    static void deleteTree(Path root) throws IOException {
        if (!Files.exists(root)) {
            return;
        }
        try (Stream<Path> walk = Files.walk(root)) {
            walk.sorted(Comparator.reverseOrder())
                .forEach(p -> {
                    try { Files.deleteIfExists(p); } catch (IOException ignored) { }
                });
        }
    }

    // 自测断言：失败即抛 AssertionError，不静默
    static void assertTrue(boolean cond, String msg) {
        if (!cond) {
            throw new AssertionError(msg);
        }
    }
}
