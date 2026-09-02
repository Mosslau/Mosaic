package com.example;

import org.springframework.context.annotation.Scope;
import org.springframework.stereotype.Component;

/**
 * 默认作用域 Bean（singleton）：容器启动即创建（非懒加载），getBean 永远同一实例。
 * 无状态服务都该是它——线程安全靠「无共享可变状态」，而不是靠 new 一个对象。
 */
@Component
public class SingletonService {

    /** 实例标识：同一个容器里只该出现一次 */
    private final long instanceId = System.nanoTime();

    public long instanceId() {
        return instanceId;
    }
}
