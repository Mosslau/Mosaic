// exercises/sol-05-pattern-matching.java —— 练习 5 参考实现：用 Pattern Matching 改写 instanceof 判断
// 验证环境：OpenJDK 17.0.18
// 编译：javac sol-05-pattern-matching.java
// 运行：java PatternMatchingSol（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
class PatternMatchingSol {

    // 小型事件类型层次：共同父类型 + 三个具体事件
    abstract static class Event { }

    static final class TextEvent extends Event {
        final String content;
        TextEvent(String content) { this.content = content; }
    }

    static final class ClickEvent extends Event {
        final int x, y;
        ClickEvent(int x, int y) { this.x = x; this.y = y; }
    }

    static final class TimeoutEvent extends Event {
        final long millis;
        TimeoutEvent(long millis) { this.millis = millis; }
    }

    public static void main(String[] args) {
        Event[] events = {
                new TextEvent("hello"),
                new TextEvent("超过十个字符的长文本内容"),
                new ClickEvent(3, 4),
                new TimeoutEvent(5000),
                null,   // null 输入：必须走 else 分支，不抛 NullPointerException
        };
        for (Event e : events) {
            String oldResult = describeOld(e);
            String newResult = describeNew(e);
            if (!oldResult.equals(newResult)) {
                throw new AssertionError("新旧版本输出不一致: " + oldResult + " vs " + newResult);
            }
            System.out.println(newResult);
        }
        System.out.println("新旧两版输出完全一致");
    }

    // 旧版（对照）：instanceof + 显式强转，样板多、易写错
    static String describeOld(Event e) {
        if (e instanceof TextEvent) {
            TextEvent t = (TextEvent) e;             // 显式强转
            if (t.content.length() > 10) {
                return "长文本事件, 长度 " + t.content.length();
            }
            return "文本事件: " + t.content;
        } else if (e instanceof ClickEvent) {
            ClickEvent c = (ClickEvent) e;           // 显式强转
            return "点击事件: (" + c.x + ", " + c.y + ")";
        } else if (e instanceof TimeoutEvent) {
            TimeoutEvent t = (TimeoutEvent) e;       // 显式强转
            return "超时事件: " + t.millis + " ms";
        } else {
            return "未知事件";
        }
    }

    // 新版：instanceof 模式匹配，匹配成功即声明模式变量，全文无显式强转
    static String describeNew(Event e) {
        if (e instanceof TextEvent t && t.content.length() > 10) {
            // 流式作用域：&& 右侧可继续用模式变量 t
            return "长文本事件, 长度 " + t.content.length();
        } else if (e instanceof TextEvent t) {
            return "文本事件: " + t.content;
        } else if (e instanceof ClickEvent c) {
            return "点击事件: (" + c.x + ", " + c.y + ")";
        } else if (e instanceof TimeoutEvent t) {
            return "超时事件: " + t.millis + " ms";
        } else {
            return "未知事件";   // null 匹配不到任何模式，落到此分支
        }
    }

    // 加分项（需 JDK 21+，本环境 OpenJDK 17 无法编译，仅作注释示意）：
    // static String describeSwitch(Event e) {
    //     return switch (e) {
    //         case null -> "未知事件";
    //         case TextEvent t when t.content.length() > 10 -> "长文本事件, 长度 " + t.content.length();
    //         case TextEvent t -> "文本事件: " + t.content;
    //         case ClickEvent c -> "点击事件: (" + c.x + ", " + c.y + ")";
    //         case TimeoutEvent t -> "超时事件: " + t.millis + " ms";
    //         default -> "未知事件";
    //     };
    // }
}
