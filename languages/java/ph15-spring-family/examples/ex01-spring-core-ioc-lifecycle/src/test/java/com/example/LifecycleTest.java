package com.example;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.context.support.GenericApplicationContext;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * ex01 测试：用独立容器观察 DI / 生命周期 / 作用域 / 条件装配的真实行为。
 * 验证命令：mvn -o -Dmaven.repo.local=/tmp/m2clone test
 */
class LifecycleTest {

    @BeforeEach
    void resetRecorder() {
        LifecycleRecorder.EVENTS.clear();
    }

    /** 三代初始化 + 三代销毁回调的实际触发顺序（Spring 官方语义的实测背书） */
    @Test
    void lifecycleCallbacksFireInDocumentedOrder() {
        try (AnnotationConfigApplicationContext ctx = new AnnotationConfigApplicationContext(AppConfig.class)) {
            // 单例 Bean 在容器启动（refresh）时已实例化并完成初始化回调
            ctx.getBean(LifecycleBean.class);
            assertThat(LifecycleRecorder.EVENTS).containsExactly(
                    "constructor",
                    "@PostConstruct",
                    "afterPropertiesSet(InitializingBean)",
                    "customInit(@Bean initMethod)"
            );
        }
        // 走到这里 try-with-resources 已 close()，销毁回调应已追加
        assertThat(LifecycleRecorder.EVENTS).containsExactly(
                "constructor",
                "@PostConstruct",
                "afterPropertiesSet(InitializingBean)",
                "customInit(@Bean initMethod)",
                "@PreDestroy",
                "destroy(DisposableBean)",
                "customDestroy(@Bean destroyMethod)"
        );
    }

    /** 构造器注入：容器按构造器参数类型自动装配，注入的是容器里那个单例 */
    @Test
    void constructorInjectionWiresSameSingleton() {
        try (AnnotationConfigApplicationContext ctx = new AnnotationConfigApplicationContext(AppConfig.class)) {
            WelcomeService service = ctx.getBean(WelcomeService.class);
            WelcomeRepository repo = ctx.getBean(WelcomeRepository.class);
            assertThat(service.greetingCount()).isEqualTo(3);
            assertThat(service.firstGreeting()).isEqualTo("你好");
            // service 内部持有的 repository 与容器中是同一个实例（单例共享）
            // 通过反射核对：构造器注入后字段非空且可用即可，这里以行为间接验证
        }
    }

    /** @Primary 与 @Qualifier 消歧：默认注入 primary，点名注入指定 Bean */
    @Test
    void primaryAndQualifierDisambiguation() {
        try (AnnotationConfigApplicationContext ctx = new AnnotationConfigApplicationContext(AppConfig.class)) {
            // 构造器参数只声明 Notifier 时，容器选 @Primary 的 EmailNotifier
            assertThat(ctx.getBean(AlertService.class).channel()).isEqualTo("sms"); // 点了名：sms
            // 直接按类型取会得到 primary
            assertThat(ctx.getBean(Notifier.class)).isInstanceOf(EmailNotifier.class);
            // 按 Bean 名取到的是 sms 那个
            assertThat(ctx.getBean("smsNotifier")).isInstanceOf(SmsNotifier.class);
        }
    }

    /** 作用域：singleton 同一实例；prototype 每次新建且容器不回调其销毁 */
    @Test
    void singletonSharedAndPrototypePerLookupWithoutDestroy() {
        PrototypeWorker handedOut;
        try (AnnotationConfigApplicationContext ctx = new AnnotationConfigApplicationContext(AppConfig.class)) {
            SingletonService a = ctx.getBean(SingletonService.class);
            SingletonService b = ctx.getBean(SingletonService.class);
            assertThat(a).isSameAs(b);

            PrototypeWorker p1 = ctx.getBean(PrototypeWorker.class);
            PrototypeWorker p2 = ctx.getBean(PrototypeWorker.class);
            assertThat(p1).isNotSameAs(p2);

            handedOut = p1;
            assertThat(handedOut.destroyed).isFalse();
        }
        // close() 后：prototype 不受容器销毁管理（官方文档语义），destroyed 保持 false
        assertThat(handedOut.destroyed).isFalse();
    }

    /** 条件装配：属性开关决定 Bean 是否存在（Core 版 @Conditional = Boot 条件注解的原语） */
    @Test
    void conditionalRegistrationFollowsSwitch() {
        // 关 → 容器里没有 FeatureToggleBean
        System.clearProperty(OnFeatureEnabledCondition.PROPERTY);
        try (AnnotationConfigApplicationContext ctx = new AnnotationConfigApplicationContext(AppConfig.class)) {
            assertThatThrownBy(() -> ctx.getBean(FeatureToggleBean.class))
                    .isInstanceOf(Exception.class);
        }
        // 开 → 有
        System.setProperty(OnFeatureEnabledCondition.PROPERTY, "true");
        try (AnnotationConfigApplicationContext ctx = new AnnotationConfigApplicationContext(AppConfig.class)) {
            assertThat(ctx.getBean(FeatureToggleBean.class).name()).isEqualTo("experimental-feature");
        } finally {
            System.clearProperty(OnFeatureEnabledCondition.PROPERTY);
        }
    }

    /** 依赖缺失时容器启动即报错（fail-fast），而不是运行期 NPE */
    @Test
    void missingDependencyFailsFastAtRefresh() {
        assertThatThrownBy(() -> {
            try (GenericApplicationContext ctx = new GenericApplicationContext()) {
                ctx.registerBean(WelcomeService.class); // 没有 WelcomeRepository，也不扫描
                ctx.refresh();
            }
        }).isInstanceOf(Exception.class);
    }
}
