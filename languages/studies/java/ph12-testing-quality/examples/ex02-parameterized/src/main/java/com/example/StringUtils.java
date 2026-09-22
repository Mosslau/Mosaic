package com.example;

/**
 * 被测工具类：判空与反转。纯函数（无状态、无外部依赖），是最适合单元测试的一类代码。
 */
public final class StringUtils {

    private StringUtils() {
        // 工具类禁止实例化
    }

    /** 空白判定：null、空串、纯空白字符（含 \t \n）都算空。 */
    public static boolean isBlank(String s) {
        return s == null || s.trim().isEmpty();
    }

    /** 反转字符串；null 视为空串（防御性输入处理）。 */
    public static String reverse(String s) {
        if (s == null) {
            return "";
        }
        return new StringBuilder(s).reverse().toString();
    }
}
