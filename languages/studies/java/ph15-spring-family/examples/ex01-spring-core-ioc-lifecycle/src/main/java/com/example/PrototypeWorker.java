package com.example;

import org.springframework.beans.factory.DisposableBean;
import org.springframework.context.annotation.Scope;
import org.springframework.stereotype.Component;

/**
 * prototype 作用域 Bean：每次 getBean / 每次注入都新建实例。
 * 教学点 1：容器只负责「发新实例」，不负责它的销毁——prototype 没有销毁回调
 *           （Spring 官方文档明确：容器不管理 prototype 的完整生命周期）。
 * 教学点 2：有状态的短命对象（如一次业务会话的上下文）才用它，绝大多数 Bean 不该是 prototype。
 */
@Component
@Scope("prototype")
public class PrototypeWorker implements DisposableBean {

    private final long instanceId = System.nanoTime();

    public long instanceId() {
        return instanceId;
    }

    public boolean destroyed;

    @Override
    public void destroy() {
        // 预期：prototype 实例销毁时容器【不会】调用本方法——由使用方自己清理
        this.destroyed = true;
    }
}
