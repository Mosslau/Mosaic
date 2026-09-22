// examples/ex04-inverted-index-demo/ex04-inverted-index-demo.java
// 手写倒排索引演示（对应主文档 3.8/3.9/4.3）：分词 -> 建倒排表 -> term 查询 / AND / OR / 相关性计数
// 教学映射：word -> 文档 id 集合 就是 ES 的 term dictionary + postings；「查表 + 集合并交」就是
//           为什么倒排检索不用扫全表；score 用词频计数近似 ES 的 _score（真实打分是 TF-IDF/BM25）。
// 刻意保留的缺口：简易分词按「非字母数字」切，切不了中文（对照主文档 3.8 中文分词注）——
//   这是教学性覆盖：为聚焦倒排结构本身省略了中文分词器（ik 等属生产插件）。
// 验证环境：OpenJDK 17（javac -version -> 17.x）；无第三方依赖
// 验证命令：
//   # 1. 编译（文件在 examples/ex04-inverted-index-demo/ 目录下执行）
//   javac ex04-inverted-index-demo.java
//   # 2. 运行
//   java InvertedIndexDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：javac 编译通过、运行全部 PASS）

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.SortedMap;
import java.util.TreeMap;
import java.util.TreeSet;

/** 手写倒排索引演示：词项 -> 文档 id 集合 */
final class InvertedIndexDemo {

    /** 文档：id + 全文 */
    record Doc(int id, String text) {
    }

    /** 简易倒排索引（教学最小版，省略了 ES 的 FST 词典压缩与删除标记等） */
    static final class InvertedIndex {
        /** term -> 按文档 id 有序的集合（TreeSet 让 AND/OR 合并天然有序，对应 postings 按 docId 升序） */
        private final SortedMap<String, Set<Integer>> postings = new TreeMap<>();
        /** term -> 文档内出现次数（用于「哪个词最能代表这篇文档」的相关性示意） */
        private final Map<String, Map<Integer, Integer>> termFreq = new HashMap<>();

        /** 简易分词：小写 + 按非字母数字切分（对应 ES standard 分析器的小写化 + tokenizer，但只限拉丁字符） */
        static List<String> tokenize(String text) {
            List<String> terms = new ArrayList<>();
            for (String token : text.toLowerCase(Locale.ROOT).split("[^a-z0-9]+")) {
                if (!token.isEmpty()) {
                    terms.add(token);
                }
            }
            return terms;
        }

        void add(Doc doc) {
            for (String term : tokenize(doc.text())) {
                postings.computeIfAbsent(term, k -> new TreeSet<>()).add(doc.id());
                termFreq.computeIfAbsent(term, k -> new HashMap<>())
                        .merge(doc.id(), 1, Integer::sum);
            }
        }

        /** term 查询（对应 ES term 查询：不分词，直接查词项表；查不到 = 空） */
        Set<Integer> searchTerm(String term) {
            return postings.getOrDefault(term.toLowerCase(Locale.ROOT), Set.of());
        }

        /** OR（should）：任意词命中即可，返回按 docId 有序的并集 */
        Set<Integer> searchAny(String... terms) {
            Set<Integer> result = new TreeSet<>();
            for (String term : terms) {
                result.addAll(searchTerm(term));
            }
            return result;
        }

        /** AND（must）：所有词都命中，postings 有序 -> 归并求交 */
        Set<Integer> searchAll(String... terms) {
            Set<Integer> result = null;
            for (String term : terms) {
                Set<Integer> hit = searchTerm(term);
                if (hit.isEmpty()) {
                    return Set.of();
                }
                result = (result == null) ? new TreeSet<>(hit) : intersect(result, hit);
            }
            return result == null ? Set.of() : result;
        }

        private static Set<Integer> intersect(Set<Integer> a, Set<Integer> b) {
            // 两个有序集合归并求交：单次线性扫描，是倒排检索「快」的来源之一
            Set<Integer> result = new TreeSet<>();
            for (int id : a) {
                if (b.contains(id)) {
                    result.add(id);
                }
            }
            return result;
        }

        /** 按命中词数排序的相关性示意（多个词同时命中排前面；真实 ES 用 BM25 打分） */
        List<Integer> ranked(List<String> queryTerms) {
            Map<Integer, Integer> score = new HashMap<>();
            for (String term : queryTerms) {
                for (int id : searchTerm(term)) {
                    score.merge(id, termFreq.get(term).getOrDefault(id, 0), Integer::sum);
                }
            }
            return score.entrySet().stream()
                    .sorted(Map.Entry.<Integer, Integer>comparingByValue().reversed())
                    .map(Map.Entry::getKey)
                    .toList();
        }
    }

    static void check(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError("自检失败: " + label);
        }
        System.out.println("PASS  " + label);
    }

    public static void main(String[] args) {
        InvertedIndex index = new InvertedIndex();
        index.add(new Doc(1, "Kafka consumer timeout retry"));
        index.add(new Doc(2, "Elasticsearch inverted index search"));
        index.add(new Doc(3, "Kafka broker ISR leader election"));
        index.add(new Doc(4, "search index in Elasticsearch"));
        index.add(new Doc(5, "consumer group rebalance timeout"));

        check(index.searchTerm("kafka").equals(Set.of(1, 3)), "term=kafka 命中 doc 1、3（词项表直接查，没扫全表）");
        check(index.searchTerm("KAFKA").equals(Set.of(1, 3)), "大小写不敏感：KAFKA 与 kafka 同词项（小写化 token filter）");
        check(index.searchTerm("nonexistent").isEmpty(), "不存在的词返回空集");

        check(index.searchAll("kafka", "broker").equals(Set.of(3)), "AND: kafka AND broker 只命中 doc 3");
        check(index.searchAll("kafka", "search").isEmpty(), "AND: kafka AND search 无交集 -> 空");
        check(index.searchAny("kafka", "search").equals(Set.of(1, 2, 3, 4)), "OR: kafka OR search 命中 1,2,3,4");

        // 对比「正排扫描」：findByContains 每篇文档逐字扫 —— 文档多了就是 O(全库)；倒排是 O(词项查表)
        List<Doc> all = List.of(
                new Doc(1, "Kafka consumer timeout retry"),
                new Doc(2, "Elasticsearch inverted index search"),
                new Doc(3, "Kafka broker ISR leader election"),
                new Doc(4, "search index in Elasticsearch"),
                new Doc(5, "consumer group rebalance timeout"));
        long matched = all.stream()
                .filter(d -> d.text().toLowerCase(Locale.ROOT).contains("kafka"))
                .count();
        check(matched == 2, "正排 contains 也能找到，但要逐篇扫全文；词项多了就退化成全表扫描（主文档 3.10 的 LIKE 对比）");

        check(index.ranked(List.of("kafka", "consumer", "timeout")).equals(List.of(1, 5, 3)),
                "相关性示意：doc 1 三词全中排最前；doc 5 命中 2 词；doc 3 命中 1 词");

        System.out.println();
        System.out.println("全部自检通过。对照主文档 3.8/4.3：");
        System.out.println("  - ES 的倒排表还有：FST 压缩词项字典、文档删除标记（segment 合并时才物理删）、BM25 打分");
        System.out.println("  - 本文件的 tokenize 切不了中文 —— 生产中文检索要装 ik 分词插件（主文档 3.8 注）");
    }
}
