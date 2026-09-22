/* exercises/sol-02-CharFrequency.java —— 练习 2 字符频次统计参考实现
 * 验证环境：OpenJDK 17.0.16
 * 编译：javac sol-02-CharFrequency.java
 * 运行：java CharFrequency
 * 已验证：本环境编译零错误，输出符合注释中的期望值
 */
class CharFrequency {
    // 返回长度 128 的计数数组，下标即 ASCII 码值，只统计 ASCII 范围内的字符
    static int[] count(String text) {
        int[] freq = new int[128];
        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            if (ch < 128) {
                freq[ch]++;
            }
        }
        return freq;
    }

    public static void main(String[] args) {
        System.out.println("--- \"hello world\" ---");
        int[] f1 = count("hello world");
        for (int i = 0; i < 128; i++) {
            if (f1[i] > 0) {
                System.out.println((char) i + " : " + f1[i]);
            }
        }
        System.out.println("--- \"aaa\" ---");
        int[] f2 = count("aaa");
        for (int i = 0; i < 128; i++) {
            if (f2[i] > 0) {
                System.out.println((char) i + " : " + f2[i]);
            }
        }
    }
}
