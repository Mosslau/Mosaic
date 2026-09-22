// exercises/sol-02-generic-pair.java —— 练习 2 泛型 Pair 参考实现
// 在示例基础上新增静态工厂 Pair.of()（泛型方法）与不可变 withValue()，验证原 Pair 不被修改
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-02-generic-pair.java
// 运行：java GenericPairSol
// 验证状态：已验证：OpenJDK 17.0.16
class GenericPairSol {
    static class Pair<K, V> {
        private final K key;   // key 不可变
        private V value;

        private Pair(K key, V value) { this.key = key; this.value = value; }

        // 泛型静态工厂方法：编译器从实参推断 K/V，替代 new 的样板代码
        public static <K, V> Pair<K, V> of(K key, V value) {
            return new Pair<>(key, value);
        }

        public K getKey() { return key; }
        public V getValue() { return value; }
        public void setValue(V value) { this.value = value; }

        // 不可变视角：返回一个改过 value 的**新** Pair，原 Pair 保持不变
        public Pair<K, V> withValue(V newValue) {
            return new Pair<>(key, newValue);
        }

        @Override
        public String toString() { return "(" + key + ", " + value + ")"; }
    }

    // 泛型方法：交换两个 Pair 的值（不关心 key 类型，用通配符 ? 表达）
    static <V> void swapValues(Pair<?, V> a, Pair<?, V> b) {
        V temp = a.getValue();
        a.setValue(b.getValue());
        b.setValue(temp);
    }

    public static void main(String[] args) {
        // 用静态工厂创建，不需要写 new Pair<String, Integer>(...)
        Pair<String, Integer> score = Pair.of("Alice", 90);
        System.out.println("成绩: " + score);

        // withValue 返回新 Pair，原对象不变（不可变风格）
        Pair<String, Integer> updated = score.withValue(95);
        System.out.println("withValue 后原对象: " + score);
        System.out.println("withValue 后新对象: " + updated);

        // swapValues 交换两个 String Pair 的值
        Pair<String, String> a = Pair.of("A", "apple");
        Pair<String, String> b = Pair.of("B", "banana");
        swapValues(a, b);
        System.out.println("交换后: a=" + a + ", b=" + b);
    }
}
