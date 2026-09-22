// examples/ex02-file-read-demo.java —— 文件读取异常：finally 手动关闭 vs try-with-resources
// 对应主文档「6. 代码示例 / 示例 2」；运行生成 demo.txt 并自动删除
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex02-file-read-demo.java
// 运行：java FileReadDemo
// 验证状态：已验证：OpenJDK 17.0.16
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;

class FileReadDemo {
    // 方式一：try/catch/finally 手动关闭资源
    public static String readWithFinally(String path) {
        FileReader reader = null;
        try {
            reader = new FileReader(path);
            StringBuilder sb = new StringBuilder();
            int ch;
            while ((ch = reader.read()) != -1) {
                sb.append((char) ch);
            }
            return sb.toString();
        } catch (FileNotFoundException e) {
            System.out.println("文件不存在: " + path);
            return null;
        } catch (IOException e) {
            System.out.println("读取失败: " + e.getMessage());
            return null;
        } finally {
            if (reader != null) {
                try {
                    reader.close();
                } catch (IOException e) {
                    System.out.println("关闭资源失败: " + e.getMessage());
                }
            }
        }
    }

    // 方式二：try-with-resources 自动关闭（推荐）
    public static String readWithTryWithResources(String path) {
        try (FileReader reader = new FileReader(path)) {
            StringBuilder sb = new StringBuilder();
            int ch;
            while ((ch = reader.read()) != -1) {
                sb.append((char) ch);
            }
            return sb.toString();
        } catch (IOException e) {
            System.out.println("读取失败: " + e.getMessage());
            return null;
        }
    }

    public static void main(String[] args) throws IOException {
        try (FileWriter writer = new FileWriter("demo.txt")) {
            writer.write("Hello Exception Stage");
        }
        System.out.println("finally 版: " + readWithFinally("demo.txt"));
        System.out.println("twr 版:     " + readWithTryWithResources("demo.txt"));
        System.out.println("不存在:     " + readWithTryWithResources("no-such-file.txt"));
        new File("demo.txt").delete();
    }
}
