/* project/CaptchaGenerator.java —— 验证码生成器核心类（封装字符集与生成逻辑）
 * 验证环境：OpenJDK 17.0.16
 * 编译：javac CaptchaGenerator.java CaptchaApp.java
 * 运行：java CaptchaApp [长度] [数量] [digits|letters|mixed]
 * 已验证：本环境编译零错误，三种字符集与批量生成均符合预期
 */
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

public class CaptchaGenerator {
    // 三种字符集。MIXED 去除易混淆字符 I/O/0/1，降低人工辨识成本。
    public enum Charset {
        DIGITS("0123456789"),
        LETTERS("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"),
        MIXED("ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789");

        private final String chars;

        Charset(String chars) {
            this.chars = chars;
        }

        String chars() {
            return chars;
        }
    }

    private final Random random = new Random();

    // 生成单个指定长度、指定字符集的验证码
    public String generate(int length, Charset charset) {
        if (length <= 0) {
            throw new IllegalArgumentException("长度必须大于 0");
        }
        String chars = charset.chars();
        StringBuilder sb = new StringBuilder(length);
        for (int i = 0; i < length; i++) {
            sb.append(chars.charAt(random.nextInt(chars.length())));
        }
        return sb.toString();
    }

    // 批量生成 count 个验证码
    public List<String> generateBatch(int length, Charset charset, int count) {
        if (count <= 0) {
            throw new IllegalArgumentException("数量必须大于 0");
        }
        List<String> codes = new ArrayList<>(count);
        for (int i = 0; i < count; i++) {
            codes.add(generate(length, charset));
        }
        return codes;
    }
}
