// examples/ex02-generic-pair.java —— 泛型 Pair：双类型参数 + 泛型方法 swapValues
// 对应主文档「6. 代码示例 / 示例 2」
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex02-generic-pair.java
// 运行：java GenericPair
// 验证状态：已验证：OpenJDK 17.0.16
class GenericPair {
    static class Pair<K, V> {
        private K key;
        private V value;

        public Pair(K key, V value) { this.key = key; this.value = value; }
        public K getKey() { return key; }
        public V getValue() { return value; }
        public void setValue(V value) { this.value = value; }

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
        Pair<String, Integer> score = new Pair<>("Alice", 90);
        System.out.println("成绩: " + score);

        Pair<String, String> a = new Pair<>("A", "apple");
        Pair<String, String> b = new Pair<>("B", "banana");
        swapValues(a, b);
        System.out.println("交换后: a=" + a + ", b=" + b);
    }
}
