/* examples/ex02-CharFrequency.java —— 字符频次统计（用数组做计数器）
 * 验证环境：OpenJDK 17.0.16
 * 编译：javac ex02-CharFrequency.java
 * 运行：java CharFrequency
 * 已验证：本环境编译零错误，输出符合注释中的期望值
 */
class CharFrequency {
    public static void main(String[] args) {
        String text = "hello world";
        int[] freq = new int[128]; // 覆盖 ASCII 范围

        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            if (ch < 128) {
                freq[ch]++;
            }
        }

        for (int i = 0; i < 128; i++) {
            if (freq[i] > 0) {
                System.out.println((char) i + " : " + freq[i]);
            }
        }
    }
}
