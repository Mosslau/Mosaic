// examples/ex02-word-freq.java —— Map 统计词频：HashMap + getOrDefault，找最高频词
// 对应主文档「6. 代码示例 / 示例 2」
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex02-word-freq.java
// 运行：java WordFreq
// 已验证：本环境编译零错误，运行输出符合注释中的期望值（词频表顺序不保证）
import java.util.*;

class WordFreq {
    public static void main(String[] args) {
        String text = "the quick brown fox jumps over the lazy dog the fox";
        String[] words = text.split(" ");

        // getOrDefault：不存在时返回 0，加 1 后写回——统计惯用法
        Map<String, Integer> freq = new HashMap<>();
        for (String word : words) {
            freq.put(word, freq.getOrDefault(word, 0) + 1);
        }

        System.out.println("词频统计:");   // HashMap 不保证顺序，输出顺序可能变化
        for (Map.Entry<String, Integer> entry : freq.entrySet()) {
            System.out.printf("  %-8s : %d%n", entry.getKey(), entry.getValue());
        }

        // 找最高频词：Collections.max 取 entrySet 中 value 最大的那条
        String topWord = Collections.max(freq.entrySet(),
                Map.Entry.comparingByValue()).getKey();
        System.out.println("最高频词: " + topWord);   // the（出现 3 次）
    }
}
