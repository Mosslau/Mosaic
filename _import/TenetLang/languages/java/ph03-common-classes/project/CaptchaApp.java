/* project/CaptchaApp.java —— 验证码生成器 CLI 入口（命令行参数解析 + 演示）
 * 验证环境：OpenJDK 17.0.16
 * 编译：javac CaptchaGenerator.java CaptchaApp.java
 * 运行：java CaptchaApp [长度] [数量] [digits|letters|mixed]
 *   无参数：生成 5 个 6 位混合验证码
 * 已验证：本环境编译零错误，无参/带参运行均符合预期
 */
public class CaptchaApp {
    public static void main(String[] args) {
        int length = 6;
        int count = 5;
        CaptchaGenerator.Charset charset = CaptchaGenerator.Charset.MIXED;

        if (args.length >= 1) {
            length = Integer.parseInt(args[0]);
        }
        if (args.length >= 2) {
            count = Integer.parseInt(args[1]);
        }
        if (args.length >= 3) {
            charset = parseCharset(args[2]);
        }

        CaptchaGenerator generator = new CaptchaGenerator();
        System.out.println("生成 " + count + " 个 " + length + " 位验证码（字符集：" + charset + "）:");
        for (String code : generator.generateBatch(length, charset, count)) {
            System.out.println("  " + code);
        }
    }

    private static CaptchaGenerator.Charset parseCharset(String name) {
        String n = name.toLowerCase();
        if (n.equals("digits")) {
            return CaptchaGenerator.Charset.DIGITS;
        }
        if (n.equals("letters")) {
            return CaptchaGenerator.Charset.LETTERS;
        }
        if (n.equals("mixed")) {
            return CaptchaGenerator.Charset.MIXED;
        }
        throw new IllegalArgumentException("未知字符集: " + name + "（可用 digits/letters/mixed）");
    }
}
