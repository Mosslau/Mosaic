// examples/ex03-csv-parser.java —— CSV 解析：Scanner 按行 + split，简单处理引号字段并计算平均分
// 对应主文档「6. 代码示例 / 示例 3」
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex03-csv-parser.java
// 运行：java CsvParser
// 验证状态：已验证：OpenJDK 17.0.16
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

class CsvParser {
    public static void main(String[] args) throws IOException {
        // 样例数据：引号仅作装饰（字段内不含逗号）
        Files.write(Paths.get("scores.csv"),
                Arrays.asList(
                        "name,class,score",
                        "\"Alice\",一班,90",
                        "Bob,一班,85",
                        "Cary,二班,78"),
                StandardCharsets.UTF_8);
        List<String[]> rows = new ArrayList<>();
        try (Scanner scanner = new Scanner(new File("scores.csv"), "UTF-8")) {
            while (scanner.hasNextLine()) {
                rows.add(parseLine(scanner.nextLine()));
            }
        }
        int total = 0;
        for (int i = 1; i < rows.size(); i++) {          // 跳过表头
            total += Integer.parseInt(rows.get(i)[2]);
        }
        System.out.println("平均分: " + (total / (rows.size() - 1)));

        for (String[] row : rows) {
            System.out.println(Arrays.toString(row));
        }
        Files.deleteIfExists(Paths.get("scores.csv"));
    }

    // 简单引号处理：切分后去除字段首尾引号；
    // 字段内含逗号（如 "Doe, John"）时 split 会拆错，需 OpenCSV 等专业库
    static String[] parseLine(String line) {
        String[] fields = line.split(",");
        for (int i = 0; i < fields.length; i++) {
            fields[i] = fields[i].trim().replace("\"", "");
        }
        return fields;
    }
}
