// exercises/sol-02-word-count.java —— 练习 2 Map 统计词频参考实现
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-02-word-count.java
// 运行：java WordCount
// 验证状态：已验证：OpenJDK 17.0.16
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

class WordCount {
    public static void main(String[] args) {
        String text = "Apple banana Apple orange banana apple apple";
        String[] words = text.split(" ");

        // 计数：先 toLowerCase 归一化，getOrDefault 累加（避免 containsKey + put 两次查询）
        Map<String, Integer> freq = new HashMap<>();
        for (String word : words) {
            String w = word.toLowerCase();
            freq.put(w, freq.getOrDefault(w, 0) + 1);
        }

        // 输出词频：先按 key 排序，保证打印顺序确定（HashMap 本身不保证顺序）
        List<Map.Entry<String, Integer>> entries = new ArrayList<>(freq.entrySet());
        entries.sort(Comparator.comparing(Map.Entry::getKey));
        for (Map.Entry<String, Integer> e : entries) {
            System.out.println(e.getKey() + " : " + e.getValue());
        }

        // 找最高频词；并列时取字典序最小
        String top = null;
        int max = -1;
        for (Map.Entry<String, Integer> e : freq.entrySet()) {
            int v = e.getValue();
            if (v > max || (v == max && top != null && e.getKey().compareTo(top) < 0)) {
                top = e.getKey();
                max = v;
            }
        }
        System.out.println("最高频词: " + top);                  // apple
    }
}
