// examples/ex06-switch-pattern-matching.java —— switch 模式匹配 + case null（Java 21+）
// 对应主文档 6. 示例 5 后半：按类型分派 + null 分支
// 验证环境：需 JDK 21+（switch 模式匹配 JEP 441 在 Java 21 正式化）
// 编译：javac ex06-switch-pattern-matching.java
// 运行：java SwitchPatternMatching（注意是类名不是文件名）
// 验证状态：未在本环境验证（本环境为 OpenJDK 17.0.18，switch 模式匹配需 Java 21+；
//           代码语法按 JEP 441 正式规范书写，在 JDK 21+ 上可直接编译运行）
class SwitchPatternMatching {
    public static void main(String[] args) {
        System.out.println(classify("abc"));    // 字符串: abc
        System.out.println(classify(42));       // 整数: 42
        System.out.println(classify(null));     // 空值
        System.out.println(classify(3.14));     // 其他类型
    }

    static String classify(Object obj) {         // 需 Java 21+（case null / 类型模式）
        return switch (obj) {
            case null -> "空值";
            case String s -> "字符串: " + s;
            case Integer i -> "整数: " + i;
            case Long l -> "长整型: " + l;
            default -> "其他类型";
        };
    }
}
