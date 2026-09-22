/*
 * project/mini-ioc/src/com/tenet/minioc/MiniContext.java
 * 简易 IOC 容器核心（注解驱动）：
 *   注册：把 @Component 类交给容器（真实 Spring 靠 classpath 扫描，这里显式列出，核心语义一致）
 *   装配：优先使用 @Inject 构造器并解析参数类型；对象创建后再做 @Inject 字段注入
 *   作用域：默认单例（Spring 的 singleton）
 *   依赖解析：参数/字段类型是接口 → 在注册表里找唯一可赋值的实现；有多个实现则报歧义
 *   循环依赖：创建中用「创建栈」检测 A→B→A，抛出含依赖链的异常（Spring 用三级缓存解决循环，
 *             本容器是教学版：检测并拒绝）
 *
 * 验证环境：OpenJDK 17.0.18（Homebrew）
 * 编译：javac -encoding UTF-8 -d /tmp/tl20-cls src/com/tenet/minioc/*.java
 * 运行：java -cp /tmp/tl20-cls com.tenet.minioc.MiniIocDemo
 * 本机已实测：6/6 PASS（含循环依赖被检测并打印依赖链）
 */
package com.tenet.minioc;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 循环依赖异常：携带当前创建链方便定位。 */
final class CycleDependencyException extends RuntimeException {
    CycleDependencyException(String beanName, Deque<String> chain) {
        super("检测到循环依赖，创建链: " + String.join(" -> ", chain) + " -> " + beanName);
    }
}

public final class MiniContext {

    private final Map<String, Class<?>> defs = new LinkedHashMap<>();      // bean 名 → 组件类（注册顺序即遍历顺序）
    private final Map<String, Object> singletons = new LinkedHashMap<>();   // bean 名 → 单例
    private final Deque<String> creating = new ArrayDeque<>();              // 当前创建栈（循环检测用）

    /** 注册一组 @Component 组件，bean 名取注解 value，缺省简单类名首字母小写。 */
    public void register(Class<?>... componentClasses) {
        for (Class<?> c : componentClasses) {
            if (!c.isAnnotationPresent(Component.class)) {
                throw new IllegalArgumentException(c.getName() + " 缺少 @Component 注解");
            }
            String name = beanNameOf(c);
            if (defs.put(name, c) != null) {
                throw new IllegalArgumentException("bean 名重复: " + name);
            }
        }
    }

    public boolean containsBean(String name) {
        return defs.containsKey(name);
    }

    @SuppressWarnings("unchecked")
    public <T> T getBean(String name) {
        Object hit = singletons.get(name);
        if (hit != null) {
            return (T) hit;
        }
        Class<?> type = defs.get(name);
        if (type == null) {
            throw new IllegalArgumentException("没有注册名为 " + name + " 的 bean");
        }
        if (creating.contains(name)) {
            throw new CycleDependencyException(name, new ArrayDeque<>(creating));
        }
        creating.addLast(name);
        try {
            Object bean = instantiate(name, type);
            singletons.put(name, bean);          // 单例：先缓存后注入（本容器不做 setter 循环引用，直接装配完再缓存）
            return (T) bean;
        } finally {
            creating.removeLast();
        }
    }

    /** 实例化：① @Inject 构造器（取唯一带注解的）装配 → ② @Inject 字段注入。 */
    private Object instantiate(String name, Class<?> type) {
        try {
            Constructor<?> ctor = pickInjectConstructor(type);
            ctor.setAccessible(true);
            Class<?>[] paramTypes = ctor.getParameterTypes();
            Object[] args = new Object[paramTypes.length];
            for (int i = 0; i < paramTypes.length; i++) {
                args[i] = getBean(resolveBeanName(paramTypes[i], name));    // 构造器参数按类型解析依赖
            }
            Object bean = ctor.newInstance(args);
            injectFields(name, type, bean);
            return bean;
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("装配 " + name + " 失败", e);
        }
    }

    /** 构造器选择：带 @Inject 的构造器优先；没有则用无参构造器。 */
    private static Constructor<?> pickInjectConstructor(Class<?> type) {
        for (Constructor<?> c : type.getDeclaredConstructors()) {
            if (c.isAnnotationPresent(Inject.class)) {
                return c;
            }
        }
        try {
            return type.getDeclaredConstructor();
        } catch (NoSuchMethodException e) {
            throw new IllegalStateException(type.getName() + " 需要 @Inject 构造器或可见的无参构造器", e);
        }
    }

    /** 字段注入：遍历带 @Inject 的非静态字段反射赋值。 */
    private void injectFields(String beanName, Class<?> type, Object bean) throws IllegalAccessException {
        for (Field f : type.getDeclaredFields()) {
            if (f.isAnnotationPresent(Inject.class)) {
                f.setAccessible(true);
                Object dep = getBean(resolveBeanName(f.getType(), beanName));
                f.set(bean, dep);
            }
        }
    }

    /** 类型 → bean 名：接口类型在注册表里找「唯一可赋值实现」；具体类/只有一个实现时用缺省名。
     *  多个实现可赋给同一接口 → 歧义，要求用 @Component(value) 显式命名。 */
    private String resolveBeanName(Class<?> wanted, String requester) {
        List<String> candidates = new ArrayList<>();
        for (Map.Entry<String, Class<?>> e : defs.entrySet()) {
            Class<?> impl = e.getValue();
            if (wanted.isAssignableFrom(impl)) {
                candidates.add(e.getKey());
            }
        }
        if (candidates.size() == 1) {
            return candidates.get(0);
        }
        if (candidates.size() > 1) {
            throw new IllegalStateException(requester + " 依赖 " + wanted.getName()
                    + " 存在多个实现 " + candidates + "，请显式 @Component(value) 区分并用类型取 bean");
        }
        // 接口没有任何实现：退回默认名（若恰好注册了同名具体类也能命中）
        return defaultName(wanted);
    }

    private static String beanNameOf(Class<?> c) {
        Component a = c.getAnnotation(Component.class);
        return a.value().isEmpty() ? defaultName(c) : a.value();
    }

    private static String defaultName(Class<?> c) {
        String simple = c.getSimpleName();
        return Character.toLowerCase(simple.charAt(0)) + simple.substring(1);
    }
}
