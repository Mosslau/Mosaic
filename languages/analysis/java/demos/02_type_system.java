// 02 · 类型系统：基本类型、装箱与泛型擦除演示
// 运行：java demos/02_type_system.java

import java.util.ArrayList;
import java.util.List;

class TypeSystemDemo {
    public static void main(String[] args) {
        System.out.println("== 1. int vs Integer：值语义 vs 引用语义 ==");
        int a = 127, b = 127;          // 基本类型：直接比内容
        Integer x = 127, y = 127;      // 自动装箱：小整数命中 Integer 缓存 [-128,127]
        System.out.println("   a == b         = " + (a == b) + "   （值比较，恒真）");
        System.out.println("   x == y (127)   = " + (x == y) + "   （缓存命中，碰巧相等）");

        Integer p = 200, q = 200;      // 超出缓存范围 → 各自 new 对象
        System.out.println("   p == q (200)   = " + (p == q) + "   （引用比较，翻车！）");
        System.out.println("   p.equals(q)    = " + p.equals(q) + "   （正确写法：equals 比内容）");
        System.out.println("   → 教训：包装类型比较必须用 equals，== 只对基本类型安全");

        System.out.println("\n== 2. 自动拆箱遇 null → NullPointerException ==");
        Integer maybeNull = null;
        try {
            int v = maybeNull;         // 拆箱：null.intValue() → NPE
        } catch (NullPointerException e) {
            System.out.println("   拆箱 null 抛 NPE：" + e.getClass().getSimpleName());
        }

        System.out.println("\n== 3. 泛型擦除：运行时不知道类型参数 ==");
        List<String> names = new ArrayList<>();
        List<Integer> scores = new ArrayList<>();
        System.out.println("   List<String>.getClass()  == List<Integer>.getClass()  ? "
                + (names.getClass() == scores.getClass()));
        System.out.println("   → 编译后都是同一个裸 List（存 Object），类型参数只活在编译期");

        // 运行期反射可以往 List<String> 塞 Integer —— 擦除的实证
        java.lang.reflect.Method add;
        try {
            add = names.getClass().getMethod("add", Object.class);
            add.invoke(names, 12345);              // 绕过编译期检查，成功（运行期无类型信息）
            System.out.println("   反射成功塞入 Integer（编译器不知道，运行时也不拦——擦除的实证）");
            try {
                String s = names.get(0);           // 但取出时强转 String → 炸
                System.out.println("   s = " + s);
            } catch (ClassCastException e) {
                System.out.println("   取出时抛 ClassCastException：" + e.getMessage()
                        + " —— 元素实际是 Integer，编译期生成的强转在运行期才暴露");
            }
        } catch (ReflectiveOperationException e) {
            System.out.println("   反射调用失败：" + e);
        }
    }
}
