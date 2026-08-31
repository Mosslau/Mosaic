// examples/ex01-class-file.java —— class 文件结构与 javap 反汇编：魔数自检 + 可被 javap -c/-v/-l 解剖的示例类
// 对应主文档 6. 示例 1：读取自身 .class 字节验证魔数 0xCAFEBABE；配合 README 中的 javac/javap 命令观察字节码
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex01-class-file.java
// 运行：java Ex01ClassFile（注意是类名不是文件名；须从 .class 所在目录运行，程序要按相对名读取自身 class 文件）
// 验证状态：已验证：OpenJDK 17.0.18
// 运行前提：本文件同时用于「javac -g 与 -g:none 的字节码差异」对照（见 README），两种编译方式行为一致
import java.io.InputStream;

class Ex01ClassFile {
    static final String GREETING = "hello jvm";   // 编译期常量：反汇编中可看到 ConstantValue / ldc 指令
    private final int base;                       // 实例字段：javap 的字段表会列出
    private static int calls = 0;                 // 静态字段：可观察 getstatic/putstatic 指令

    Ex01ClassFile(int base) {
        this.base = base;
    }

    int add(int a, int b) {                       // 实例方法：反汇编可见 aload_0 + invokevirtual 的调用约定
        calls++;
        return a + b + base;
    }

    static long sumUp(int n) {                    // 静态方法：含循环，反汇编可见 goto 跳转与 iload/iadd
        long total = 0;
        for (int i = 1; i <= n; i++) total += i;
        return total;
    }

    public static void main(String[] args) throws Exception {
        // 1. 从自身 classpath 读取本类的 .class 字节，验证魔数 0xCAFEBABE（class 文件的固定开头）
        InputStream in = Ex01ClassFile.class.getResourceAsStream("Ex01ClassFile.class");
        if (in == null) throw new IllegalStateException("找不到 Ex01ClassFile.class，请从 .class 所在目录运行");
        byte[] magic = in.readNBytes(4);
        long magicInt = ((magic[0] & 0xffL) << 24) | ((magic[1] & 0xffL) << 16)
                | ((magic[2] & 0xffL) << 8) | (magic[3] & 0xffL);
        // 注意：必须写成 0xCAFEBABEL（long 字面量）——若写 0xCAFEBABE 它是 int 字面量，因最高位为 1 而为负数，
        // 与 long 比较时符号扩展成 0xFFFFFFFFCAFEBABE，恒不相等（本文件开发时踩过，正是教学点）
        System.out.printf("class 文件魔数 = 0x%08X (应为 0xCAFEBABE): %s%n", magicInt,
                magicInt == 0xCAFEBABEL ? "通过" : "不符");
        if (magicInt != 0xCAFEBABEL) throw new AssertionError("魔数不是 0xCAFEBABE");

        // 2. 跑一遍方法，保证反汇编与运行行为一致（add 有实例字段参与，sumUp 有循环）
        Ex01ClassFile obj = new Ex01ClassFile(10);
        int r = obj.add(3, 4);
        long s = sumUp(100);
        System.out.println("add(3,4)+base(10) = " + r + "  (期望 17)");
        System.out.println("sumUp(100) = " + s + "  (期望 5050)");
        if (r != 17 || s != 5050) throw new AssertionError("运行结果与期望不符");
        System.out.println("自检通过：魔数验证 + 方法运行结果正确");
    }
}
