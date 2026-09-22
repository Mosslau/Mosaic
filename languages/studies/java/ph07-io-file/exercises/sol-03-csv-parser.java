// exercises/sol-03-csv-parser.java —— 练习 3 参考实现：CSV 解析（平均分 + 按班级分组 + 非法行容错）
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-03-csv-parser.java
// 运行：java CsvParserSol
// 验证状态：已验证：OpenJDK 17.0.16
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

class CsvParserSol {
    // 去除字段首尾空白与成对引号
    static String clean(String field) {
        field = field.trim();
        if (field.length() >= 2 && field.startsWith("\"") && field.endsWith("\"")) {
            field = field.substring(1, field.length() - 1);
        }
        return field;
    }

    public static void main(String[] args) throws IOException {
        Path p = Paths.get("scores.csv");
        Files.write(p, Arrays.asList(
                "name,class,score",
                "\"Alice\",一班,90",
                "Bob,一班,85",
                "Cary,二班,78",
                "bad-line-without-enough-fields",   // 非法行：字段不足
                "Dave,二班,abc"),                   // 非法行：score 非数字
                StandardCharsets.UTF_8);

        int total = 0;
        int count = 0;
        Map<String, int[]> byClass = new TreeMap<>();   // class -> [总分, 人数]

        try (BufferedReader reader = Files.newBufferedReader(p, StandardCharsets.UTF_8)) {
            String line = reader.readLine();            // 跳过表头
            while ((line = reader.readLine()) != null) {
                String[] fields = line.split(",");
                if (fields.length < 3) {
                    System.out.println("警告：跳过非法行（字段不足）: " + line);
                    continue;
                }
                int score;
                try {
                    score = Integer.parseInt(clean(fields[2]));
                } catch (NumberFormatException e) {
                    System.out.println("警告：跳过非法行（分数非数字）: " + line);
                    continue;
                }
                String clazz = clean(fields[1]);
                total += score;
                count++;
                byClass.computeIfAbsent(clazz, k -> new int[2]);
                byClass.get(clazz)[0] += score;
                byClass.get(clazz)[1]++;
            }
        }

        System.out.printf("全体平均分: %.1f%n", (double) total / count);
        for (Map.Entry<String, int[]> e : byClass.entrySet()) {
            System.out.printf("%s 平均分: %.1f%n", e.getKey(),
                    (double) e.getValue()[0] / e.getValue()[1]);
        }
        Files.deleteIfExists(p);
    }
}
