// 04 · 受检异常：错误处理的一场设计赌注演示
// 运行：java demos/04_exception_handling.java

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

class ExceptionHandlingDemo {

    // 受检异常：方法签名承诺"可能失败"——调用方不处理/不上抛就编译不过
    // 把下面的 throws IOException 删掉试试：javac 会报 unreported exception
    static String readConfig() throws IOException {
        return Files.readString(Path.of("app.conf"));
    }

    // 不受检异常（RuntimeException 子类）：编译器不强制，运行时才抛
    static int divide(int a, int b) {
        return a / b;                       // b == 0 → ArithmeticException（不受检）
    }

    // Spring 式包装：把受检异常包成不受检，让上层不必层层声明
    static class ConfigException extends RuntimeException {
        ConfigException(String msg, Throwable cause) { super(msg, cause); }
    }
    static String loadConfigQuietly() {
        try {
            return readConfig();
        } catch (IOException e) {
            throw new ConfigException("配置读取失败（已包装为不受检）", e);
        }
    }

    public static void main(String[] args) {
        System.out.println("== 1. 受检异常：三种处理姿势 ==");
        // 姿势 A：就地 catch（注释里演示了删除 throws 会编译失败）
        try {
            readConfig();
        } catch (IOException e) {
            System.out.println("   [catch] 配置不存在也没关系：" + e.getClass().getSimpleName());
        }
        // 姿势 B：上抛（见 readConfig 签名，loadConfigQuietly 用姿势 C）
        // 姿势 C：包装成不受检（见下）

        System.out.println("\n== 2. 不受检异常：编译器不拦，运行时才炸 ==");
        try {
            divide(1, 0);
        } catch (ArithmeticException e) {
            System.out.println("   divide(1,0) → " + e + "（不受检，没人强制你 catch）");
        }

        System.out.println("\n== 3. 包装模式：受检 → 不受检（Spring 的 DataAccessException 同款思路）==");
        try {
            loadConfigQuietly();
        } catch (ConfigException e) {
            System.out.println("   " + e.getMessage());
            System.out.println("   原因链：caused by " + e.getCause().getClass().getSimpleName()
                    + "（异常携带完整上下文）");
        }

        System.out.println("\n== 4. finally：无论异常与否都执行 ==");
        try {
            System.out.println("   try 里做点事，然后抛一个不受检异常");
            throw new IllegalStateException("模拟中途失败");
        } catch (IllegalStateException e) {
            System.out.println("   catch 到：" + e.getMessage());
        } finally {
            System.out.println("   finally 执行：清理资源（对应 try-with-resources 的语义）");
        }

        System.out.println("\n== 5. 栈迹：错误的排障资产 ==");
        try {
            divide(1, 0);
        } catch (ArithmeticException e) {
            System.out.println("   " + e);   // 完整类名 + 消息；e.printStackTrace() 有调用栈
        }
    }
}
