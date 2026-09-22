/* examples/ex01-StringReverse.java —— 字符串反转（利用 StringBuilder.reverse）
 * 验证环境：OpenJDK 17.0.16
 * 编译：javac ex01-StringReverse.java
 * 运行：java StringReverse
 * 已验证：本环境编译零错误，输出符合注释中的期望值
 */
class StringReverse {
    static String reverse(String s) {
        return new StringBuilder(s).reverse().toString();
    }

    public static void main(String[] args) {
        System.out.println(reverse("hello"));      // olleh
        System.out.println(reverse("Java"));       // avaJ
        System.out.println(reverse("上海自来水"));   // 水来自海上
    }
}
