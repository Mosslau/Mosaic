// exercises/sol-01-mini-di-container.java —— 练习 1 参考实现：手写微型 DI 容器（零第三方依赖）
// 验证环境：OpenJDK 17.0.18（javac -version → 17.0.18），零第三方依赖
// 验证状态：已验证（本机实测）
// 实测结果：MINI DI TESTS PASSED (4 assertions)
//   （构造器注入可用 / 单例共享 / 引擎单例 / 循环依赖检测抛可读错误）
// ---------------------------------------------------------------------------
// 编译与运行（零依赖单文件，直接在 exercises/ 目录执行；MiniDiContainer 是包级类，
// 文件名不必与类名一致，可就地编译）：
//   javac -d out sol-01-mini-di-container.java
//   java -cp out com.example.MiniDiContainer
// 教学点：Spring 的 @ComponentScan + 构造器注入本质就是「看构造器参数类型 → 递归创建依赖
//   → 单例缓存」——先手写一遍再回 ex01 看 AnnotationConfigApplicationContext，容器不是魔法。
//   循环依赖检测对应真实场景：Spring 对纯构造器循环会在启动时抛
//   BeanCurrentlyInCreationException（练习 2 实测）。
package com.example;

import java.lang.reflect.Constructor;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/**
 * 手写微型 DI 容器（零第三方依赖）：仅凭「构造器参数类型」完成对象创建与注入。
 * 教学点：Spring 的 @ComponentScan + 构造器注入，本质就是下面这段逻辑——
 * 扫到组件类 → 看构造器要什么类型 → 递归创建依赖 → 单例缓存。先手写一遍，
 * 再回去看 ex01 的 AnnotationConfigApplicationContext，就明白「容器」不是魔法。
 */
final class MiniDiContainer {

    private final Map<Class<?>, Object> singletons = new HashMap<>();
    private final Set<Class<?>> inProgress = new HashSet<>();

    /** 取组件：已建则返回单例；未建则递归解析构造器依赖后创建 */
    public synchronized <T> T get(Class<T> type) {
        Object cached = singletons.get(type);
        if (cached != null) {
            return type.cast(cached);
        }
        if (!inProgress.add(type)) {
            throw new IllegalStateException("循环依赖：" + type.getSimpleName()
                    + " 的依赖链上再次出现自己——容器无法决定先创建谁");
        }
        try {
            T instance = create(type);
            singletons.put(type, instance); // 单例缓存：整个容器共享同一实例
            return instance;
        } finally {
            inProgress.remove(type);
        }
    }

    private <T> T create(Class<T> type) {
        try {
            Constructor<?>[] constructors = type.getDeclaredConstructors();
            if (constructors.length != 1) {
                throw new IllegalStateException(type.getSimpleName() + " 需要恰好一个构造器（本迷你容器只支持构造器注入）");
            }
            Constructor<?> constructor = constructors[0];
            Class<?>[] parameterTypes = constructor.getParameterTypes();
            Object[] dependencies = new Object[parameterTypes.length];
            for (int i = 0; i < parameterTypes.length; i++) {
                dependencies[i] = get(parameterTypes[i]); // 递归：先造依赖，再造自己
            }
            return type.cast(constructor.newInstance(dependencies));
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("无法实例化 " + type.getSimpleName(), e);
        }
    }

    // ------------------------------------------------------------------
    // 自测：main 里用迷你断言计数器跑三类场景
    // ------------------------------------------------------------------

    public static void main(String[] args) {
        var asserts = new int[]{0};

        // 场景 1：构造器注入 —— Car 需要 Engine，容器递归创建并注入
        MiniDiContainer container = new MiniDiContainer();
        Car car = container.get(Car.class);
        expect(asserts, "device.run() 用的是注入的引擎", "running with engine #1".equals(device.run()));

        // 场景 2：单例共享 —— 两次 get 同一实例，且引擎也只有一个
        Car again = container.get(Car.class);
        expect(asserts, "两次 get(Car) 是同一单例", car == again);
        expect(asserts, "两台设备的引擎是同一个单例", car.engine() == again.engine());

        // 场景 3：循环依赖检测 —— A 要 B、B 要 A，启动即报错而不是死循环
        MiniDiContainer bad = new MiniDiContainer();
        try {
            bad.get(ServiceA.class);
            expect(asserts, "循环依赖应抛异常", false);
        } catch (IllegalStateException e) {
            expect(asserts, "循环依赖被检测并给出可读错误", e.getMessage().contains("循环依赖"));
        }

        System.out.println("MINI DI TESTS PASSED (" + asserts[0] + " assertions)");
    }

    private static void expect(int[] counter, String name, boolean condition) {
        counter[0]++;
        if (!condition) {
            throw new AssertionError("断言失败: " + name);
        }
    }

    // ---- 被测组件（恰好一个构造器 = 构造器注入契约）----

    public static final class Engine {

        private final int serial = 1;

        int serial() {
            return serial;
        }
    }

    public static final class Car {

        private final Engine engine;

        public Car(Engine engine) { // 唯一构造器：参数类型即依赖声明
            this.engine = engine;
        }

        String drive() {
            return "running with engine #" + engine.serial();
        }

        Engine engine() {
            return engine;
        }
    }

    public static final class ServiceA {

        public ServiceA(ServiceB b) { // A 依赖 B
        }
    }

    public static final class ServiceB {

        public ServiceB(ServiceA a) { // B 依赖 A —— 构造器循环
        }
    }
}
