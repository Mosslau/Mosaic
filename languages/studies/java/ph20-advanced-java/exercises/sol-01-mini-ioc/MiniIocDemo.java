/*
 * exercises/sol-01-mini-ioc/MiniIocDemo.java —— 练习 1 参考实现演示
 * 验证：① 容器注入构造器依赖；② 调用链完整可用；③ 单例语义（两次 getBean 同一实例）。
 *
 * 验证环境：OpenJDK 17.0.18（Homebrew）
 * 编译：javac -encoding UTF-8 -d /tmp/tl20-cls MiniContainer.java MiniIocDemo.java
 * 运行：java -cp /tmp/tl20-cls MiniIocDemo
 * 本机已实测：3 段输出 PASS
 */
interface Notifier {
    void notify(String msg);
}

/** 一个带依赖的实现：构造器要求 Notifier，这正是容器要替调用方注入的依赖。 */
interface Greeter {
    String greet(String who);
}

final class ConsoleNotifier implements Notifier {
    private int count = 0;

    @Override
    public void notify(String msg) {
        count++;
        System.out.println("    [console-notifier#" + count + "] " + msg);
    }
}

final class PoliteGreeter implements Greeter {
    private final Notifier notifier;          // 依赖：由容器注入，调用方从不 new Notifier

    PoliteGreeter(Notifier notifier) {
        this.notifier = notifier;
    }

    @Override
    public String greet(String who) {
        notifier.notify("greeting " + who);
        return "你好，" + who + "！";
    }
}

public final class MiniIocDemo {
    public static void main(String[] args) {
        MiniContainer container = new MiniContainer();
        // 只注册「接口 → 实现」，谁依赖谁由容器在装配时自己解析
        container.register(Notifier.class, ConsoleNotifier.class);
        container.register(Greeter.class, PoliteGreeter.class);

        Greeter greeter = container.getBean(Greeter.class);      // 容器递归注入 ConsoleNotifier
        String result = greeter.greet("Tenet");
        check(result.startsWith("你好"), "greet 返回正常：" + result);

        check(container.getBean(Greeter.class) == greeter, "单例语义：两次 getBean 是同一实例");
        check(container.getBean(Notifier.class) instanceof ConsoleNotifier, "Notifier 解析到注册实现");
        System.out.println("ALL PASS: 3/3");
    }

    private static void check(boolean cond, String msg) {
        System.out.println((cond ? "PASS: " : "FAIL: ") + msg);
        if (!cond) {
            System.exit(1);
        }
    }
}
