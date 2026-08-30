// exercises/sol-03-generic-stack.java —— 练习 3 泛型 Stack 参考实现
// 在示例基础上实现容量自动增长（Object[] 满时翻倍）+ 有界泛型方法 sum(Stack<? extends Number>)
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-03-generic-stack.java
// 运行：java GenericStackSol
// 验证状态：已验证：OpenJDK 17.0.16
class GenericStackSol {
    static class Stack<T> {
        private Object[] elements;   // 不能 new T[]（类型擦除限制），用 Object[] + 强转
        private int size = 0;

        public Stack() { this(16); }

        public Stack(int capacity) {
            if (capacity <= 0) throw new IllegalArgumentException("容量必须 > 0");
            elements = new Object[capacity];
        }

        public void push(T item) {
            if (size == elements.length) grow();   // 满则扩容
            elements[size++] = item;
        }

        private void grow() {
            Object[] bigger = new Object[elements.length * 2];
            System.arraycopy(elements, 0, bigger, 0, size);
            elements = bigger;
        }

        @SuppressWarnings("unchecked")
        public T pop() {
            if (size == 0) throw new IllegalStateException("空栈不能 pop");
            T item = (T) elements[--size];   // 类型擦除后的必要强转
            elements[size] = null;           // 置空出栈槽位，避免内存泄漏
            return item;
        }

        @SuppressWarnings("unchecked")
        public T peek() {
            if (size == 0) throw new IllegalStateException("空栈不能 peek");
            return (T) elements[size - 1];
        }

        public boolean isEmpty() { return size == 0; }
        public int size() { return size; }
    }

    // 有界泛型方法：T 必须是 Number 子类，才能调用 doubleValue()
    static <T extends Number> double sum(Stack<T> stack) {
        double total = 0.0;
        while (!stack.isEmpty()) total += stack.pop().doubleValue();
        return total;
    }

    public static void main(String[] args) {
        // 基本 LIFO
        Stack<String> stack = new Stack<>();
        stack.push("请求1-登录");
        stack.push("请求2-查询");
        stack.push("请求3-更新");
        System.out.println("栈顶: " + stack.peek());
        StringBuilder popped = new StringBuilder();
        while (!stack.isEmpty()) popped.append(stack.pop()).append(" ");
        System.out.println("出栈顺序: " + popped.toString().trim());
        System.out.println("清空后 size: " + stack.size());

        // 扩容验证：初始容量 2，压入 5 个不失败
        Stack<Integer> growable = new Stack<>(2);
        for (int i = 1; i <= 5; i++) growable.push(i * 10);
        System.out.println("扩容后 size: " + growable.size() + "，peek: " + growable.peek());

        // 有界泛型方法：Stack<Integer> 传入 sum
        Stack<Integer> nums = new Stack<>();
        for (int i = 1; i <= 4; i++) nums.push(i);
        System.out.println("sum(1..4): " + sum(nums));
    }
}
