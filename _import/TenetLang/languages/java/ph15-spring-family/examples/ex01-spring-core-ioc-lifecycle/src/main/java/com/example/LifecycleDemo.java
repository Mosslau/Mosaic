package com.example;

import org.springframework.context.annotation.AnnotationConfigApplicationContext;

/**
 * 手工演示入口（本环境以 mvn -o test 的 LifecycleTest 实测；IDE 里可直接运行本类）：
 * 打印 Bean 名称、生命周期回调顺序、作用域行为、条件装配开关。
 * 运行说明：需要 spring-context 在 classpath——IDE 运行即可；
 * 命令行可用 `mvn -o -Dmaven.repo.local=/tmp/m2clone test` 看等价断言输出。
 */
public class LifecycleDemo {

    public static void main(String[] args) {
        LifecycleRecorder.EVENTS.clear();
        try (AnnotationConfigApplicationContext ctx = new AnnotationConfigApplicationContext(AppConfig.class)) {
            System.out.println("== 容器内的 Bean ==");
            for (String name : ctx.getBeanDefinitionNames()) {
                System.out.println("  - " + name);
            }

            System.out.println("\n== 生命周期回调顺序（context.close() 前打印初始化，后打印销毁）==");
            System.out.println("init: " + LifecycleRecorder.EVENTS);

            // 作用域：singleton 同一实例；prototype 每次新建
            SingletonService s1 = ctx.getBean(SingletonService.class);
            SingletonService s2 = ctx.getBean(SingletonService.class);
            System.out.println("\nsingleton 两次 getBean 同一实例? " + (s1 == s2));
            PrototypeWorker p1 = ctx.getBean(PrototypeWorker.class);
            PrototypeWorker p2 = ctx.getBean(PrototypeWorker.class);
            System.out.println("prototype 两次 getBean 同一实例? " + (p1 == p2));

            // DI：@Primary / @Qualifier
            AlertService alert = ctx.getBean(AlertService.class);
            System.out.println("AlertService 注入的通道（@Qualifier→sms）: " + alert.channel());

            System.out.println("WelcomeService 注入 Repository 后可用: "
                    + ctx.getBean(WelcomeService.class).firstGreeting());
        }
        System.out.println("\n== close() 后的完整事件序列（含销毁回调）==");
        LifecycleRecorder.EVENTS.forEach(e -> System.out.println("  " + e));
    }
}
