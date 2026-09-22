// examples/ex05-pecs-demo.java —— PECS 演示：? extends 只读 + ? super 只写 + copyAll 组合
// 对应主文档「6. 代码示例 / 示例 5」
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex05-pecs-demo.java
// 运行：java PecsDemo
// 验证状态：已验证：OpenJDK 17.0.16
import java.util.*;

class PecsDemo {
    // Producer Extends: src 只读（生产者）——读出来的至少是 Number，可安全消费
    static double sumOfList(List<? extends Number> list) {
        double sum = 0.0;
        for (Number n : list) sum += n.doubleValue();
        return sum;
    }

    // Consumer Super: dest 只写（消费者）——容器接受 Integer 或其父类，写入安全
    static void addNumbers(List<? super Integer> list) {
        for (int i = 1; i <= 3; i++) list.add(i);
    }

    // PECS 组合：src 是生产者(extends)，dest 是消费者(super)
    static <T> void copyAll(List<? extends T> src, List<? super T> dest) {
        for (T item : src) dest.add(item);
    }

    public static void main(String[] args) {
        // ? extends T：可接收多种子类型
        System.out.println("sum(ints): " + sumOfList(Arrays.asList(1, 2, 3)));
        System.out.println("sum(doubles): " + sumOfList(Arrays.asList(1.5, 2.5, 3.5)));

        // ? super T：可写入多种父类容器
        List<Number> numbers = new ArrayList<>();
        addNumbers(numbers);
        System.out.println("addNumbers: " + numbers);

        // PECS 组合：List<Integer> 拷入 List<Number>
        List<Integer> src = Arrays.asList(10, 20, 30);
        List<Number> dest = new ArrayList<>();
        copyAll(src, dest);
        System.out.println("copyAll: " + dest);
    }
}
