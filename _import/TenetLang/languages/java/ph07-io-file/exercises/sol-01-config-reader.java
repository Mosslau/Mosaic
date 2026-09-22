// exercises/sol-01-config-reader.java —— 练习 1 参考实现：读取配置文件（key=value 解析 + 默认值 + 类型转换）
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-01-config-reader.java
// 运行：java ConfigReaderSol
// 验证状态：已验证：OpenJDK 17.0.16
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

class ConfigReaderSol {
    // 解析 key=value：跳过空行与 # 注释，按第一个 = 切分，两端去空白
    static Map<String, String> loadConfig(String path) throws IOException {
        Map<String, String> config = new LinkedHashMap<>();
        for (String line : Files.readAllLines(Paths.get(path), StandardCharsets.UTF_8)) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) {
                continue;
            }
            int idx = line.indexOf('=');
            if (idx > 0) {
                config.put(line.substring(0, idx).trim(), line.substring(idx + 1).trim());
            }
        }
        return config;
    }

    static String get(Map<String, String> config, String key, String defaultValue) {
        return config.getOrDefault(key, defaultValue);
    }

    // 类型转换失败抛 IllegalArgumentException，消息带 key 名方便定位
    static int getInt(Map<String, String> config, String key, int defaultValue) {
        String v = config.get(key);
        if (v == null) {
            return defaultValue;
        }
        try {
            return Integer.parseInt(v);
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("配置项 " + key + " 不是合法整数: " + v, e);
        }
    }

    public static void main(String[] args) throws IOException {
        Path p = Paths.get("test.properties");
        Files.write(p, Arrays.asList(
                "# 应用配置",
                "",
                "timeout= 30 ",
                "db.url=jdbc:mysql://localhost:3306/app",
                "bad.number=abc"), StandardCharsets.UTF_8);

        Map<String, String> config = loadConfig(p.toString());
        System.out.println("size = " + config.size());                       // 3
        System.out.println("timeout = " + getInt(config, "timeout", 10));    // 30
        System.out.println("missing = " + get(config, "missing", "default"));// default

        try {
            getInt(config, "bad.number", 0);
        } catch (IllegalArgumentException e) {
            System.out.println("捕获: " + e.getMessage());
        }
        Files.deleteIfExists(p);
    }
}
