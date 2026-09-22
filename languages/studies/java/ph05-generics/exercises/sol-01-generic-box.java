// exercises/sol-01-generic-box.java —— 练习 1 泛型 Box 参考实现
// 在示例基础上新增 clear() 与 getOrElse()，并验证编译期类型安全 + 运行时 Class 相同
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-01-generic-box.java
// 运行：java GenericBoxSol
// 验证状态：已验证：OpenJDK 17.0.16
class GenericBoxSol {
    static class Box<T> {
        private T value;

        public void set(T value) { this.value = value; }
        public T get() { return value; }
        public boolean isEmpty() { return value == null; }

        // 清空：值置 null，isEmpty() 变 true
        public void clear() { value = null; }

        // 空盒时返回兜底值，非空时返回真实值——Optional.orElse 的泛型版
        public T getOrElse(T fallback) {
            return value == null ? fallback : value;
        }
    }

    public static void main(String[] args) {
        Box<String> strBox = new Box<>();
        strBox.set("Hello Generics");
        System.out.println("strBox: " + strBox.get());

        Box<Integer> intBox = new Box<>();
        intBox.set(42);
        System.out.println("intBox: " + intBox.get());

        // 编译期类型安全：编译器阻止 Box<String> 装入 Integer
        // strBox.set(42);  // 取消注释会编译错误: incompatible types

        // 空盒行为：clear 后 isEmpty 为 true，getOrElse 返回兜底值
        strBox.clear();
        System.out.println("clear 后 isEmpty: " + strBox.isEmpty());
        System.out.println("getOrElse 兜底: " + strBox.getOrElse("空盒"));

        // 运行时类型擦除：两个参数化类型是同一个 Class
        System.out.println("运行时 Class 相同: " +
                (strBox.getClass() == intBox.getClass()));
    }
}
