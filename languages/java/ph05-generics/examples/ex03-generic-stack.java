// examples/ex03-generic-stack.java —— 泛型 Stack：Object[] 规避泛型数组 + pop 强转
// 对应主文档「6. 代码示例 / 示例 3」
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex03-generic-stack.java
// 运行：java GenericStack
// 验证状态：已验证：OpenJDK 17.0.16
class GenericStack {
    static class Stack<T> {
        private Object[] elements = new Object[16];  // 不能 new T[]（类型擦除限制）
        private int size = 0;

        public void push(T item) { elements[size++] = item; }

        @SuppressWarnings("unchecked")
        public T pop() {
            T item = (T) elements[--size];  // 类型擦除后的必要强转
            elements[size] = null;          // 避免内存泄漏：置空出栈槽位
            return item;
        }

        @SuppressWarnings("unchecked")
        public T peek() { return (T) elements[size - 1]; }

        public boolean isEmpty() { return size == 0; }
        public int size() { return size; }
    }

    public static void main(String[] args) {
        Stack<String> stack = new Stack<>();
        stack.push("请求1-登录");
        stack.push("请求2-查询");
        stack.push("请求3-更新");

        System.out.println("栈顶: " + stack.peek());
        while (!stack.isEmpty()) {
            System.out.println("处理: " + stack.pop());
        }
    }
}
