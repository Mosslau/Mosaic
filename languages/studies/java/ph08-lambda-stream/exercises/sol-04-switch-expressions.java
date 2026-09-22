// exercises/sol-04-switch-expressions.java —— 练习 4 参考实现：用 Switch Expressions 重写 if-else 分支
// 验证环境：OpenJDK 17.0.18
// 编译：javac sol-04-switch-expressions.java
// 运行：java SwitchExpressionsSol（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
class SwitchExpressionsSol {
    public static void main(String[] args) {
        System.out.println("grade(85) = " + grade(85));      // 良好
        System.out.println("grade(105) = " + grade(105));    // 非法分数
        System.out.println("grade(59) = " + grade(59));      // 不及格
        System.out.println("dayLabel(3) = " + dayLabel(3));  // 工作日
        System.out.println("dayLabel(6) = " + dayLabel(6));  // 周末
        System.out.println("dayLabel(9) = " + dayLabel(9));  // 非法日期
        // 为什么 int 型 switch 表达式必须写 default：int 取值有 2^32 种，编译器无法证明
        // 有限个 case 已穷尽，没有 default 就是编译错误（the switch expression does not cover
        // all possible input values）；枚举全覆盖时可省略 default。
    }

    // 成绩分级：switch 是表达式，直接 return；块体分支用 yield 产出值
    // 注意 101~109 与 100 一样 /10 都得 10，所以 case 10 必须用块体再判一次越界
    static String grade(int score) {
        return switch (score / 10) {
            case 9 -> "优秀";
            case 10 -> {
                yield score == 100 ? "优秀" : "非法分数";   // 101~109 也落到此分支
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

    // 周几判断：箭头语法多值合并，天然无穿透、无需 break
    static String dayLabel(int day) {
        return switch (day) {
            case 1, 2, 3, 4, 5 -> "工作日";
            case 6, 7 -> "周末";
            default -> "非法日期";
        };
    }
}
