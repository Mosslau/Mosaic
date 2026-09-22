// project/common/src/main/java/com/example/common/TextStats.java —— 公共文本统计工具
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12；验证状态：已验证（随根目录 mvn clean package 构建）
package com.example.common;

/** 公共文本统计工具：放在依赖链最底层, 被 app 模块引用（依赖方向单向, 公共代码下沉） */
public final class TextStats {
    private TextStats() {
    }

    /** 行数：与 wc -l 语义一致（按换行符计数） */
    public static long countLines(String text) {
        return text.lines().count();
    }

    /** 单词数：按空白分隔, 空文本返回 0 */
    public static long countWords(String text) {
        if (text.isBlank()) {
            return 0;
        }
        return text.trim().split("\\s+").length;
    }

    /** 字符数：String 内部按 UTF-16 码元计数, 常用中文（BMP 区）每字 1 个码元 */
    public static long countChars(String text) {
        return text.length();
    }
}
