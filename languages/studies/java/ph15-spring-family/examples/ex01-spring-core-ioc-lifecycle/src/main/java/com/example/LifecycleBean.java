package com.example;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.springframework.beans.factory.DisposableBean;
import org.springframework.beans.factory.InitializingBean;

/**
 * 生命周期观察 Bean：同一颗 Bean 上叠满四代初始化回调，用 LifecycleRecorder
 * 记录实际触发顺序——这是 ph15 主文档 3.2 节「回调顺序表」的实测来源。
 *
 * 预期顺序（Spring 官方语义，本示例实测）：
 *   构造 → @PostConstruct → afterPropertiesSet（InitializingBean）→ customInit（@Bean initMethod）
 * 销毁顺序（Spring 官方语义，与初始化相反方向）：
 *   @PreDestroy → destroy（DisposableBean）→ customDestroy（@Bean destroyMethod）
 */
public class LifecycleBean implements InitializingBean, DisposableBean {

    public LifecycleBean() {
        LifecycleRecorder.record("constructor");
    }

    @PostConstruct
    public void postConstruct() {
        LifecycleRecorder.record("@PostConstruct");
    }

    @Override
    public void afterPropertiesSet() {
        LifecycleRecorder.record("afterPropertiesSet(InitializingBean)");
    }

    /** 由 @Bean(initMethod = "customInit") 指定 —— 三代初始化回调中最后触发 */
    public void customInit() {
        LifecycleRecorder.record("customInit(@Bean initMethod)");
    }

    @PreDestroy
    public void preDestroy() {
        LifecycleRecorder.record("@PreDestroy");
    }

    @Override
    public void destroy() {
        LifecycleRecorder.record("destroy(DisposableBean)");
    }

    /** 由 @Bean(destroyMethod = "customDestroy") 指定 —— 三代销毁回调中最后触发 */
    public void customDestroy() {
        LifecycleRecorder.record("customDestroy(@Bean destroyMethod)");
    }
}
