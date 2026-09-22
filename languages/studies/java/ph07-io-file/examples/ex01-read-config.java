// examples/ex01-read-config.java —— 读取配置文件：Files.readAllLines + 手写 key=value 解析（忽略空行与 # 注释）
// 对应主文档「6. 代码示例 / 示例 1」
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex01-read-config.java
// 运行：java ReadConfig
// 验证状态：已验证：OpenJDK 17.0.16
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

class ReadConfig {
    public static Map<String, String> load(String path) throws IOException {
        Map<String, String> config = new HashMap<>();
        for (String line : Files.readAllLines(Paths.get(path), StandardCharsets.UTF_8)) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) {
                continue;                        // 跳过空行和注释
            }
            int idx = line.indexOf('=');
            if (idx > 0) {
                config.put(line.substring(0, idx).trim(),
                        line.substring(idx + 1).trim());
            }
        }
        return config;
    }

    public static void main(String[] args) throws IOException {
        Files.write(Paths.get("app.properties"),
                Arrays.asList(
                        "# 数据库配置",
                        "db.url=jdbc:mysql://localhost:3306/app",
                        "timeout=30"),
                StandardCharsets.UTF_8);
        Map<String, String> config = load("app.properties");
        System.out.println("timeout = " + config.get("timeout"));
        System.out.println("db.url  = " + config.get("db.url"));
        Files.deleteIfExists(Paths.get("app.properties"));
    }
}
