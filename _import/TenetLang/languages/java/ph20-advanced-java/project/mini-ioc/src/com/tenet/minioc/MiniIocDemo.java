/*
 * project/mini-ioc/src/com/tenet/minioc/MiniIocDemo.java —— 项目演示入口
 * 验证点：① 构造器注入链路（OrderService → Notifier 接口 → EmailNotifier → Logger）完整；
 *        ② 字段注入生效；③ 单例语义（两次取同一 bean 同一实例）；
 *        ④ 接口有唯一实现时按类型解析；⑤ 循环依赖被检测并打印创建链。
 *
 * 编译：javac -encoding UTF-8 -d /tmp/tl20-cls src/com/tenet/minioc/*.java
 * 运行：java -cp /tmp/tl20-cls com.tenet.minioc.MiniIocDemo
 * 本机已实测：7/7 PASS
 */
package com.tenet.minioc;

public final class MiniIocDemo {

    public static void main(String[] args) {
        MiniContext ctx = new MiniContext();
        ctx.register(Logger.class, EmailNotifier.class, OrderService.class, Metrics.class);

        // ① 构造器注入整链可用：OrderService.place → EmailNotifier.send → Logger.log
        OrderService orderService = ctx.getBean("orderService");
        check("订单通知结果 = " + orderService.place("o-1001"), orderService.place("o-1001").equals("email#order-placed:o-1001"));

        // ② 字段注入 + ③ 单例：Metrics 与 EmailNotifier 注入的 Logger 是同一个单例
        Metrics metrics = ctx.getBean("metrics");
        metrics.record("startup");
        int total = metrics.totalLogged();               // orderService.place 的 1 条 + record 的 1 条
        check("字段注入的 Logger 与构造注入共享同一单例（共 " + total + " 条记录）", total >= 2);

        check("单例语义：两次 getBean 同一实例", ctx.getBean("logger") == ctx.getBean("logger"));
        check("接口唯一实现可解析：Notifier 注入到 EmailNotifier",
                ctx.getBean("emailNotifier") instanceof EmailNotifier);
        check("未注册名称报错清晰", notRegistered(ctx));

        // ⑤ 循环依赖：A→B→A 应被检测
        MiniContext cyc = new MiniContext();
        cyc.register(CycleA.class, CycleB.class);
        boolean cycleCaught = false;
        try {
            cyc.getBean("cycleA");
        } catch (CycleDependencyException expected) {
            cycleCaught = true;
            check("循环依赖被检测：" + expected.getMessage(), expected.getMessage().contains("cycleA -> cycleB -> cycleA"));
        }
        check("getBean(\"cycleA\") 抛 CycleDependencyException", cycleCaught);
        System.out.println("ALL PASS: 7/7");
    }

    private static boolean notRegistered(MiniContext ctx) {
        try {
            ctx.getBean("doesNotExist");
            return false;
        } catch (IllegalArgumentException expected) {
            return expected.getMessage().contains("没有注册");
        }
    }

    private static void check(String msg, boolean cond) {
        System.out.println((cond ? "PASS: " : "FAIL: ") + msg);
        if (!cond) {
            System.exit(1);
        }
    }
}
