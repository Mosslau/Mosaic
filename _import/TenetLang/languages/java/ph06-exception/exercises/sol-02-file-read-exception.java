// exercises/sol-02-file-read-exception.java —— 练习 2 文件读取异常参考实现
// 在示例 ex02 基础上：try-with-resources 逐行统计行数，区分「文件不存在」与「读取中途失败」
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-02-file-read-exception.java
// 运行：java FileReadExceptionSol
// 验证状态：已验证：OpenJDK 17.0.16
import java.io.BufferedReader;
import java.io.FileNotFoundException;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;

class FileReadExceptionSol {
    // 逐行读取并统计行数：
    // 返回 -1 表示文件不存在（可预期、调用方可直接处理）
    // 返回 -2 表示读取中途失败（文件被截断、IO 错误等）
    // 用 try-with-resources：JVM 自动 close，不需要手动关闭
    public static int countLines(String path) {
        try (BufferedReader reader = new BufferedReader(new FileReader(path))) {
            int lines = 0;
            String line;
            while ((line = reader.readLine()) != null) {
                lines++;
            }
            return lines;
        } catch (FileNotFoundException e) {
            System.out.println("文件不存在: " + path);
            return -1;
        } catch (IOException e) {
            System.out.println("读取中途失败: " + e.getMessage());
            return -2;
        }
        // 为什么 FileNotFoundException 写在 IOException 前面？
        // FileNotFoundException 是 IOException 的子类，catch 按声明顺序匹配第一个；
        // 子类在前，否则子类分支永远不可达（编译错误）。
    }

    public static void main(String[] args) throws IOException {
        // 先用 FileWriter 生成 3 行测试文件（try-with-resources 同样负责关闭）
        try (FileWriter writer = new FileWriter("lines-demo.txt")) {
            writer.write("line 1\nline 2\nline 3\n");
        }

        System.out.println("3 行测试文件行数: " + countLines("lines-demo.txt"));
        System.out.println("不存在文件行数:   " + countLines("no-such-file.txt"));

        // 清理测试文件
        java.io.File f = new java.io.File("lines-demo.txt");
        if (f.exists()) {
            f.delete();
        }
    }
}
