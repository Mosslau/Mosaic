// examples/ex01-generic-box.java —— 泛型 Box：单类型参数 + 运行时 Class 相同验证
// 对应主文档「6. 代码示例 / 示例 1」
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex01-generic-box.java
// 运行：java GenericBox
// 验证状态：已验证：OpenJDK 17.0.16
class GenericBox {
    static class Box<T> {
        private T value;

        public void set(T value) { this.value = value; }
        public T get() { return value; }
        public boolean isEmpty() { return value == null; }
    }

    public static void main(String[] args) {
        Box<String> strBox = new Box<>();
        strBox.set("Hello Generics");
        System.out.println("strBox: " + strBox.get());

        Box<Integer> intBox = new Box<>();
        intBox.set(42);
        System.out.println("intBox: " + intBox.get());

        // Box<String> 和 Box<Integer> 运行时是同一个 Class（类型擦除的结果）
        System.out.println("运行时 Class 相同: " +
                (strBox.getClass() == intBox.getClass()));
    }
}
