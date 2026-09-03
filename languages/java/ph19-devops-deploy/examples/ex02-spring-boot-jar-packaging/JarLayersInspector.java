// examples/ex02-spring-boot-jar-packaging/JarLayersInspector.java
// Spring Boot 可执行 jar 结构检查器（对应主文档 3.2 的 jar 内部结构图）
// 教学映射：把「fat jar / 分层 jar」从概念变成可观察的东西——
//   1. 任意 jar 传入，检查是否为 Spring Boot 可执行 jar（看 org/springframework/boot/loader/ 与 MANIFEST Main-Class）
//   2. 列出 BOOT-INF/lib（依赖数）与 BOOT-INF/classes（应用资源数）——「fat」有多 fat 一目了然
//   3. 解析 BOOT-INF/layers.idx 打印分层结构——Dockerfile 按层 COPY 命中缓存的对象（3.3）
// 教学性覆盖：只读不解压（用 ZipFile 直接读 entry）；对非 Boot jar 也能给出「不是可执行 jar」的明确诊断
// 验证环境：OpenJDK 17（javac -version -> 17.x）；无第三方依赖（JDK 自带 java.util.zip）
// 验证命令：
//   # 1. 编译
//   javac JarLayersInspector.java
//   # 2. 检查任意 jar（有 mvn 环境时指向 mvn package 产物）
//   java JarLayersInspector target/myapp.jar
//   # 3. 无 mvn 时手工构造一个「演示分层 jar」再检查（见 README，命令已给出）
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：真实普通 jar 与手工构造的 BOOT-INF/layers.idx 演示 jar 均解析正确）

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.jar.Attributes;
import java.util.jar.JarFile;
import java.util.jar.Manifest;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/** Spring Boot fat jar / 分层 jar 结构检查器 */
final class JarLayersInspector {

    private static final String BOOT_LOADER_PREFIX = "org/springframework/boot/loader/";
    private static final String LAYERS_IDX = "BOOT-INF/layers.idx";
    private static final String LIB_PREFIX = "BOOT-INF/lib/";
    private static final String CLASSES_PREFIX = "BOOT-INF/classes/";

    public static void main(String[] args) throws IOException {
        if (args.length != 1) {
            System.err.println("用法: java JarLayersInspector <app.jar>");
            System.exit(1);
        }
        Path jarPath = Path.of(args[0]);
        if (!Files.isRegularFile(jarPath)) {
            System.err.println("找不到 jar: " + jarPath.toAbsolutePath());
            System.exit(1);
        }
        inspect(jarPath);
    }

    /** 逐项检查一个 jar，输出人可读报告 */
    static void inspect(Path jarPath) throws IOException {
        boolean isBootJar = false;
        int libCount = 0;
        int classesCount = 0;
        String mainClass = "(无 MANIFEST 或未设 Main-Class)";
        try (ZipFile zip = new ZipFile(jarPath.toFile())) {
            List<String> bootLoaderEntries = new ArrayList<>();
            for (ZipEntry e : zip.stream().toList()) {
                String name = e.getName();
                boolean isDir = name.endsWith("/");
                if (name.startsWith(BOOT_LOADER_PREFIX) && !isDir) {
                    bootLoaderEntries.add(name);
                } else if (name.startsWith(LIB_PREFIX) && !isDir) {
                    libCount++;                              // 只数实际 jar 条目，跳过目录 entry
                } else if (name.startsWith(CLASSES_PREFIX) && !isDir) {
                    classesCount++;
                }
            }
            isBootJar = !bootLoaderEntries.isEmpty();

            JarFile jf = new JarFile(jarPath.toFile());
            try {
                Manifest mf = jf.getManifest();
                if (mf != null) {
                    mainClass = mf.getMainAttributes().getValue(Attributes.Name.MAIN_CLASS);
                    if (mainClass == null) {
                        mainClass = "(清单无 Main-Class)";
                    }
                }
            } finally {
                jf.close();
            }

            System.out.println("jar   : " + jarPath.getFileName());
            System.out.println("大小  : " + (Files.size(jarPath) / 1024) + " KB");
            System.out.println("是否 Spring Boot 可执行 jar : " + (isBootJar ? "是 (含 JarLauncher)" : "否 (普通 jar)"));
            System.out.println("MANIFEST Main-Class        : " + mainClass);
            System.out.println("BOOT-INF/lib   依赖条目数   : " + libCount + "   <- fat jar 的「fat」在这");
            System.out.println("BOOT-INF/classes 应用资源数 : " + classesCount);

            ZipEntry layers = zip.getEntry(LAYERS_IDX);
            if (layers != null) {
                System.out.println("BOOT-INF/layers.idx         : 存在 —— 分层 jar，Dockerfile 可按层 COPY（见主文档 3.3）");
                List<String> lines;
                try (var in = zip.getInputStream(layers)) {
                    lines = new String(in.readAllBytes(), StandardCharsets.UTF_8).lines().toList();
                }
                Map<String, Integer> layerStats = parseLayers(lines);
                layerStats.forEach((layer, count) ->
                        System.out.println("    - 层 " + layer + " : " + count + " 个条目"));
            } else {
                System.out.println("BOOT-INF/layers.idx         : 不存在 —— 未开启分层（pom.xml 加 <layers><enabled>true</enabled></layers>）");
            }
        }
    }

    /** 解析 layers.idx：每层以 `- "层名":` 开头，层内条目以 `  - ` 开头（Boot 3.x 格式） */
    static Map<String, Integer> parseLayers(List<String> lines) {
        Map<String, Integer> result = new LinkedHashMap<>();
        String currentLayer = null;
        for (String line : lines) {
            if (line.startsWith("- \"")) {
                currentLayer = line.substring(3, line.lastIndexOf('"'));
                result.putIfAbsent(currentLayer, 0);
            } else if (line.startsWith("  - ") && currentLayer != null) {
                result.compute(currentLayer, (k, v) -> v == null ? 1 : v + 1);
            }
        }
        return result;
    }
}
