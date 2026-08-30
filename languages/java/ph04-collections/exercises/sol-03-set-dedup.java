// exercises/sol-03-set-dedup.java —— 练习 3 Set 去重参考实现
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-03-set-dedup.java
// 运行：java SetDedup
// 验证状态：已验证：OpenJDK 17.0.16
import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;

class SetDedup {
    public static void main(String[] args) {
        List<Integer> numbers = Arrays.asList(5, 3, 1, 5, 2, 3, 4, 1);

        // LinkedHashSet：去重并保持首次出现顺序
        Set<Integer> inserted = new LinkedHashSet<>(numbers);
        System.out.println("去重(保持插入序): " + inserted);     // [5, 3, 1, 2, 4]

        // TreeSet：去重并按自然顺序排序
        Set<Integer> sorted = new TreeSet<>(numbers);
        System.out.println("去重(自然排序): " + sorted);         // [1, 2, 3, 4, 5]

        // HashSet 批量操作：交集（retainAll 就地修改调用者，先拷贝一份）
        Set<Integer> other = new HashSet<>(Set.of(1, 2, 3, 10, 11));
        Set<Integer> copy = new HashSet<>(inserted);
        copy.retainAll(other);
        System.out.println("与 {1,2,3,10,11} 的交集: " + copy);  // [1, 2, 3]
    }
}
