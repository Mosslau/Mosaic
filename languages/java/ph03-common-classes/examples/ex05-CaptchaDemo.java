/* examples/ex05-CaptchaDemo.java —— 验证码生成器 + Integer 缓存演示
 * 验证环境：OpenJDK 17.0.16
 * 编译：javac ex05-CaptchaDemo.java
 * 运行：java CaptchaDemo
 * 已验证：本环境编译零错误，输出为 5 个 6 位随机验证码 + 固定缓存/equals 结果
 */
import java.util.Random;

class CaptchaDemo {
    // 生成指定长度的验证码（去除易混淆字符 I/O/0/1）
    static String generate(int length) {
        String chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
        Random rand = new Random();
        StringBuilder sb = new StringBuilder(length);
        for (int i = 0; i < length; i++) {
            sb.append(chars.charAt(rand.nextInt(chars.length())));
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        // 自动装箱：int → Integer
        Integer count = 5;  // 等价 Integer.valueOf(5)

        System.out.println("生成 " + count + " 个验证码:");
        for (int i = 0; i < count; i++) {  // 自动拆箱
            System.out.println("  " + generate(6));
        }

        // Integer 缓存范围演示
        Integer a = 127, b = 127;
        Integer c = 128, d = 128;
        System.out.println("127 == 127: " + (a == b));          // true（命中缓存）
        System.out.println("128 == 128: " + (c == d));          // false（不同对象）
        System.out.println("128 equals 128: " + c.equals(d));   // true（内容比较）
    }
}
