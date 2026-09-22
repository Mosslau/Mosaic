// examples/ex03-set-dedup.java —— Set 去重：LinkedHashSet 保插入序 / TreeSet 自然排序 / HashSet 批量交集
// 对应主文档「6. 代码示例 / 示例 3」
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex03-set-dedup.java
// 运行：java SetDedup
// 已验证：本环境编译零错误，运行输出符合注释中的期望值
import java.util.*;

class SetDedup {
    public static void main(String[] args) {
        List<Integer> numbers = Arrays.asList(3, 1, 4, 1, 5, 9, 2, 6, 5, 3);

        // LinkedHashSet 去重并保持插入顺序
        Set<Integer> unique = new LinkedHashSet<>(numbers);
        System.out.println("去重(保持顺序): " + unique);   // [3, 1, 4, 5, 9, 2, 6]

        // TreeSet 去重并自然排序
        Set<Integer> sorted = new TreeSet<>(numbers);
        System.out.println("去重(自然排序): " + sorted);    // [1, 2, 3, 4, 5, 6, 9]

        // HashSet 批量操作：交集（retainAll 保留两集合共有的元素）
        Set<Integer> other = new HashSet<>(Arrays.asList(1, 2, 3, 10, 11));
        unique.retainAll(other);
        System.out.println("与 {1,2,3,10,11} 的交集: " + unique);   // [3, 1, 2]（保插入序）
    }
}
