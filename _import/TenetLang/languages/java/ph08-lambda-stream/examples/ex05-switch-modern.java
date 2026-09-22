// examples/ex05-switch-modern.java —— Switch Expressions + instanceof 模式匹配（Java 14/16 语法）
// 对应主文档 6. 示例 5 前半：传统 switch 穿透对照、箭头语法、yield、instanceof 模式匹配
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex05-switch-modern.java
// 运行：java SwitchModern（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
class SwitchModern {
    public static void main(String[] args) {
        System.out.println("传统: " + traditional(3));

        int day = 3;   // Switch Expressions（Java 14+）：箭头语法无穿透
        String label = switch (day) {
            case 1, 2, 3 -> "工作日";
            case 6, 7 -> "周末";
            default -> "非法日期";          // int 必须 default（穷尽）
        };
        System.out.println("Switch Expressions: " + label);

        System.out.println("成绩: " + grade(85));   // yield：块体分支产出值

        printShape("hello");   // instanceof 模式匹配（Java 16+）
        printShape(42);
        printShape(3.14);
    }

    static String traditional(int day) {   // 传统 switch：每个 case 必须 break，漏写即穿透
        String r;
        switch (day) {
            case 1: case 2: case 3: r = "工作日"; break;
            case 6: case 7: r = "周末"; break;
            default: r = "非法日期";
        }
        return r;
    }

    static String grade(int score) {
        return switch (score / 10) {
            case 9 -> "优秀";
            case 10 -> {
                yield score == 100 ? "优秀" : "非法分数";   // 101~109 /10 也得 10，须再判越界
            }
            case 8 -> "良好";
            case 7 -> "中等";
            case 6 -> "及格";
            default -> {
                if (score < 0 || score > 100) yield "非法分数";
                yield "不及格";
            }
        };
    }

    static void printShape(Object obj) {
        if (obj instanceof String s) {           // 模式变量 s 直接可用
            System.out.println("字符串, 长度 " + s.length());
        } else if (obj instanceof Integer i) {
            System.out.println("整数, 平方 " + (i * i));
        } else {
            System.out.println("其他: " + obj);
        }
    }
}
